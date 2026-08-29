from __future__ import annotations

import asyncio
from time import perf_counter
from typing import cast
from uuid import uuid4

from controlplane.detectors.historical import HistoricalSignalDetector
from controlplane.detectors.judge import JudgeDetector
from controlplane.detectors.registry import DetectorRegistry
from controlplane.schemas.check_result import CheckResult, CheckStatus, EvidenceState
from controlplane.schemas.decision import (
    DecisionAction,
    EvaluationResult,
    StopReason,
)
from controlplane.schemas.event import ControlEvent
from controlplane.security.redaction import redact_data
from controlplane.settings import Settings, settings
from controlplane.storage.audit_repository import AuditRepository
from controlplane.storage.policy_repository import PolicyRepository
from controlplane.storage.source_repository import (
    MISSING_SOURCE_MARKER,
    SourceRepository,
)

from .claim_parser import extract_known_claims
from .decision_engine import DecisionEngine
from .risk_profiler import RiskProfiler
from .verification_planner import VerificationPlanner


class ControlPlaneEvaluator:
    def __init__(self, app_settings: Settings = settings):
        self.settings = app_settings
        self.audit = AuditRepository(app_settings.db_path)
        self.policies = PolicyRepository(app_settings.policy_dir)
        self.sources = SourceRepository(app_settings.source_registry)
        self.detectors = DetectorRegistry(app_settings, self.audit, self.sources)
        self.risk_profiler = RiskProfiler()
        self.planner = VerificationPlanner(self.detectors)
        self.decision_engine = DecisionEngine()

    async def evaluate(
        self,
        event: ControlEvent,
        *,
        history_snapshot: tuple[int, float] | None = None,
        counts_toward_history: bool = True,
    ) -> EvaluationResult:
        started = perf_counter()
        event = self._normalize_event(event)
        policy = self.policies.get_for_use_case(event.use_case, event.policy_version)

        historical_detector = cast(
            HistoricalSignalDetector, self.detectors.get("historical_signal")
        )
        if history_snapshot is None:
            historical = await historical_detector.evaluate(event, policy)
        else:
            total, failure_rate = history_snapshot
            historical = historical_detector.result_from_stats(
                policy, total, failure_rate
            )
        risk = self.risk_profiler.profile(event, policy, historical)
        plan = self.planner.plan(risk, policy)
        results: list[CheckResult] = [historical]
        stop_reason: StopReason | None = None

        for group in plan.groups:
            elapsed_ms = (perf_counter() - started) * 1000
            remaining_seconds = (policy.latency_budget_ms - elapsed_ms) / 1000
            if remaining_seconds <= 0:
                stop_reason = StopReason.LATENCY_BUDGET_REACHED
                break
            try:
                prior_results = list(results)
                group_results = await asyncio.wait_for(
                    asyncio.gather(
                        *(
                            self._run_detector_safely(
                                detector_id, event, policy, prior_results
                            )
                            for detector_id in group
                        )
                    ),
                    timeout=remaining_seconds,
                )
            except TimeoutError:
                stop_reason = StopReason.LATENCY_BUDGET_REACHED
                break
            results.extend(group_results)
            if self.decision_engine.has_policy_veto(results, policy):
                stop_reason = StopReason.CRITICAL_VETO
                break
            if self._resolved(event, results):
                stop_reason = StopReason.RESOLVED
                break

        if stop_reason is None:
            stop_reason = StopReason.TIER_EXHAUSTED

        outcome = self.decision_engine.decide(event, risk, results, policy)
        if outcome.critical_veto:
            stop_reason = StopReason.CRITICAL_VETO
        elif stop_reason == StopReason.LATENCY_BUDGET_REACHED:
            outcome.action = policy.fail_mode
            outcome.reasons.insert(
                0,
                "The verification deadline expired; the configured fail mode was applied.",
            )
        elif (
            outcome.action == DecisionAction.ESCALATE
            and stop_reason != StopReason.LATENCY_BUDGET_REACHED
        ):
            stop_reason = StopReason.HUMAN_REVIEW_REQUIRED

        executed = {result.detector_id for result in results}
        skipped = [
            detector_id
            for detector_id in self.detectors.ids()
            if detector_id not in executed
        ]
        latency_ms = (perf_counter() - started) * 1000
        evaluation = EvaluationResult(
            evaluation_id=str(uuid4()),
            event_id=event.event_id,
            use_case=event.use_case,
            risk_profile=risk,
            evidence_state=outcome.evidence,
            authorization_state=outcome.authorization,
            decision=outcome.action,
            stop_reason=stop_reason,
            reasons=outcome.reasons,
            checks_selected=plan.selected,
            checks_skipped=skipped,
            check_results=results,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            policy_checksum=self.policies.checksum(policy),
            latency_ms=latency_ms,
            estimated_cost_units=sum(result.estimated_cost_units for result in results),
            model_calls=sum(result.model_calls for result in results),
            checks_executed=len(results),
            source_versions=self._source_versions(results),
            source_checksums=self._source_checksums(results),
            sanitized_output=outcome.sanitized_output,
        )
        self.audit.save(
            evaluation_id=evaluation.evaluation_id,
            event_id=event.event_id,
            fingerprint=event.fingerprint(),
            use_case=event.use_case,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            decision=evaluation.decision.value,
            risk_tier=risk.tier.value,
            event=redact_data(event.model_dump(mode="json")),
            result=redact_data(evaluation.model_dump(mode="json")),
            counts_toward_history=counts_toward_history,
        )
        return evaluation

    async def replay(
        self, evaluation_id: str, policy_version: str | None = None
    ) -> EvaluationResult:
        record = self.audit.get(evaluation_id)
        if record is None:
            raise KeyError(f"Evaluation {evaluation_id} does not exist")
        target_policy_version = policy_version or record["policy_version"]
        if target_policy_version == record["policy_version"]:
            original_checksum = record["result"].get("policy_checksum")
            if not original_checksum:
                raise ValueError(
                    "Exact replay is unavailable because the original audit record "
                    "does not contain a policy checksum."
                )
            current_policy = self.policies.get_for_use_case(
                record["use_case"], target_policy_version
            )
            if self.policies.checksum(current_policy) != original_checksum:
                raise ValueError(
                    "Exact replay refused because the original policy content has changed."
                )
        self._assert_source_integrity(record["result"])
        payload = dict(record["event"])
        if self._contains_redaction_marker(payload):
            raise ValueError(
                "Exact replay is unavailable because sensitive values were redacted from the audit record."
            )
        payload["event_id"] = f"{payload['event_id']}-replay"
        payload["policy_version"] = target_policy_version
        original_risk = record["result"].get("risk_profile", {})
        history_snapshot = (
            int(original_risk.get("historical_sample_size", 0)),
            float(original_risk.get("historical_failure_rate", 0)),
        )
        return await self.evaluate(
            ControlEvent.model_validate(payload),
            history_snapshot=history_snapshot,
            counts_toward_history=False,
        )

    async def _run_detector_safely(
        self,
        detector_id: str,
        event: ControlEvent,
        policy,
        prior_results: list[CheckResult],
    ) -> CheckResult:
        try:
            detector = self.detectors.get(detector_id)
            if detector_id == "judge_detector":
                return await cast(JudgeDetector, detector).evaluate(
                    event, policy, prior_results=prior_results
                )
            return await detector.evaluate(event, policy)
        except Exception as exc:  # noqa: BLE001 - detector boundary must fail closed
            return CheckResult(
                detector_id=detector_id,
                status=CheckStatus.UNKNOWN,
                severity="HIGH",
                reason=f"Detector failed safely: {type(exc).__name__}.",
                evidence_state=EvidenceState.UNCERTAIN,
            )

    @staticmethod
    def _normalize_event(event: ControlEvent) -> ControlEvent:
        if not event.use_case.startswith("support") or event.candidate.claims:
            return event
        claims = extract_known_claims(event.candidate.text)
        if not claims:
            return event
        normalized = event.model_copy(deep=True)
        normalized.candidate.claims = claims
        normalized.metadata["claims_extracted_by_controlplane"] = True
        return normalized

    @staticmethod
    def _source_versions(results: list[CheckResult]) -> dict[str, str]:
        versions: dict[str, str] = {}
        for result in results:
            for reference in result.evidence_references:
                source_id = reference.get("source_id")
                version = reference.get("source_version")
                if source_id and version:
                    versions[str(source_id)] = str(version)
        return versions

    @staticmethod
    def _source_checksums(results: list[CheckResult]) -> dict[str, str]:
        checksums: dict[str, str] = {}
        for result in results:
            for reference in result.evidence_references:
                source_id = reference.get("source_id")
                checksum = reference.get("source_checksum")
                if source_id and checksum:
                    checksums[str(source_id)] = str(checksum)
        return checksums

    def _assert_source_integrity(self, result: dict[str, object]) -> None:
        versions = self._audit_string_map(result, "source_versions")
        checksums = self._audit_string_map(result, "source_checksums")
        if versions and set(versions) - set(checksums):
            raise ValueError(
                "Exact replay is unavailable because the original audit record "
                "does not contain checksums for every source."
            )
        for source_id, expected_checksum in checksums.items():
            current = self.sources.get(source_id)
            expected_version = versions.get(source_id)
            if expected_checksum == MISSING_SOURCE_MARKER:
                if current is not None:
                    raise ValueError(
                        f"Exact replay refused because source '{source_id}' has changed "
                        "or is unavailable."
                    )
                continue
            if (
                current is None
                or str(current.get("version")) != expected_version
                or str(current.get("checksum")) != expected_checksum
            ):
                raise ValueError(
                    f"Exact replay refused because source '{source_id}' has changed "
                    "or is unavailable."
                )

    @staticmethod
    def _audit_string_map(result: dict[str, object], field: str) -> dict[str, str]:
        value = result.get(field, {})
        if not isinstance(value, dict):
            raise ValueError(  # noqa: TRY004 - replay contract violation maps to HTTP 409
                f"Exact replay is unavailable because audit field '{field}' is malformed."
            )
        return {str(key): str(item) for key, item in value.items()}

    @staticmethod
    def _contains_redaction_marker(value: object) -> bool:
        if isinstance(value, str):
            return "[REDACTED]" in value
        if isinstance(value, dict):
            return any(
                ControlPlaneEvaluator._contains_redaction_marker(item)
                for item in value.values()
            )
        if isinstance(value, list):
            return any(
                ControlPlaneEvaluator._contains_redaction_marker(item) for item in value
            )
        return False

    @staticmethod
    def _resolved(event: ControlEvent, results: list[CheckResult]) -> bool:
        by_id = {result.detector_id: result for result in results}
        pii = by_id.get("pii_detector")
        if pii and pii.status == CheckStatus.FAIL and not event.candidate.claims:
            return True
        judge = by_id.get("judge_detector")
        if (
            judge
            and judge.model_calls == 1
            and judge.evidence_state
            in {
                EvidenceState.VERIFIED,
                EvidenceState.CONTRADICTED,
                EvidenceState.UNCERTAIN,
                EvidenceState.NO_EVIDENCE,
            }
        ):
            return True
        evidence = DecisionEngine.aggregate_evidence(results)
        if evidence in {EvidenceState.VERIFIED, EvidenceState.CONTRADICTED}:
            return True
        if event.use_case.startswith("engineering"):
            relevant = [
                result
                for result in results
                if result.detector_id != "historical_signal"
            ]
            return bool(relevant) and all(
                result.status in {CheckStatus.PASS, CheckStatus.NOT_APPLICABLE}
                for result in relevant
            )
        return False
