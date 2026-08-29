from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controlplane.core.evaluator import ControlPlaneEvaluator
from controlplane.schemas.event import ControlEvent


async def run(path: Path) -> None:
    event = ControlEvent.model_validate_json(path.read_text(encoding="utf-8"))
    result = await ControlPlaneEvaluator().evaluate(event)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path)
    arguments = parser.parse_args()
    asyncio.run(run(arguments.scenario))
