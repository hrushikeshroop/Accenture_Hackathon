from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from .check_result import CheckResult, EvidenceState


class RiskTier(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuthorizationState(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DecisionAction(StrEnum):
    ALLOW = "ALLOW"
    EDIT_REDACT = "EDIT_REDACT"
    REGENERATE = "REGENERATE"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class StopReason(StrEnum):
    RESOLVED = "RESOLVED"
    CRITICAL_VETO = "CRITICAL_VETO"
    TIER_EXHAUSTED = "TIER_EXHAUSTED"
    LATENCY_BUDGET_REACHED = "LATENCY_BUDGET_REACHED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class RiskProfile(BaseModel):
    tier: RiskTier
    signals: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    historical_failure_rate: float = 0
    historical_sample_size: int = 0


class EvaluationResult(BaseModel):
    evaluation_id: str
    event_id: str
    use_case: str
    risk_profile: RiskProfile
    evidence_state: EvidenceState
    authorization_state: AuthorizationState
    decision: DecisionAction
    stop_reason: StopReason
    reasons: list[str]
    checks_selected: list[str]
    checks_skipped: list[str]
    check_results: list[CheckResult]
    policy_id: str
    policy_version: str
    policy_checksum: str
    latency_ms: float
    estimated_cost_units: float
    model_calls: int
    checks_executed: int
    source_versions: dict[str, str] = Field(default_factory=dict)
    source_checksums: dict[str, str] = Field(default_factory=dict)
    sanitized_output: str | None = None
