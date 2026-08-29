from __future__ import annotations

import asyncio
import json
import shutil

import pytest
import yaml

from controlplane.core.evaluator import ControlPlaneEvaluator
from controlplane.detectors.judge import JudgeDetector
from controlplane.schemas.check_result import EvidenceState
from controlplane.schemas.decision import DecisionAction
from controlplane.schemas.event import Actor, Candidate, Claim, ControlEvent
from controlplane.settings import PROJECT_ROOT, Settings
from controlplane.storage.source_repository import (
    MISSING_SOURCE_MARKER,
    SourceRepository,
)

from .conftest import load_scenario


def test_stale_source_cannot_verify_a_claim(evaluator):
    event = load_scenario("support/supported-faq.json")
    event.candidate.text = "Customers may request a refund within thirty days."
    event.candidate.claims[0].value = 30
    event.trusted_context["policy_sources"] = ["refunds-v1"]

    result = asyncio.run(evaluator.evaluate(event))
    retrieval = next(
        item for item in result.check_results if item.detector_id == "retrieval_detector"
    )

    assert result.evidence_state == EvidenceState.NO_EVIDENCE
    assert result.decision == DecisionAction.REGENERATE
    assert retrieval.evidence_references[0]["source_status"] == "stale"
    assert retrieval.evidence_references[0]["usable"] is False
    assert retrieval.evidence_references[0]["used_for_decision"] is False


def test_no_evidence_records_every_attempted_source(evaluator):
    event = load_scenario("support/no-evidence-answer.json")
    result = asyncio.run(evaluator.evaluate(event))
    retrieval = next(
        item for item in result.check_results if item.detector_id == "retrieval_detector"
    )

    references = retrieval.evidence_references
    assert {item["source_id"] for item in references} == {
        "refunds-v2",
        "plan-changes",
    }
    assert all(item.get("source_version") for item in references)
    assert all(item.get("source_checksum") for item in references)
    assert all(item["used_for_decision"] is False for item in references)


def test_numeric_pii_is_redacted_from_audit_and_risk_profile(evaluator):
    event = ControlEvent(
        event_id="numeric-pii",
        session_id="numeric-pii-session",
        use_case="support.informational",
        event_type="candidate_response",
        actor=Actor(id="support-ai", role="ai_agent"),
        candidate=Candidate(
            text="Your request is ready.",
            arguments={"card_number": 4111111111111111},
        ),
        trusted_context={"policy_sources": ["privacy-policy"]},
    )

    result = asyncio.run(evaluator.evaluate(event))
    stored = evaluator.audit.get(result.evaluation_id)

    assert result.decision == DecisionAction.EDIT_REDACT
    assert "contains_pii" in result.risk_profile.signals
    assert "4111111111111111" not in json.dumps(stored)
    assert "[REDACTED]" in json.dumps(stored)


def test_sensitive_argument_key_uses_same_detection_and_risk_path(evaluator):
    event = ControlEvent(
        event_id="keyed-secret",
        session_id="keyed-secret-session",
        use_case="support.informational",
        event_type="candidate_response",
        actor=Actor(id="support-ai", role="ai_agent"),
        candidate=Candidate(
            text="Your request is ready.",
            arguments={"api_key": "demo-sensitive-value"},
        ),
        trusted_context={"policy_sources": ["privacy-policy"]},
    )

    result = asyncio.run(evaluator.evaluate(event))
    stored = evaluator.audit.get(result.evaluation_id)

    assert "contains_pii" in result.risk_profile.signals
    assert result.decision == DecisionAction.EDIT_REDACT
    assert "demo-sensitive-value" not in json.dumps(stored)


