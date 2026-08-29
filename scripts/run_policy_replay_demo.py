from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controlplane.core.evaluator import ControlPlaneEvaluator  # noqa: E402
from controlplane.schemas.event import ControlEvent  # noqa: E402
from controlplane.settings import Settings  # noqa: E402


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="controlplane-replay-") as directory:
        evaluator = ControlPlaneEvaluator(
            Settings(db_path=Path(directory) / "replay.db")
        )
        path = PROJECT_ROOT / "scenarios" / "support" / "supported-faq.json"
        event = ControlEvent.model_validate_json(path.read_text(encoding="utf-8"))
        event.policy_version = "1.0"
        original = await evaluator.evaluate(event)
        replay = await evaluator.replay(original.evaluation_id, "1.1")
        print(
            json.dumps(
                {
                    "original": {
                        "policy_version": original.policy_version,
                        "decision": original.decision.value,
                    },
                    "replay": {
                        "policy_version": replay.policy_version,
                        "decision": replay.decision.value,
                    },
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
