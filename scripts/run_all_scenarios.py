from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controlplane.core.evaluator import ControlPlaneEvaluator  # noqa: E402
from controlplane.schemas.event import ControlEvent  # noqa: E402
from controlplane.settings import Settings  # noqa: E402


async def main(persistent_history: bool = False) -> None:
    if persistent_history:
        evaluator = ControlPlaneEvaluator()
        temporary = None
    else:
        temporary = tempfile.TemporaryDirectory(prefix="controlplane-scenarios-")
        evaluator = ControlPlaneEvaluator(
            Settings(
                db_path=Path(temporary.name) / "scenarios.db",
                judge_api_key="",
            )
        )
    paths = sorted((PROJECT_ROOT / "scenarios").glob("**/*.json"))
    print(f"{'SCENARIO':38} {'RISK':10} {'DECISION':15} STOP")
    print("-" * 90)
    for path in paths:
        event = ControlEvent.model_validate_json(path.read_text(encoding="utf-8"))
        result = await evaluator.evaluate(event)
        print(
            f"{path.stem:38} {result.risk_profile.tier.value:10} "
            f"{result.decision.value:15} {result.stop_reason.value}"
        )
    if temporary is not None:
        temporary.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--persistent-history",
        action="store_true",
        help="Use controlplane.db so prior decisions can adapt future routing.",
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.persistent_history))
