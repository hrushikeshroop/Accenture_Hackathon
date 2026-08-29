from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from controlplane.storage.audit_repository import AuditRepository


class MetricsService:
    def __init__(self, audit: AuditRepository):
        self.audit = audit

    def summary(self) -> dict[str, Any]:
        records = self.audit.list(limit=10000)
        decisions = Counter(record["decision"] for record in records)
        by_use_case: dict[str, Counter[str]] = defaultdict(Counter)
        latencies: list[float] = []
        cost_units: list[float] = []
        model_calls: list[int] = []
        check_counts: list[int] = []
        stop_reasons: Counter[str] = Counter()
        for record in records:
            by_use_case[record["use_case"]][record["decision"]] += 1
            latencies.append(float(record["result"]["latency_ms"]))
            cost_units.append(float(record["result"]["estimated_cost_units"]))
            model_calls.append(int(record["result"].get("model_calls", 0)))
            check_counts.append(
                int(
                    record["result"].get(
                        "checks_executed", len(record["result"].get("check_results", []))
                    )
                )
            )
            stop_reasons[record["result"]["stop_reason"]] += 1
        feedback = self.audit.list_feedback(limit=10000)
        feedback_labels = Counter(item["label"] for item in feedback)
        return {
            "total_evaluations": len(records),
            "decisions": dict(decisions),
            "by_use_case": {key: dict(value) for key, value in by_use_case.items()},
            "average_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "average_cost_units": sum(cost_units) / len(cost_units) if cost_units else 0,
            "total_model_calls": sum(model_calls),
            "average_checks_executed": (
                sum(check_counts) / len(check_counts) if check_counts else 0
            ),
            "stop_reasons": dict(stop_reasons),
            "feedback_count": len(feedback),
            "feedback_labels": dict(feedback_labels),
        }