def test_external_judge_payload_is_minimized_and_redacted():
    event = load_scenario("support/overlap-pii-contradiction.json")
    event.candidate.arguments["card_number"] = 4111111111111111
    event.trusted_context["internal_access_token"] = "secret-token-value"

    payload = JudgeDetector._external_payload(
        event,
        [
            {
                "source_id": "refunds-v2",
                "claim_key": "refund_window_days",
                "claim_value": "alice@example.com",
                "expected_value": 14,
                "usable": True,
                "used_for_decision": True,
            }
        ],
    )
    serialized = json.dumps(payload)

    assert "alice@example.com" not in serialized
    assert "4111111111111111" not in serialized
    assert "secret-token-value" not in serialized
    assert "customer-88" not in serialized
    assert "identity_verified" not in serialized
    assert "refunds-v2" in serialized
    retrieved_evidence = payload["retrieved_evidence"]
    assert isinstance(retrieved_evidence, list)
    assert retrieved_evidence[0]["expected_value"] == 14
    assert "[REDACTED]" in serialized


def test_historical_sample_size_is_structured_not_parsed_from_reason(evaluator):
    event = load_scenario("support/no-evidence-answer.json")
    policy = evaluator.policies.get_for_use_case(event.use_case)
    historical = evaluator.detectors.get("historical_signal").result_from_stats(
        policy, 7, 0.5
    )
    historical.reason = "This wording deliberately contains no numeric sample prose."

    risk = evaluator.risk_profiler.profile(event, policy, historical)

    assert historical.sample_size == 7
    assert risk.historical_sample_size == 7


def test_false_positive_feedback_removes_intervention_from_history(evaluator):
    event = load_scenario("support/no-evidence-answer.json")
    result = asyncio.run(evaluator.evaluate(event))
    evaluator.audit.add_feedback(
        result.evaluation_id,
        "reviewer-1",
        "FALSE_POSITIVE",
        "The intervention was unnecessary.",
    )

    total, adverse_rate = evaluator.audit.history_stats(event.fingerprint())

    assert total == 1
    assert adverse_rate == 0.0


def test_replay_uses_frozen_history_and_does_not_train_history(evaluator):
    event = load_scenario("support/no-evidence-answer.json")
    original = asyncio.run(evaluator.evaluate(event))

    replays = [
        asyncio.run(evaluator.replay(original.evaluation_id)) for _ in range(4)
    ]
    total, adverse_rate = evaluator.audit.history_stats(event.fingerprint())

    assert {item.decision for item in replays} == {original.decision}
    assert {
        item.risk_profile.historical_sample_size for item in replays
    } == {original.risk_profile.historical_sample_size}
    assert total == 1
    assert adverse_rate == 1.0
    assert all(evaluator.audit.get(item.evaluation_id)["is_replay"] for item in replays)


def test_exact_replay_refuses_same_version_with_changed_source_content(evaluator):
    event = load_scenario("support/supported-faq.json")
    original = asyncio.run(evaluator.evaluate(event))
    evaluator.sources.sources["refunds-v2"]["facts"]["refund_window_days"] = 30

    with pytest.raises(ValueError, match="source 'refunds-v2' has changed"):
        asyncio.run(evaluator.replay(original.evaluation_id))


def test_engineering_sensitive_argument_key_is_blocked(evaluator):
    event = ControlEvent(
        session_id="engineering-sensitive-key",
        use_case="engineering.development",
        event_type="proposed_action",
        actor=Actor(id="coding-agent", role="ai_agent"),
        candidate=Candidate(
            tool="edit",
            operation="file_edit",
            arguments={"api_key": "plain-demo-sensitive-value"},
        ),
        trusted_context={"environment": "development", "authorized": True},
    )

    result = asyncio.run(evaluator.evaluate(event))

    assert "exposed_secret" in result.risk_profile.signals
    assert result.decision == DecisionAction.BLOCK
    stored = evaluator.audit.get(result.evaluation_id)
    assert "plain-demo-sensitive-value" not in json.dumps(stored)


