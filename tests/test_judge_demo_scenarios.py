from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from controlplane.core.evaluator import ControlPlaneEvaluator
from controlplane.schemas.check_result import CheckStatus, EvidenceState
from controlplane.schemas.decision import DecisionAction, RiskTier, StopReason
from controlplane.settings import PROJECT_ROOT, Settings

from .conftest import load_scenario


@pytest.mark.parametrize(
    ("scenario", "expected_risk", "expected_decision", "expected_stop"),
    [
        (
            "support/judge-mixed-evidence-refund.json",
            RiskTier.MEDIUM,
            DecisionAction.REGENERATE,
            StopReason.RESOLVED,
        ),
        (
            "support/judge-plan-change-promise.json",
            RiskTier.CRITICAL,
            DecisionAction.ESCALATE,
            StopReason.HUMAN_REVIEW_REQUIRED,
        ),
    ],
)
def test_demo_scenarios_reach_configured_judge(
    tmp_path: Path,
    scenario: str,
    expected_risk: RiskTier,
    expected_decision: DecisionAction,
    expected_stop: StopReason,
):
    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "judge-demo.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
            judge_url="mock://local",
            judge_api_key="",
            judge_model="simulated-judge",
        )
    )

    result = asyncio.run(evaluator.evaluate(load_scenario(scenario)))
    checks = {item.detector_id: item for item in result.check_results}

    assert result.risk_profile.tier == expected_risk
    assert result.decision == expected_decision
    assert result.stop_reason == expected_stop
    assert "judge_detector" in result.checks_selected
    assert "judge_detector" not in result.checks_skipped
    assert result.model_calls == 1
    assert checks["retrieval_detector"].evidence_state == EvidenceState.NO_EVIDENCE
    assert checks["judge_detector"].evidence_state == EvidenceState.NO_EVIDENCE
    assert checks["judge_detector"].model_calls == 1
    assert checks["judge_detector"].evidence_references


def test_mixed_evidence_fixture_sends_both_claim_traces_to_judge(tmp_path: Path):
    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "mixed-evidence.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
            judge_url="mock://local",
            judge_model="simulated-judge",
        )
    )

    result = asyncio.run(
        evaluator.evaluate(load_scenario("support/judge-mixed-evidence-refund.json"))
    )
    judge = next(
        item for item in result.check_results if item.detector_id == "judge_detector"
    )
    refund_window = [
        item
        for item in judge.evidence_references
        if item["claim_key"] == "refund_window_days"
    ]
    settlement = [
        item
        for item in judge.evidence_references
        if item["claim_key"] == "refund_settlement_hours"
    ]

    assert any(
        item["evidence_state"] == "VERIFIED"
        and item["used_for_decision"] is True
        for item in refund_window
    )
    assert settlement
    assert all(item["usable"] is False for item in settlement)
    assert all(item["used_for_decision"] is False for item in settlement)


def test_medium_risk_uncertain_judge_result_regenerates_without_human_review(
    tmp_path: Path,
):
    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "medium-uncertain.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
            judge_url="mock://local",
            judge_model="simulated-judge",
        )
    )
    event = load_scenario("support/judge-mixed-evidence-refund.json")
    event.metadata["mock_judge_state"] = "UNCERTAIN"

    result = asyncio.run(evaluator.evaluate(event))

    assert result.risk_profile.tier == RiskTier.MEDIUM
    assert result.evidence_state == EvidenceState.UNCERTAIN
    assert result.decision == DecisionAction.REGENERATE
    assert result.stop_reason == StopReason.RESOLVED
    assert result.model_calls == 1


def test_authorized_plan_change_reaches_judge_instead_of_entitlement_veto(
    tmp_path: Path,
):
    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "plan-change.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
            judge_url="mock://local",
            judge_model="simulated-judge",
        )
    )

    result = asyncio.run(
        evaluator.evaluate(load_scenario("support/judge-plan-change-promise.json"))
    )
    checks = {item.detector_id: item for item in result.check_results}

    assert checks["entitlement_detector"].status == CheckStatus.PASS
    assert checks["judge_detector"].model_calls == 1
    assert result.decision == DecisionAction.ESCALATE
