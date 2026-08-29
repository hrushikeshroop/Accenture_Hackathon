from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from .check_result import CheckStatus
from .decision import DecisionAction, RiskTier


class VetoRule(BaseModel):
    detector: str
    statuses: list[CheckStatus] = Field(default_factory=lambda: [CheckStatus.FAIL])
    decision: DecisionAction
    reason: str


class PolicyConfig(BaseModel):
    policy_id: str
    version: str
    use_case: str
    base_risk: RiskTier
    latency_budget_ms: int = 2000
    fail_mode: DecisionAction = DecisionAction.ESCALATE
    signal_risks: dict[str, RiskTier] = Field(default_factory=dict)
    required_checks: dict[RiskTier, list[str]]
    veto_rules: list[VetoRule] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    allowed_source_statuses: list[str] = Field(
        default_factory=lambda: ["current", "approved"]
    )
    minimum_source_authority: float = 0.5
    historical_boost_min_samples: int = 2
    historical_boost_failure_rate: float = 0.5

    @model_validator(mode="after")
    def validate_policy_contract(self) -> PolicyConfig:
        missing = set(RiskTier) - set(self.required_checks)
        if missing:
            raise ValueError(
                "required_checks is missing risk tiers: "
                + ", ".join(sorted(tier.value for tier in missing))
            )
        if self.fail_mode not in {DecisionAction.BLOCK, DecisionAction.ESCALATE}:
            raise ValueError("fail_mode must be BLOCK or ESCALATE")
        if self.latency_budget_ms <= 0:
            raise ValueError("latency_budget_ms must be positive")
        if not 0 <= self.historical_boost_failure_rate <= 1:
            raise ValueError("historical_boost_failure_rate must be between 0 and 1")
        if self.historical_boost_min_samples < 1:
            raise ValueError("historical_boost_min_samples must be at least 1")
        if not 0 <= self.minimum_source_authority <= 1:
            raise ValueError("minimum_source_authority must be between 0 and 1")
        if not self.allowed_source_statuses:
            raise ValueError("allowed_source_statuses must not be empty")
        if any(not rule.statuses for rule in self.veto_rules):
            raise ValueError("veto rule statuses must not be empty")
        return self