def test_destructive_command_in_operation_field_is_blocked(evaluator):
    event = ControlEvent(
        session_id="operation-command",
        use_case="engineering.production",
        event_type="proposed_action",
        actor=Actor(id="coding-agent", role="ai_agent"),
        candidate=Candidate(tool="shell", operation="DROP TABLE customers"),
        trusted_context={
            "environment": "production",
            "authorized": True,
            "approval_present": True,
            "rollback_available": True,
        },
    )

    result = asyncio.run(evaluator.evaluate(event))

    assert "destructive_operation" in result.risk_profile.signals
    assert result.decision == DecisionAction.BLOCK


def test_unknown_production_mutation_requires_rollback(evaluator):
    event = ControlEvent(
        session_id="operation-mutation",
        use_case="engineering.production",
        event_type="proposed_action",
        actor=Actor(id="coding-agent", role="ai_agent"),
        candidate=Candidate(
            tool="database",
            operation="ALTER TABLE accounts ADD COLUMN region TEXT",
        ),
        trusted_context={
            "environment": "production",
            "authorized": True,
            "approval_present": True,
            "rollback_available": False,
        },
    )

    result = asyncio.run(evaluator.evaluate(event))

    assert "missing_rollback" in result.risk_profile.signals
    assert result.decision == DecisionAction.BLOCK


def test_source_registry_changes_reload_without_process_restart(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    shutil.copytree(PROJECT_ROOT / "knowledge", knowledge_dir)
    registry_path = knowledge_dir / "source_registry.yaml"
    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "reload.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=registry_path,
        )
    )
    source = evaluator.sources.get("refunds-v2")
    assert source is not None
    assert source["facts"]["refund_window_days"] == 7

    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    raw["sources"]["refunds-v2"]["facts"]["refund_window_days"] = 30
    registry_path.write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )

    source = evaluator.sources.get("refunds-v2")
    assert source is not None
    assert source["facts"]["refund_window_days"] == 30


def test_source_registry_rejects_files_outside_knowledge_directory(tmp_path):
    registry_path = tmp_path / "source_registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {
                "sources": {
                    "escaped-source": {
                        "file": "../outside.md",
                        "authority": 1.0,
                        "status": "current",
                        "version": "1.0",
                        "facts": {"example": True},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="inside the knowledge directory"):
        SourceRepository(registry_path)


@pytest.mark.parametrize("authority", [-0.1, 1.1, "high", True])
def test_source_registry_rejects_invalid_authority(tmp_path, authority):
    registry_path = tmp_path / "source_registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {
                "sources": {
                    "invalid-authority": {
                        "file": "policy.md",
                        "authority": authority,
                        "status": "current",
                        "version": "1.0",
                        "facts": {"example": True},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="between 0 and 1"):
        SourceRepository(registry_path)


def test_exact_replay_refuses_when_previously_missing_source_appears(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    shutil.copytree(PROJECT_ROOT / "knowledge", knowledge_dir)
    registry_path = knowledge_dir / "source_registry.yaml"
    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "missing-source.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=registry_path,
        )
    )
    event = ControlEvent(
        session_id="missing-source",
        use_case="support.informational",
        event_type="candidate_response",
        actor=Actor(id="support-ai", role="ai_agent"),
        candidate=Candidate(
            text="The future policy is enabled.",
            claims=[Claim(key="future_policy_enabled", value=True)],
        ),
        trusted_context={"policy_sources": ["future-policy"]},
    )
    original = asyncio.run(evaluator.evaluate(event))
    assert original.evidence_state == EvidenceState.NO_EVIDENCE
    assert original.source_checksums == {
        "future-policy": MISSING_SOURCE_MARKER
    }

    (knowledge_dir / "future-policy.md").write_text(
        "# Future policy\n\nThe policy is enabled.\n", encoding="utf-8"
    )
    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    raw["sources"]["future-policy"] = {
        "file": "future-policy.md",
        "authority": 1.0,
        "status": "current",
        "version": "1.0",
        "facts": {"future_policy_enabled": True},
    }
    registry_path.write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="source 'future-policy' has changed"):
        asyncio.run(evaluator.replay(original.evaluation_id))


