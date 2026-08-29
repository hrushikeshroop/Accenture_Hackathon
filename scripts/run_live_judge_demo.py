from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controlplane.core.evaluator import ControlPlaneEvaluator
from controlplane.schemas.event import ControlEvent
from controlplane.settings import Settings

REQUIRED_ENVIRONMENT = (
    "CONTROLPLANE_JUDGE_URL",
    "CONTROLPLANE_JUDGE_API_KEY",
    "CONTROLPLANE_JUDGE_MODEL",
)


def main() -> None:
    missing = [name for name in REQUIRED_ENVIRONMENT if not os.getenv(name)]
    if missing:
        raise SystemExit(
            "Live judge is not configured. Missing environment variables: "
            + ", ".join(missing)
        )

    event_path = (
        PROJECT_ROOT
        / "scenarios"
        / "support"
        / "judge-unavailable-escalation.json"
    )
    event = ControlEvent.model_validate_json(event_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="controlplane-live-judge-") as temp_dir:
        evaluator = ControlPlaneEvaluator(
            Settings(
                db_path=Path(temp_dir) / "live-judge.db",
                policy_dir=PROJECT_ROOT / "policies",
                source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
                judge_url=os.environ["CONTROLPLANE_JUDGE_URL"],
                judge_api_key=os.environ["CONTROLPLANE_JUDGE_API_KEY"],
                judge_model=os.environ["CONTROLPLANE_JUDGE_MODEL"],
            )
        )
        result = asyncio.run(evaluator.evaluate(event))

    judge = next(
        (
            item
            for item in result.check_results
            if item.detector_id == "judge_detector"
        ),
        None,
    )
    call_recorded = judge is not None and judge.model_calls == 1
    call_succeeded = (
        call_recorded and "failed safely" not in judge.reason.lower()
        if judge is not None
        else False
    )
    summary = {
        "provider_endpoint": os.environ["CONTROLPLANE_JUDGE_URL"],
        "model": os.environ["CONTROLPLANE_JUDGE_MODEL"],
        "api_key_loaded": True,
        "external_call_recorded": call_recorded,
        "external_call_succeeded": call_succeeded,
        "judge_status": judge.status.value if judge is not None else "NOT_COMPLETED",
        "judge_evidence_state": (
            judge.evidence_state.value if judge is not None else "NOT_COMPLETED"
        ),
        "judge_reason": (
            judge.reason
            if judge is not None
            else "The judge did not complete within the policy evaluation route."
        ),
        "final_decision": result.decision.value,
        "stop_reason": result.stop_reason.value,
        "latency_ms": round(result.latency_ms, 2),
    }
    print(json.dumps(summary, indent=2, default=str))
    if not summary["external_call_succeeded"]:
        raise SystemExit("The live judge did not complete successfully.")


if __name__ == "__main__":
    main()
