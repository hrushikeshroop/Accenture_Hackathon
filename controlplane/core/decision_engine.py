from __future__ import annotations

from dataclasses import dataclass

from controlplane.schemas.check_result import CheckResult, CheckStatus, EvidenceState
from controlplane.schemas.decision import (
    AuthorizationState,
    DecisionAction,
    RiskProfile,
)
from controlplane.schemas.event import ControlEvent
from controlplane.schemas.policy import PolicyConfig
from controlplane.security.redaction import redact_text


@dataclass
class DecisionOutcome:
    action: DecisionAction
    evidence: EvidenceState
    authorization: AuthorizationState
    reasons: list[str]
    sanitized_output: str | None = None
    critical_veto: bool = False


class DecisionEngine:
    def decide(
        self,
        event: ControlEvent,
        risk: RiskProfile,
        results: list[CheckResult],
        policy: PolicyConfig,
    ) -> DecisionOutcome:
        evidence = self.aggregate_evidence(results)
        authorization = self.authorization(event, results)
        by_id = {result.detector_id: result for result in results}

        for veto in policy.veto_rules:
            result = by_id.get(veto.detector)
            if result and result.status in veto.statuses:
                return DecisionOutcome(
                    action=veto.decision,
                    evidence=evidence,
                    authorization=authorization,
                    reasons=[veto.reason, result.reason],
                    critical_veto=True,
                )

        pii = by_id.get("pii_detector")
        pii_failed = bool(pii and pii.status == CheckStatus.FAIL)
        pii_reasons = [pii.reason] if pii_failed and pii else []

        if authorization == AuthorizationState.DENIED:
            return DecisionOutcome(
                action=DecisionAction.BLOCK,
                evidence=evidence,
                authorization=authorization,
                reasons=["Trusted authorization or entitlement checks failed.", *pii_reasons],
                critical_veto=True,
            )
        if authorization == AuthorizationState.APPROVAL_REQUIRED:
            return DecisionOutcome(
                action=DecisionAction.ESCALATE,
                evidence=evidence,
                authorization=authorization,
                reasons=["A required approval is missing.", *pii_reasons],
            )
        if evidence == EvidenceState.CONTRADICTED:
            return DecisionOutcome(
                action=(
                    DecisionAction.REGENERATE
                    if event.event_type == "candidate_response"
                    else DecisionAction.BLOCK
                ),
                evidence=evidence,
                authorization=authorization,
                reasons=["The candidate conflicts with authoritative evidence.", *pii_reasons],
            )
        if evidence == EvidenceState.NO_EVIDENCE:
            return DecisionOutcome(
                action=(
                    DecisionAction.ESCALATE
                    if risk.tier.value in {"HIGH", "CRITICAL"}
                    else DecisionAction.REGENERATE
                ),
                evidence=evidence,
                authorization=authorization,
                reasons=["No usable evidence supports at least one claim.", *pii_reasons],
            )
        if evidence == EvidenceState.UNCERTAIN:
            return DecisionOutcome(
                action=(
                    DecisionAction.REGENERATE
                    if event.event_type == "candidate_response"
                    and risk.tier.value in {"LOW", "MEDIUM"}
                    else DecisionAction.ESCALATE
                ),
                evidence=evidence,
                authorization=authorization,
                reasons=[
                    "Available verification is uncertain or conflicting.",
                    *pii_reasons,
                ],
            )

        if pii_failed:
            sanitized = redact_text(event.candidate.text or "")
            return DecisionOutcome(
                action=(
                    DecisionAction.EDIT_REDACT
                    if event.event_type == "candidate_response"
                    else DecisionAction.BLOCK
                ),
                evidence=evidence,
                authorization=authorization,
                reasons=pii_reasons,
                sanitized_output=sanitized,
            )

        unresolved = [
            result
            for result in results
            if result.status == CheckStatus.UNKNOWN
            and result.detector_id != "historical_signal"
        ]
        if unresolved and risk.tier.value in {"HIGH", "CRITICAL"}:
            return DecisionOutcome(
                action=DecisionAction.ESCALATE,
                evidence=evidence,
                authorization=authorization,
                reasons=["A mandatory high-risk check remains unresolved."],
            )
        return DecisionOutcome(
            action=DecisionAction.ALLOW,
            evidence=evidence,
            authorization=authorization,
            reasons=["All mandatory checks resolved without a policy violation."],
            sanitized_output=event.candidate.text,
        )

    @staticmethod
    def aggregate_evidence(results: list[CheckResult]) -> EvidenceState:
        states = [
            result.evidence_state
            for result in results
            if result.evidence_state != EvidenceState.NOT_APPLICABLE
        ]
        for state in (
            EvidenceState.CONTRADICTED,
            EvidenceState.UNCERTAIN,
            EvidenceState.NO_EVIDENCE,
            EvidenceState.VERIFIED,
        ):
            if state in states:
                return state
        return EvidenceState.NOT_APPLICABLE

    @staticmethod
    def authorization(
        event: ControlEvent, results: list[CheckResult]
    ) -> AuthorizationState:
        if event.event_type != "proposed_action":
            return AuthorizationState.NOT_APPLICABLE
        by_id = {result.detector_id: result for result in results}
        for detector_id in ("permission_detector", "entitlement_detector"):
            result = by_id.get(detector_id)
            if result and result.status == CheckStatus.FAIL:
                return AuthorizationState.DENIED
        for detector_id in ("permission_detector", "entitlement_detector"):
            result = by_id.get(detector_id)
            if result and result.status == CheckStatus.UNKNOWN:
                return AuthorizationState.APPROVAL_REQUIRED
        if event.trusted_context.get("authorized") is False:
            return AuthorizationState.DENIED
        return AuthorizationState.AUTHORIZED

    @staticmethod
    def has_policy_veto(
        results: list[CheckResult], policy: PolicyConfig
    ) -> bool:
        by_id = {result.detector_id: result for result in results}
        return any(
            (result := by_id.get(veto.detector)) is not None
            and result.status in veto.statuses
            for veto in policy.veto_rules
        )
