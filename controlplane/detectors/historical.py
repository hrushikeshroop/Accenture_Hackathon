from __future__ import annotations

from time import perf_counter

from controlplane.schemas.check_result import CheckResult, CheckStatus
from controlplane.schemas.event import ControlEvent
from controlplane.schemas.policy import PolicyConfig
from controlplane.storage.audit_repository import AuditRepository

from .base import Detector


class HistoricalSignalDetector(Detector):
    detector_id = "historical_signal"
    tier = 4

    def __init__(self, audit: AuditRepository):
        self.audit = audit

    async def evaluate(self, event: ControlEvent, policy: PolicyConfig) -> CheckResult:
        started = perf_counter()
        total, failure_rate = self.audit.history_stats(event.fingerprint())
        return self.result_from_stats(
            policy,
            total,
            failure_rate,
            latency_ms=(perf_counter() - started) * 1000,
        )

    @staticmethod
    def result_from_stats(
        policy: PolicyConfig,
        total: int,
        failure_rate: float,
        *,
        latency_ms: float = 0,
    ) -> CheckResult:
        risky = (
            total >= policy.historical_boost_min_samples
            and failure_rate >= policy.historical_boost_failure_rate
        )
        return CheckResult(
            detector_id=HistoricalSignalDetector.detector_id,
            status=CheckStatus.FAIL if risky else CheckStatus.PASS,
            severity="HIGH" if risky else "LOW",
            reason=(
                f"Similar events have a {failure_rate:.0%} adverse-outcome rate across {total} samples."
                if risky
                else f"No policy-significant historical risk was found across {total} samples."
            ),
            confidence=failure_rate if total else None,
            signals=["historical_risk"] if risky else [],
            sample_size=total,
            latency_ms=latency_ms,
            estimated_cost_units=1,
        )
