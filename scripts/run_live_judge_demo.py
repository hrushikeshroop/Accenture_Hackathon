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

from controlplane.core.evaluator import ControlPlaneEvaluator  # noqa: E402
from controlplane.schemas.event import ControlEvent  # noqa: E402
from controlplane.settings import Settings  # noqa: E402

REQUIRED_ENVIRONMENT = ("GROQ_API_KEY",)

LIVE_SCENARIOS = (
    "judge-unavailable-escalation.json",
    "judge-mixed-evidence-refund.json",
    "judge-plan-change-promise.json",
)


def main() -> None:
    missing = [name for name in REQUIRED_ENVIRONMENT if not os.getenv(name)]
    if missing:
        raise SystemExit(
            "Live judge is not configured. Missing environment variables: "
            + ", ".join(missing)
        )

    with tempfile.TemporaryDirectory(prefix="controlplane-live-judge-") as temp_dir:
        evaluator = ControlPlaneEvaluator(
            Settings(
                db_path=Path(temp_dir) / "live-judge.db",
                policy_dir=PROJECT_ROOT / "policies",
                source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
                judge_api_key=os.environ["GROQ_API_KEY"],
            )
        )
        summaries = []
        for scenario_name in LIVE_SCENARIOS:
            event_path = PROJECT_ROOT / "scenarios" / "support" / scenario_name
            event = ControlEvent.model_validate_json(
                event_path.read_text(encoding="utf-8")
            )
            result = asyncio.run(
                evaluator.evaluate(event, counts_toward_history=False)
            )
            policy = evaluator.policies.get_for_use_case(event.use_case)
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
            summaries.append(
                {
                    "scenario": scenario_name,
                    "external_call_succeeded": call_succeeded,
                    "judge_status": (
                        judge.status.value if judge is not None else "NOT_COMPLETED"
                    ),
                    "judge_evidence_state": (
                        judge.evidence_state.value
                        if judge is not None
                        else "NOT_COMPLETED"
                    ),
                    "judge_reason": (
                        judge.reason
                        if judge is not None
                        else "The judge did not complete within the evaluation route."
                    ),
                    "judge_latency_ms": (
                        round(judge.latency_ms, 2) if judge is not None else None
                    ),
                    "final_decision": result.decision.value,
                    "stop_reason": result.stop_reason.value,
                    "latency_ms": round(result.latency_ms, 2),
                    "policy_latency_budget_ms": policy.latency_budget_ms,
                }
            )

    output = {
        "provider_endpoint": evaluator.settings.judge_url,
        "model": evaluator.settings.judge_model,
        "api_key_loaded": True,
        "judge_http_timeout_seconds": evaluator.settings.judge_timeout_seconds,
        "calls": summaries,
    }
    print(json.dumps(output, indent=2, default=str))
    if not all(item["external_call_succeeded"] for item in summaries):
        raise SystemExit("The live judge did not complete successfully.")


if __name__ == "__main__":
    main()
