from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field

from controlplane.detectors.registry import DetectorRegistry
from controlplane.schemas.decision import RiskProfile
from controlplane.schemas.policy import PolicyConfig


class VerificationPlan(BaseModel):
    selected: list[str]
    groups: list[list[str]]
    reasons: list[str] = Field(default_factory=list)


class VerificationPlanner:
    def __init__(self, registry: DetectorRegistry):
        self.registry = registry

    def plan(self, risk: RiskProfile, policy: PolicyConfig) -> VerificationPlan:
        selected = list(dict.fromkeys(policy.required_checks[risk.tier]))
        grouped: dict[int, list[str]] = defaultdict(list)
        for detector_id in selected:
            grouped[self.registry.get(detector_id).tier].append(detector_id)
        groups = [grouped[tier] for tier in sorted(grouped)]
        return VerificationPlan(
            selected=selected,
            groups=groups,
            reasons=[
                f"Policy {policy.policy_id} selects {len(selected)} checks for {risk.tier.value} risk.",
                "Independent checks within a tier run concurrently.",
            ],
        )
