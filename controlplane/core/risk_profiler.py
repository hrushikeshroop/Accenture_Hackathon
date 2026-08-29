from __future__ import annotations

import json
from typing import ClassVar

from controlplane.detectors.engineering import (
    candidate_blob,
    contains_destructive_operation,
    contains_exposed_secret,
    requires_rollback,
)
from controlplane.schemas.check_result import CheckResult, CheckStatus
from controlplane.schemas.decision import RiskProfile, RiskTier
from controlplane.schemas.event import ControlEvent
from controlplane.schemas.policy import PolicyConfig
from controlplane.security.redaction import PATTERNS, contains_sensitive_key

RISK_RANK = {
    RiskTier.LOW: 0,
    RiskTier.MEDIUM: 1,
    RiskTier.HIGH: 2,
    RiskTier.CRITICAL: 3,
}


def max_risk(*tiers: RiskTier) -> RiskTier:
    return max(tiers, key=lambda tier: RISK_RANK[tier])


class RiskProfiler:
    HIGH_IMPACT_ACTIONS: ClassVar[set[str]] = {
        "account_cancellation",
        "refund",
        "plan_change",
        "schema_migration",
        "database_command",
        "deployment",
    }

    def profile(
        self,
        event: ControlEvent,
        policy: PolicyConfig,
        historical_result: CheckResult,
    ) -> RiskProfile:
        signals = self._signals(event)
        if historical_result.status == CheckStatus.FAIL:
            signals.add("historical_risk")

        tier = policy.base_risk
        reasons = [f"Policy base risk is {policy.base_risk.value}."]
        for signal in sorted(signals):
            mapped = policy.signal_risks.get(signal)
            if mapped is not None:
                old_tier = tier
                tier = max_risk(tier, mapped)
                if tier != old_tier or mapped == tier:
                    reasons.append(f"Signal '{signal}' maps to {mapped.value} risk.")

        return RiskProfile(
            tier=tier,
            signals=sorted(signals),
            reasons=reasons,
            historical_failure_rate=historical_result.confidence or 0,
            historical_sample_size=historical_result.sample_size,
        )

    def _signals(self, event: ControlEvent) -> set[str]:
        signals: set[str] = set()
        context = event.trusted_context
        blob = candidate_blob(event)
        operation = event.candidate.operation or ""

        if context.get("environment") == "production":
            signals.add("production_environment")
        if context.get("branch") in {"main", "master"} and event.event_type == "proposed_action":
            signals.add("protected_branch")
        if contains_destructive_operation(blob):
            signals.add("destructive_operation")
        if contains_exposed_secret(event):
            signals.add("exposed_secret")
        if context.get("authorized") is False:
            signals.add("unauthorized_actor")
        if (
            context.get("environment") == "production"
            and event.event_type == "proposed_action"
            and not context.get("approval_present", False)
        ):
            signals.add("missing_approval")
        if (
            context.get("environment") == "production"
            and requires_rollback(event)
            and not context.get("rollback_available", False)
        ):
            signals.add("missing_rollback")

        if event.use_case.startswith("support"):
            if event.event_type == "proposed_action" or event.use_case.endswith("transactional"):
                signals.add("transactional_event")
            if operation in self.HIGH_IMPACT_ACTIONS:
                signals.add("high_impact_action")
            if event.event_type == "proposed_action" and not context.get(
                "identity_verified", False
            ):
                signals.add("identity_unverified")
            if event.event_type == "proposed_action" and not context.get(
                "approval_present", False
            ):
                signals.add("missing_approval")
            if not (context.get("policy_sources")):
                signals.add("missing_policy_sources")
            candidate_payload = json.dumps(
                event.candidate.model_dump(mode="json"), default=str
            )
            if any(
                pattern.search(candidate_payload) for pattern in PATTERNS
            ) or contains_sensitive_key(event.candidate.model_dump(mode="json")):
                signals.add("contains_pii")
        return signals
