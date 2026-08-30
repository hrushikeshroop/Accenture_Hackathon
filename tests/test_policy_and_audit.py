from __future__ import annotations

import asyncio
import shutil

import pytest
from pydantic import ValidationError

from controlplane.detectors.base import Detector
from controlplane.schemas.check_result import CheckResult, CheckStatus
from controlplane.schemas.decision import DecisionAction, RiskTier, StopReason
from controlplane.schemas.event import Actor, Candidate, ControlEvent
from controlplane.schemas.policy import PolicyConfig
from controlplane.security.redaction import redact_data
from controlplane.services.metrics_service import MetricsService
from controlplane.settings import PROJECT_ROOT
from controlplane.storage import policy_repository as policy_repository_module
from controlplane.storage.audit_repository import AuditRepository
from controlplane.storage.policy_repository import PolicyRepository

from .conftest import load_scenario


def test_four_policy_profiles_load(evaluator):
    policies = evaluator.policies.list()
    assert {policy.use_case for policy in policies} == {
        "engineering.development",
        "engineering.production",
        "support.informational",
        "support.transactional",
    }
    assert evaluator.policies.get_for_use_case("engineering.production").base_risk == RiskTier.HIGH
    detector_ids = set(evaluator.detectors.ids())
    for policy in policies:
        assert {
            detector_id
            for checks in policy.required_checks.values()
            for detector_id in checks
        } <= detector_ids
        assert {rule.detector for rule in policy.veto_rules} <= detector_ids
        for source_id in policy.source_ids:
            source = evaluator.sources.get(source_id)
            assert source is not None
            assert source["content_available"] is True


