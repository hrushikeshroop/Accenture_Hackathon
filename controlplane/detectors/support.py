from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from controlplane.schemas.check_result import CheckResult, CheckStatus, EvidenceState
from controlplane.schemas.event import ControlEvent
from controlplane.schemas.policy import PolicyConfig
from controlplane.security.redaction import (
    PATTERNS,
    contains_sensitive_key,
    redact_text,
)
from controlplane.storage.source_repository import (
    MISSING_SOURCE_MARKER,
    SourceRepository,
)

from .base import Detector


class PiiDetector(Detector):
    detector_id = "pii_detector"

    async def evaluate(self, event: ControlEvent, policy: PolicyConfig) -> CheckResult:
        started = perf_counter()
        text = event.candidate.text or ""
        candidate_payload = json.dumps(event.candidate.model_dump(mode="json"), default=str)
        found = [
            pattern.pattern for pattern in PATTERNS if pattern.search(candidate_payload)
        ]
        if contains_sensitive_key(event.candidate.model_dump(mode="json")):
            found.append("sensitive_argument_key")
        return CheckResult(
            detector_id=self.detector_id,
            status=CheckStatus.FAIL if found else CheckStatus.PASS,
            severity="HIGH" if found else "LOW",
            reason=(
                f"Detected {len(found)} sensitive-data pattern(s); a redacted output is available."
                if found
                else "No configured PII pattern was detected."
            ),
            evidence_references=(
                [{"sanitized_output": redact_text(text)}] if found else []
            ),
            signals=["contains_pii"] if found else [],
            latency_ms=(perf_counter() - started) * 1000,
            estimated_cost_units=1,
        )


class ClaimExtractorDetector(Detector):
    detector_id = "claim_extractor"

    async def evaluate(self, event: ControlEvent, policy: PolicyConfig) -> CheckResult:
        started = perf_counter()
        count = len(event.candidate.claims)
        if count:
            status = CheckStatus.PASS
            origin = (
                "extracted by the bounded PoC parser"
                if event.metadata.get("claims_extracted_by_controlplane")
                else "supplied by the application adapter"
            )
            reason = f"Received {count} structured claim unit(s), {origin}."
        elif event.candidate.text:
            status = CheckStatus.UNKNOWN
            reason = "Text is present but no structured claim units were supplied."
        else:
            status = CheckStatus.NOT_APPLICABLE
            reason = "The event contains no candidate text."
        return CheckResult(
            detector_id=self.detector_id,
            status=status,
            severity="MEDIUM" if status == CheckStatus.UNKNOWN else "LOW",
            reason=reason,
            latency_ms=(perf_counter() - started) * 1000,
            estimated_cost_units=1,
        )


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return left.strip().lower() == right.strip().lower()
    return left == right


