from __future__ import annotations

import asyncio
import json
from time import perf_counter
from urllib.request import Request, urlopen

from controlplane.schemas.check_result import CheckResult, CheckStatus, EvidenceState
from controlplane.schemas.event import ControlEvent
from controlplane.schemas.policy import PolicyConfig
from controlplane.security.redaction import redact_data
from controlplane.settings import Settings

from .base import Detector


class JudgeDetector(Detector):
    detector_id = "judge_detector"
    tier = 3
    estimated_cost_units = 10

    def __init__(self, settings: Settings):
        self.settings = settings

    async def evaluate(
        self,
        event: ControlEvent,
        policy: PolicyConfig,
        *,
        prior_results: list[CheckResult] | None = None,
    ) -> CheckResult:
        started = perf_counter()
        evidence_references = self._retrieval_references(prior_results or [])
        if not (self.settings.judge_url and self.settings.judge_model):
            return CheckResult(
                detector_id=self.detector_id,
                status=CheckStatus.UNKNOWN,
                severity="MEDIUM",
                reason="The optional secondary model judge is not configured.",
                evidence_state=EvidenceState.NOT_APPLICABLE,
                latency_ms=(perf_counter() - started) * 1000,
                estimated_cost_units=0,
                model_calls=0,
            )
        if not evidence_references:
            return CheckResult(
                detector_id=self.detector_id,
                status=CheckStatus.UNKNOWN,
                severity="HIGH",
                reason=(
                    "The secondary judge was not called because no retrieved "
                    "evidence trace was supplied."
                ),
                evidence_state=EvidenceState.NO_EVIDENCE,
                latency_ms=(perf_counter() - started) * 1000,
                estimated_cost_units=0,
                model_calls=0,
            )
        try:
            if self.settings.judge_url == "mock://local":
                state, reason = self._mock_call(event, evidence_references)
            else:
                state, reason = await asyncio.to_thread(
                    self._call, event, evidence_references
                )
            status = (
                CheckStatus.PASS
                if state == EvidenceState.VERIFIED
                else CheckStatus.FAIL
                if state == EvidenceState.CONTRADICTED
                else CheckStatus.UNKNOWN
            )
        except Exception as exc:  # noqa: BLE001 - external boundary must fail closed
            state = EvidenceState.NOT_APPLICABLE
            status = CheckStatus.UNKNOWN
            reason = f"Secondary judge failed safely: {type(exc).__name__}."
        return CheckResult(
            detector_id=self.detector_id,
            status=status,
            severity="HIGH",
            reason=reason,
            evidence_state=state,
            evidence_references=redact_data(evidence_references),
            latency_ms=(perf_counter() - started) * 1000,
            estimated_cost_units=self.estimated_cost_units,
            model_calls=1,
        )

    @staticmethod
    def _mock_call(
        event: ControlEvent, evidence_references: list[dict[str, object]]
    ) -> tuple[EvidenceState, str]:
        """Transparent in-process substitute used only for the PoC demo and tests."""
        requested = str(event.metadata.get("mock_judge_state", "UNCERTAIN"))
        state = EvidenceState(requested)
        return (
            state,
            (
                "Simulated secondary-judge result over the supplied retrieval trace "
                "for the offline PoC; no external model was called."
            ),
        )

    def _call(
        self,
        event: ControlEvent,
        evidence_references: list[dict[str, object]],
    ) -> tuple[EvidenceState, str]:
        judge_input = self._external_payload(event, evidence_references)
        payload = {
            "model": self.settings.judge_model,
            "reasoning_effort": "none",
            "max_completion_tokens": 180,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Classify the candidate as VERIFIED, CONTRADICTED, UNCERTAIN, "
                        "or NO_EVIDENCE using only the supplied retrieved_evidence. "
                        "Honor usability and used_for_decision flags; if no usable "
                        "evidence establishes the claim, return NO_EVIDENCE. Return "
                        "JSON with state and reason. Never use internal model knowledge "
                        "as evidence."
                    ),
                },
                {"role": "user", "content": json.dumps(judge_input, default=str)},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.settings.judge_api_key:
            headers["Authorization"] = f"Bearer {self.settings.judge_api_key}"
        request = Request(
            self.settings.judge_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=self.settings.judge_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return EvidenceState(parsed["state"]), str(parsed["reason"])

    @staticmethod
    def _external_payload(
        event: ControlEvent,
        evidence_references: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        """Return only the redacted fields required for secondary classification."""
        payload = {
            "schema_version": event.schema_version,
            "use_case": event.use_case,
            "event_type": event.event_type,
            "candidate": event.candidate.model_dump(mode="json"),
            "policy_source_ids": list(
                event.trusted_context.get("policy_sources", [])
            ),
            "retrieved_evidence": evidence_references or [],
        }
        return redact_data(payload)

    @staticmethod
    def _retrieval_references(
        prior_results: list[CheckResult],
    ) -> list[dict[str, object]]:
        return [
            dict(reference)
            for result in prior_results
            if result.detector_id == "retrieval_detector"
            for reference in result.evidence_references
        ]
