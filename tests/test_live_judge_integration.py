from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from controlplane.core.evaluator import ControlPlaneEvaluator
from controlplane.schemas.check_result import EvidenceState
from controlplane.schemas.decision import DecisionAction
from controlplane.settings import PROJECT_ROOT, Settings

from .conftest import load_scenario

pytestmark = pytest.mark.live


@pytest.mark.parametrize(
    "scenario",
    [
        "support/judge-unavailable-escalation.json",
        "support/judge-mixed-evidence-refund.json",
        "support/judge-plan-change-promise.json",
    ],
)
def test_configured_external_judge_is_reached_and_fails_closed(
    tmp_path: Path, scenario: str
):
    """Opt-in network test; standard test runs never send data to a provider."""
    if os.getenv("CONTROLPLANE_RUN_LIVE_JUDGE") != "1":
        pytest.skip("Set CONTROLPLANE_RUN_LIVE_JUDGE=1 to call the configured judge.")

    required = {"GROQ_API_KEY": os.getenv("GROQ_API_KEY", "")}
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.fail("Missing live-judge environment variables: " + ", ".join(missing))

    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "live-judge.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
            judge_api_key=required["GROQ_API_KEY"],
        )
    )
    result = asyncio.run(
        evaluator.evaluate(load_scenario(scenario))
    )
    judge = next(
        item for item in result.check_results if item.detector_id == "judge_detector"
    )

    assert judge.model_calls == 1
    assert "failed safely" not in judge.reason.lower()
    assert judge.evidence_state in {
        EvidenceState.NO_EVIDENCE,
        EvidenceState.UNCERTAIN,
    }
    assert result.decision == DecisionAction.ESCALATE