def test_missing_source_document_is_not_treated_as_usable_evidence(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    shutil.copytree(PROJECT_ROOT / "knowledge", knowledge_dir)
    registry_path = knowledge_dir / "source_registry.yaml"
    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    raw["sources"]["missing-document"] = {
        "file": "does-not-exist.md",
        "authority": 1.0,
        "status": "current",
        "version": "1.0",
        "facts": {"document_backed_claim": True},
    }
    registry_path.write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "missing-document.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=registry_path,
        )
    )
    event = ControlEvent(
        session_id="missing-document",
        use_case="support.informational",
        event_type="candidate_response",
        actor=Actor(id="support-ai", role="ai_agent"),
        candidate=Candidate(
            text="The document-backed claim is true.",
            claims=[Claim(key="document_backed_claim", value=True)],
        ),
        trusted_context={"policy_sources": ["missing-document"]},
    )

    result = asyncio.run(evaluator.evaluate(event))
    retrieval = next(
        item for item in result.check_results if item.detector_id == "retrieval_detector"
    )

    assert result.evidence_state == EvidenceState.NO_EVIDENCE
    assert result.decision == DecisionAction.REGENERATE
    assert retrieval.evidence_references[0]["usable"] is False
    assert "unavailable" in retrieval.evidence_references[0]["reason"]


def test_claimless_authorized_support_action_fails_closed(evaluator):
    event = ControlEvent(
        session_id="claimless-support-action",
        use_case="support.transactional",
        event_type="proposed_action",
        actor=Actor(id="support-ai", role="ai_agent"),
        candidate=Candidate(
            tool="account_service",
            operation="account_cancellation",
            arguments={"customer_id": "customer-1"},
        ),
        trusted_context={
            "identity_verified": True,
            "eligible": True,
            "approval_present": True,
            "policy_sources": ["account-cancellation"],
        },
    )

    result = asyncio.run(evaluator.evaluate(event))

    assert result.authorization_state.value == "AUTHORIZED"
    assert result.evidence_state == EvidenceState.NO_EVIDENCE
    assert result.decision == DecisionAction.ESCALATE


def test_evidence_backed_support_action_requires_trusted_approval(evaluator):
    event = ControlEvent(
        session_id="unapproved-support-action",
        use_case="support.transactional",
        event_type="proposed_action",
        actor=Actor(id="support-ai", role="ai_agent"),
        candidate=Candidate(
            tool="account_service",
            operation="account_cancellation",
            claims=[
                Claim(
                    key="cancellation_requires_verified_identity",
                    value=True,
                )
            ],
        ),
        trusted_context={
            "identity_verified": True,
            "eligible": True,
            "approval_present": False,
            "policy_sources": ["account-cancellation"],
        },
    )

    result = asyncio.run(evaluator.evaluate(event))

    assert result.authorization_state.value == "APPROVAL_REQUIRED"
    assert result.decision == DecisionAction.ESCALATE


def test_evidence_backed_approved_support_action_can_pass(evaluator):
    event = ControlEvent(
        session_id="approved-support-action",
        use_case="support.transactional",
        event_type="proposed_action",
        actor=Actor(id="support-ai", role="ai_agent"),
        candidate=Candidate(
            tool="account_service",
            operation="account_cancellation",
            claims=[
                Claim(
                    key="cancellation_requires_verified_identity",
                    value=True,
                )
            ],
        ),
        trusted_context={
            "identity_verified": True,
            "eligible": True,
            "approval_present": True,
            "policy_sources": ["account-cancellation"],
        },
    )

    result = asyncio.run(evaluator.evaluate(event))

    assert result.authorization_state.value == "AUTHORIZED"
    assert result.evidence_state == EvidenceState.VERIFIED
    assert result.decision == DecisionAction.ALLOW
