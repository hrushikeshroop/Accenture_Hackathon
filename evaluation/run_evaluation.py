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
    with tempfile.TemporaryDirectory(prefix="controlplane-eval-") as directory:
        evaluator = ControlPlaneEvaluator(
            Settings(db_path=Path(directory) / "evaluation.db")
        )
        report = await evaluate_cases(evaluator)

    output = PROJECT_ROOT / "evaluation" / "results" / "latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))


async def evaluate_cases(evaluator: ControlPlaneEvaluator) -> dict:
    cases: list[dict] = []
    for path in sorted((PROJECT_ROOT / "evaluation").glob("*-cases.jsonl")):
        cases.extend(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    rows: list[dict] = []
    for case in cases:
        scenario = PROJECT_ROOT / case["scenario"]
        event = ControlEvent.model_validate_json(scenario.read_text(encoding="utf-8"))
        result = await evaluator.evaluate(event)
        rows.append(
            {
                **case,
                "actual_decision": result.decision.value,
                "risk": result.risk_profile.tier.value,
                "passed": result.decision.value == case["expected_decision"],
                "latency_ms": result.latency_ms,
                "cost_units": result.estimated_cost_units,
                "model_calls": result.model_calls,
                "checks_executed": result.checks_executed,
            }
        )

    total = len(rows)
    passed = sum(row["passed"] for row in rows)
    safe = [row for row in rows if not row["unsafe"]]
    unsafe = [row for row in rows if row["unsafe"]]
    false_blocks = sum(
        row["actual_decision"] != "ALLOW" for row in safe
    )
    unsafe_escapes = sum(
        row["actual_decision"] == "ALLOW" for row in unsafe
    )
    report = {
        "total": total,
        "passed": passed,
        "scenario_accuracy": passed / total if total else 0,
        "false_block_rate": false_blocks / len(safe) if safe else 0,
        "unsafe_escape_rate": unsafe_escapes / len(unsafe) if unsafe else 0,
        "average_latency_ms": sum(row["latency_ms"] for row in rows) / total if total else 0,
        "total_model_calls": sum(row["model_calls"] for row in rows),
        "average_checks_executed": (
            sum(row["checks_executed"] for row in rows) / total if total else 0
        ),
        "history_mode": "isolated",
        "rows": rows,
    }
    return report


if __name__ == "__main__":
    asyncio.run(main())
