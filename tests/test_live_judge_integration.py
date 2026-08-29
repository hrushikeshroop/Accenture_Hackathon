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


def test_configured_external_judge_is_reached_and_fails_closed(tmp_path: Path):
    """Opt-in network test; standard test runs never send data to a provider."""
    if os.getenv("CONTROLPLANE_RUN_LIVE_JUDGE") != "1":
        pytest.skip("Set CONTROLPLANE_RUN_LIVE_JUDGE=1 to call the configured judge.")

    required = {
        name: os.getenv(name, "")
        for name in (
            "CONTROLPLANE_JUDGE_URL",
            "CONTROLPLANE_JUDGE_API_KEY",
            "CONTROLPLANE_JUDGE_MODEL",
        )
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.fail("Missing live-judge environment variables: " + ", ".join(missing))

    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "live-judge.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
            judge_url=required["CONTROLPLANE_JUDGE_URL"],
            judge_api_key=required["CONTROLPLANE_JUDGE_API_KEY"],
            judge_model=required["CONTROLPLANE_JUDGE_MODEL"],
        )
    )
    result = asyncio.run(
        evaluator.evaluate(load_scenario("support/judge-unavailable-escalation.json"))
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
