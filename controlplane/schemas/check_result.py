from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceState(StrEnum):
    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    UNCERTAIN = "UNCERTAIN"
    NO_EVIDENCE = "NO_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CheckResult(BaseModel):
    detector_id: str
    status: CheckStatus
    severity: str = "LOW"
    reason: str
    confidence: float | None = None
    evidence_state: EvidenceState = EvidenceState.NOT_APPLICABLE
    evidence_references: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    sample_size: int = 0
    latency_ms: float = 0
    estimated_cost_units: float = 0
    model_calls: int = 0
