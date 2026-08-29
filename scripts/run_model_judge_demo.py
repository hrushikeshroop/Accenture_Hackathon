from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controlplane.core.evaluator import ControlPlaneEvaluator
from controlplane.schemas.event import ControlEvent
from controlplane.settings import Settings


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="controlplane-judge-") as directory:
        evaluator = ControlPlaneEvaluator(
            Settings(
                db_path=Path(directory) / "judge.db",
                judge_url="mock://local",
                judge_model="simulated-secondary-judge",
            )
        )
        path = PROJECT_ROOT / "scenarios" / "support" / "judge-unavailable-escalation.json"
        event = ControlEvent.model_validate_json(path.read_text(encoding="utf-8"))
        event.metadata["mock_judge_state"] = "UNCERTAIN"
        result = await evaluator.evaluate(event)
        judge = next(
            item for item in result.check_results if item.detector_id == "judge_detector"
        )
        print(
            json.dumps(
                {
                    "simulation_only": True,
                    "decision": result.decision.value,
                    "model_calls": result.model_calls,
                    "judge_status": judge.status.value,
                    "judge_reason": judge.reason,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