class RetrievalDetector(Detector):
    detector_id = "retrieval_detector"
    tier = 2
    estimated_cost_units = 2

    def __init__(self, sources: SourceRepository):
        self.sources = sources

    async def evaluate(self, event: ControlEvent, policy: PolicyConfig) -> CheckResult:
        started = perf_counter()
        source_ids = event.trusted_context.get("policy_sources") or policy.source_ids
        requested_source_ids = list(dict.fromkeys(source_ids))
        sources = {
            source["source_id"]: source
            for source in self.sources.resolve(requested_source_ids)
        }
        if not event.candidate.claims:
            return CheckResult(
                detector_id=self.detector_id,
                status=CheckStatus.UNKNOWN,
                severity="MEDIUM",
                reason="No structured claim was available for source verification.",
                evidence_state=EvidenceState.NO_EVIDENCE,
                latency_ms=(perf_counter() - started) * 1000,
                estimated_cost_units=self.estimated_cost_units,
            )

        states: list[EvidenceState] = []
        references: list[dict[str, Any]] = []
        for claim in event.candidate.claims:
            candidates: list[tuple[float, dict[str, Any], Any, int]] = []
            allowed_statuses = {
                item.lower() for item in policy.allowed_source_statuses
            }
            for source_id in requested_source_ids:
                source = sources.get(source_id)
                if source is None:
                    references.append(
                        {
                            "claim_key": claim.key,
                            "claim_value": claim.value,
                            "source_id": source_id,
                            "source_version": MISSING_SOURCE_MARKER,
                            "source_checksum": MISSING_SOURCE_MARKER,
                            "source_status": "missing",
                            "usable": False,
                            "used_for_decision": False,
                            "evidence_state": EvidenceState.NO_EVIDENCE.value,
                            "reason": "The configured source could not be resolved.",
                        }
                    )
                    continue

                authority = float(source.get("authority", 0))
                status = str(source.get("status", "unknown")).lower()
                reference = {
                    "claim_key": claim.key,
                    "claim_value": claim.value,
                    "source_id": source_id,
                    "source_version": source.get("version"),
                    "source_checksum": source.get("checksum"),
                    "source_status": status,
                    "authority": authority,
                    "usable": False,
                    "used_for_decision": False,
                    "evidence_state": EvidenceState.NOT_APPLICABLE.value,
                }
                if not source.get("content_available", True):
                    reference["reason"] = "The configured source document is unavailable."
                    references.append(reference)
                    continue
                if status not in allowed_statuses:
                    reference["reason"] = (
                        f"Source status '{status}' is not allowed by policy."
                    )
                    references.append(reference)
                    continue
                if authority < policy.minimum_source_authority:
                    reference["reason"] = (
                        "Source authority is below the policy minimum of "
                        f"{policy.minimum_source_authority:.2f}."
                    )
                    references.append(reference)
                    continue
                facts = source.get("facts", {})
                if claim.key not in facts:
                    reference["reason"] = "Source does not contain this claim key."
                    references.append(reference)
                    continue

                reference.update(
                    {
                        "usable": True,
                        "expected_value": facts[claim.key],
                        "reason": "Source is eligible for verification.",
                    }
                )
                reference_index = len(references)
                references.append(reference)
                candidates.append(
                    (authority, source, facts[claim.key], reference_index)
                )
            if not candidates:
                states.append(EvidenceState.NO_EVIDENCE)
                continue
            highest = max(item[0] for item in candidates)
            authoritative = [item for item in candidates if item[0] == highest]
            values = {repr(item[2]) for item in authoritative}
            if len(values) > 1:
                claim_state = EvidenceState.UNCERTAIN
            elif _equal(claim.value, authoritative[0][2]):
                claim_state = EvidenceState.VERIFIED
            else:
                claim_state = EvidenceState.CONTRADICTED
            states.append(claim_state)
            authoritative_indexes = {item[3] for item in authoritative}
            for authority, source, value, reference_index in candidates:
                reference = references[reference_index]
                if reference_index in authoritative_indexes:
                    reference.update(
                        {
                            "evidence_state": claim_state.value,
                            "used_for_decision": True,
                            "reason": "Highest-authority usable source for this claim.",
                        }
                    )
                else:
                    reference["reason"] = (
                        "Usable source was not selected because a higher-authority "
                        "source was available."
                    )

        if EvidenceState.CONTRADICTED in states:
            state = EvidenceState.CONTRADICTED
            status = CheckStatus.FAIL
            reason = "At least one claim conflicts with the highest-authority source."
        elif EvidenceState.UNCERTAIN in states:
            state = EvidenceState.UNCERTAIN
            status = CheckStatus.UNKNOWN
            reason = "Equally authoritative sources conflict."
        elif EvidenceState.NO_EVIDENCE in states:
            state = EvidenceState.NO_EVIDENCE
            status = CheckStatus.UNKNOWN
            reason = "At least one claim has no usable supporting evidence."
        else:
            state = EvidenceState.VERIFIED
            status = CheckStatus.PASS
            reason = "All structured claims match the highest-authority source facts."

        return CheckResult(
            detector_id=self.detector_id,
            status=status,
            severity="HIGH" if status != CheckStatus.PASS else "LOW",
            reason=reason,
            confidence=1.0 if state in {EvidenceState.VERIFIED, EvidenceState.CONTRADICTED} else None,
            evidence_state=state,
            evidence_references=references,
            latency_ms=(perf_counter() - started) * 1000,
            estimated_cost_units=self.estimated_cost_units,
        )


class EntitlementDetector(Detector):
    detector_id = "entitlement_detector"

    async def evaluate(self, event: ControlEvent, policy: PolicyConfig) -> CheckResult:
        started = perf_counter()
        if event.event_type != "proposed_action":
            status = CheckStatus.NOT_APPLICABLE
            reason = "Entitlement is evaluated only for proposed business actions."
            signals: list[str] = []
        elif not event.trusted_context.get("identity_verified", False):
            status = CheckStatus.FAIL
            reason = "Customer identity is not verified."
            signals = ["identity_unverified"]
        elif not event.trusted_context.get("eligible", False):
            status = CheckStatus.FAIL
            reason = "Trusted customer records do not establish action eligibility."
            signals = ["customer_ineligible"]
        elif not event.trusted_context.get("approval_present", False):
            status = CheckStatus.UNKNOWN
            reason = "The customer action is eligible, but trusted approval is missing."
            signals = ["missing_approval"]
        else:
            status = CheckStatus.PASS
            reason = "Identity, entitlement, and approval checks passed."
            signals = []
        return CheckResult(
            detector_id=self.detector_id,
            status=status,
            severity=(
                "CRITICAL"
                if status == CheckStatus.FAIL
                else "HIGH"
                if status == CheckStatus.UNKNOWN
                else "LOW"
            ),
            reason=reason,
            signals=signals,
            latency_ms=(perf_counter() - started) * 1000,
            estimated_cost_units=1,
        )