def test_policy_repository_caches_until_a_policy_file_changes(tmp_path, monkeypatch):
    policy_dir = tmp_path / "policies"
    shutil.copytree(PROJECT_ROOT / "policies", policy_dir)
    calls = 0
    original_safe_load = policy_repository_module.yaml.safe_load

    def counting_safe_load(stream):
        nonlocal calls
        calls += 1
        return original_safe_load(stream)

    monkeypatch.setattr(policy_repository_module.yaml, "safe_load", counting_safe_load)
    repository = PolicyRepository(policy_dir)

    repository.list()
    initial_calls = calls
    repository.list()
    assert calls == initial_calls

    changed = policy_dir / "engineering-development.yaml"
    changed.write_text(changed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    repository.list()
    assert calls > initial_calls


def test_policy_rejects_zero_historical_sample_threshold(evaluator):
    raw = evaluator.policies.get_for_use_case(
        "support.informational"
    ).model_dump(mode="json")
    raw["historical_boost_min_samples"] = 0

    with pytest.raises(ValidationError, match="must be at least 1"):
        PolicyConfig.model_validate(raw)


def test_policy_rejects_unknown_veto_status(evaluator):
    raw = evaluator.policies.get_for_use_case(
        "engineering.production"
    ).model_dump(mode="json")
    raw["veto_rules"][0]["statuses"] = ["BROKEN"]

    with pytest.raises(ValidationError):
        PolicyConfig.model_validate(raw)


def test_evaluation_is_audited_and_replayable(evaluator):
    result = asyncio.run(
        evaluator.evaluate(load_scenario("engineering/safe-file-edit.json"))
    )
    stored = evaluator.audit.get(result.evaluation_id)
    assert stored is not None
    assert stored["policy_version"] == "1.0"
    replay = asyncio.run(evaluator.replay(result.evaluation_id))
    assert replay.event_id.endswith("-replay")
    assert replay.decision == result.decision


def test_audit_restores_canonical_ids_when_redaction_matches_uuid_digits(tmp_path):
    evaluation_id = "a670e266-4572-4652-9345-96d11771c57d"
    event_id = "event-a670e266-4572-4652-9345"
    repository = AuditRepository(tmp_path / "canonical-ids.db")
    repository.save(
        evaluation_id=evaluation_id,
        event_id=event_id,
        fingerprint="support.transactional:candidate_response:unstructured_response",
        use_case="support.transactional",
        policy_id="support-transactional",
        policy_version="1.0",
        decision="ESCALATE",
        risk_tier="HIGH",
        event=redact_data({"event_id": event_id, "candidate": {"text": "Held"}}),
        result=redact_data(
            {
                "evaluation_id": evaluation_id,
                "event_id": event_id,
                "decision": "ESCALATE",
            }
        ),
    )

    stored = repository.get(evaluation_id)

    assert stored is not None
    assert stored["evaluation_id"] == evaluation_id
    assert stored["event"]["event_id"] == event_id
    assert stored["result"]["evaluation_id"] == evaluation_id
    assert stored["result"]["event_id"] == event_id


def test_history_can_raise_routing_signal(evaluator):
    event = load_scenario("support/contradicted-refund-answer.json")
    asyncio.run(evaluator.evaluate(event))
    asyncio.run(evaluator.evaluate(event))
    result = asyncio.run(evaluator.evaluate(event))
    assert "historical_risk" in result.risk_profile.signals


def test_history_does_not_cross_contaminate_unrelated_claims(evaluator):
    failing = load_scenario("support/no-evidence-answer.json")
    asyncio.run(evaluator.evaluate(failing))
    asyncio.run(evaluator.evaluate(failing))

    safe = asyncio.run(
        evaluator.evaluate(load_scenario("support/supported-faq.json"))
    )
    assert "historical_risk" not in safe.risk_profile.signals


def test_sensitive_audit_record_cannot_be_replayed_as_if_exact(evaluator):
    result = asyncio.run(
        evaluator.evaluate(load_scenario("support/pii-leak.json"))
    )
    stored = evaluator.audit.get(result.evaluation_id)
    assert "alice@example.com" not in str(stored)
    with pytest.raises(ValueError, match="sensitive values were redacted"):
        asyncio.run(evaluator.replay(result.evaluation_id))


def test_replay_can_select_another_policy_version(evaluator):
    event = load_scenario("support/supported-faq.json")
    event.policy_version = "1.0"
    original = asyncio.run(evaluator.evaluate(event))
    replay = asyncio.run(evaluator.replay(original.evaluation_id, "1.1"))
    assert original.policy_version == "1.0"
    assert replay.policy_version == "1.1"
    assert replay.decision == original.decision


def test_replay_defaults_to_original_policy_version(evaluator):
    event = load_scenario("support/supported-faq.json")
    event.policy_version = "1.0"
    original = asyncio.run(evaluator.evaluate(event))

    replay = asyncio.run(evaluator.replay(original.evaluation_id))

    assert original.policy_version == "1.0"
    assert replay.policy_version == "1.0"
    assert replay.policy_checksum == original.policy_checksum


def test_exact_replay_refuses_changed_same_version_policy(evaluator):
    event = load_scenario("support/supported-faq.json")
    original = asyncio.run(evaluator.evaluate(event))
    current = evaluator.policies.get_for_use_case(event.use_case)
    changed = current.model_copy(
        update={"latency_budget_ms": current.latency_budget_ms + 1}
    )
    evaluator.policies.get_for_use_case = lambda *args, **kwargs: changed

    with pytest.raises(ValueError, match="policy content has changed"):
        asyncio.run(evaluator.replay(original.evaluation_id))


def test_missing_trusted_action_context_is_rejected():
    with pytest.raises(ValidationError, match="trusted_context.authorized"):
        ControlEvent(
            session_id="missing-context",
            use_case="engineering.development",
            event_type="proposed_action",
            actor=Actor(id="agent", role="ai_agent"),
            candidate=Candidate(operation="file_edit"),
            trusted_context={},
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authorized", "false"),
        ("authorized", 1),
    ],
)
def test_engineering_trust_flags_require_real_booleans(field, value):
    with pytest.raises(ValidationError, match=f"trusted_context.{field} must be a boolean"):
        ControlEvent(
            session_id="typed-context",
            use_case="engineering.development",
            event_type="proposed_action",
            actor=Actor(id="agent", role="ai_agent"),
            candidate=Candidate(operation="file_edit"),
            trusted_context={"environment": "development", field: value},
        )


@pytest.mark.parametrize("field", ["approval_present", "rollback_available"])
def test_production_trust_flags_require_real_booleans(field):
    trusted_context = {
        "environment": "production",
        "authorized": True,
        "approval_present": True,
        "rollback_available": True,
    }
    trusted_context[field] = "false"
    with pytest.raises(ValidationError, match=f"trusted_context.{field} must be a boolean"):
        ControlEvent(
            session_id="typed-production-context",
            use_case="engineering.production",
            event_type="proposed_action",
            actor=Actor(id="agent", role="ai_agent"),
            candidate=Candidate(operation="deployment"),
            trusted_context=trusted_context,
        )


