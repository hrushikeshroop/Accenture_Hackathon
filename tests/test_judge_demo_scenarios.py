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
    ("scenario", "expected_risk"),
    [
        ("support/judge-mixed-evidence-refund.json", RiskTier.HIGH),
        ("support/judge-plan-change-promise.json", RiskTier.CRITICAL),
    ],
)
def test_demo_scenarios_reach_configured_judge(
    tmp_path: Path, scenario: str, expected_risk: RiskTier
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
    assert result.decision == DecisionAction.ESCALATE
    assert result.stop_reason == StopReason.HUMAN_REVIEW_REQUIRED
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
    references = {item["claim_key"]: item for item in judge.evidence_references}

    assert references["refund_window_days"]["evidence_state"] == "VERIFIED"
    assert references["refund_window_days"]["used_for_decision"] is True
    assert references["refund_settlement_hours"]["usable"] is False
    assert references["refund_settlement_hours"]["used_for_decision"] is False


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