def test_engineering_use_case_and_environment_must_match():
    with pytest.raises(ValidationError, match="requires trusted_context.environment"):
        ControlEvent(
            session_id="mismatched-environment",
            use_case="engineering.production",
            event_type="proposed_action",
            actor=Actor(id="agent", role="ai_agent"),
            candidate=Candidate(operation="database_command"),
            trusted_context={
                "environment": "development",
                "authorized": True,
            },
        )


def test_support_trust_flags_require_real_booleans():
    with pytest.raises(ValidationError, match="identity_verified must be a boolean"):
        ControlEvent(
            session_id="typed-support-context",
            use_case="support.transactional",
            event_type="proposed_action",
            actor=Actor(id="support-ai", role="ai_agent"),
            candidate=Candidate(operation="account_cancellation"),
            trusted_context={"identity_verified": "false", "eligible": True},
        )


def test_policy_sources_require_a_non_empty_string_list():
    with pytest.raises(ValidationError, match="non-empty list of strings"):
        ControlEvent(
            session_id="bad-sources",
            use_case="support.informational",
            event_type="candidate_response",
            actor=Actor(id="support-ai", role="ai_agent"),
            candidate=Candidate(text="A response"),
            trusted_context={"policy_sources": "refunds-v2"},
        )


def test_database_parent_directory_is_created(tmp_path):
    nested_database = tmp_path / "audit" / "nested" / "controlplane.db"
    repository = AuditRepository(nested_database)

    assert repository.db_path == nested_database
    assert nested_database.exists()


def test_feedback_contributes_to_history_and_metrics(evaluator):
    result = asyncio.run(
        evaluator.evaluate(load_scenario("support/supported-faq.json"))
    )
    evaluator.audit.add_feedback(
        result.evaluation_id,
        "reviewer-1",
        "UNSAFE_ESCAPE",
        "The response should have been intercepted.",
    )
    total, intervention_rate = evaluator.audit.history_stats(
        load_scenario("support/supported-faq.json").fingerprint()
    )
    metrics = MetricsService(evaluator.audit).summary()
    assert total == 1
    assert intervention_rate == 1.0
    assert metrics["feedback_labels"] == {"UNSAFE_ESCAPE": 1}


def test_repeated_regeneration_history_promotes_similar_answers_to_escalation(
    evaluator,
):
    event = load_scenario("support/no-evidence-answer.json")

    first_three = [
        asyncio.run(evaluator.evaluate(event)).decision for _ in range(3)
    ]
    fourth = asyncio.run(evaluator.evaluate(event))
    historical = next(
        item
        for item in fourth.check_results
        if item.detector_id == "historical_signal"
    )

    assert first_three == [DecisionAction.REGENERATE] * 3
    assert fourth.risk_profile.tier == RiskTier.HIGH
    assert fourth.decision == DecisionAction.ESCALATE
    assert historical.status == CheckStatus.FAIL
    assert historical.sample_size == 3


def test_successful_edit_redact_does_not_count_as_adverse_history(evaluator):
    event = load_scenario("support/pii-leak.json")
    asyncio.run(evaluator.evaluate(event))
    total, adverse_rate = evaluator.audit.history_stats(event.fingerprint())
    assert total == 1
    assert adverse_rate == 0.0


class SlowDetector(Detector):
    detector_id = "engineering_action"

    async def evaluate(self, event, policy):
        await asyncio.sleep(0.05)
        return CheckResult(
            detector_id=self.detector_id,
            status=CheckStatus.PASS,
            reason="Slow test detector completed.",
        )


def test_latency_budget_applies_policy_fail_mode(evaluator):
    event = load_scenario("engineering/safe-file-edit.json")
    policy = evaluator.policies.get_for_use_case(event.use_case).model_copy(
        update={"latency_budget_ms": 1}
    )
    evaluator.policies.get_for_use_case = lambda *args, **kwargs: policy
    evaluator.detectors.detectors["engineering_action"] = SlowDetector()
    result = asyncio.run(evaluator.evaluate(event))
    assert result.stop_reason == StopReason.LATENCY_BUDGET_REACHED
    assert result.decision == DecisionAction.ESCALATE
