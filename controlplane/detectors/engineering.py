from __future__ import annotations

import re
from time import perf_counter
from typing import Any

from controlplane.schemas.check_result import CheckResult, CheckStatus
from controlplane.schemas.event import ControlEvent
from controlplane.schemas.policy import PolicyConfig
from controlplane.security.redaction import contains_sensitive_key

from .base import Detector

DESTRUCTIVE_PATTERNS = [
    re.compile(r"\bdrop\s+(?:table|database)\b", re.IGNORECASE),
    re.compile(r"\btruncate\s+table\b", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\b.*--force", re.IGNORECASE),
]

_SQL_IDENTIFIER = r'(?:[A-Za-z_][\w$]*|`[^`]+`|"[^"]+"|\[[^\]]+\])'
DELETE_FROM_PATTERN = re.compile(
    rf"\bdelete\s+from\s+{_SQL_IDENTIFIER}(?:\s*\.\s*{_SQL_IDENTIFIER})*",
    re.IGNORECASE,
)
DELETE_BOUNDARY_PATTERN = re.compile(r";|[.!?](?=\s|$)|\r?\n")
SQL_LINE_CONTINUATIONS = re.compile(
    r"(?i)^(?:where|using|returning|order\s+by|limit|and|or)\b"
)
SQL_NON_CODE_PATTERN = re.compile(
    r"--[^\r\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|"
    r"`(?:``|[^`])*`|\[(?:\]\]|[^\]])*\]",
    re.DOTALL,
)

SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)(?:api[_-]?key|password|secret)\s*[:=]\s*['\"]?[^\s'\"]+"),
]

REVERSIBILITY_REQUIRED_OPERATIONS = {
    "branch_merge",
    "database_command",
    "deployment",
    "file_edit",
    "schema_migration",
}
READ_ONLY_ENGINEERING_OPERATIONS = {
    "database_read",
    "list_files",
    "query",
    "read_file",
    "read_repository",
}
MUTATING_PATTERNS = [
    re.compile(r"\balter\s+table\b", re.IGNORECASE),
    re.compile(r"\bcreate\s+table\b", re.IGNORECASE),
    re.compile(r"\binsert\s+into\b", re.IGNORECASE),
    re.compile(r"\bupdate\s+\S+\s+set\b", re.IGNORECASE),
]


def _flatten(value: Any) -> list[str]:
    if isinstance(value, dict):
        flattened: list[str] = []
        for key, item in value.items():
            flattened.append(str(key))
            flattened.extend(_flatten(item))
        return flattened
    if isinstance(value, (list, tuple, set)):
        return [part for item in value for part in _flatten(item)]
    return [str(value)]


def candidate_blob(event: ControlEvent) -> str:
    values = [
        event.candidate.text or "",
        event.candidate.tool or "",
        event.candidate.operation or "",
    ]
    values.extend(_flatten(event.candidate.arguments))
    return "\n".join(values)


def contains_exposed_secret(event: ControlEvent) -> bool:
    candidate = event.candidate.model_dump(mode="json")
    return contains_sensitive_key(candidate) or any(
        pattern.search(candidate_blob(event)) for pattern in SECRET_PATTERNS
    )


def _mask_sql_non_code(value: str) -> str:
    def mask(match: re.Match[str]) -> str:
        return "".join(
            character if character in {"\r", "\n"} else " "
            for character in match.group(0)
        )

    return SQL_NON_CODE_PATTERN.sub(mask, value)


def contains_unbounded_delete(blob: str) -> bool:
    """Detect DELETE statements whose own bounded statement has no WHERE clause.

    AI output often contains a command followed by prose. Statement boundaries keep
    a later natural-language word such as "where" from masking an unsafe DELETE.
    A newline immediately followed by a common SQL continuation remains part of the
    same bounded statement so multiline DELETE ... WHERE commands are not blocked.
    """

    for match in DELETE_FROM_PATTERN.finditer(blob):
        tail = blob[match.end() :]
        masked_tail = _mask_sql_non_code(tail)
        statement_tail = masked_tail
        for boundary in DELETE_BOUNDARY_PATTERN.finditer(masked_tail):
            if boundary.group(0) in {"\n", "\r\n"}:
                following = masked_tail[boundary.end() :].lstrip()
                if SQL_LINE_CONTINUATIONS.match(following):
                    continue
            statement_tail = masked_tail[: boundary.start()]
            break
        if re.search(r"\bwhere\b", statement_tail, re.IGNORECASE) is None:
            return True
    return False


def contains_destructive_operation(blob: str) -> bool:
    return contains_unbounded_delete(blob) or any(
        pattern.search(blob) for pattern in DESTRUCTIVE_PATTERNS
    )


def requires_rollback(event: ControlEvent) -> bool:
    if event.event_type != "proposed_action":
        return False
    operation = event.candidate.operation or ""
    blob = candidate_blob(event)
    if contains_destructive_operation(blob) or any(
        pattern.search(blob) for pattern in MUTATING_PATTERNS
    ):
        return True
    if operation in REVERSIBILITY_REQUIRED_OPERATIONS:
        return True
    return operation not in READ_ONLY_ENGINEERING_OPERATIONS


class EngineeringActionDetector(Detector):
    detector_id = "engineering_action"

    async def evaluate(self, event: ControlEvent, policy: PolicyConfig) -> CheckResult:
        started = perf_counter()
        blob = candidate_blob(event)
        destructive = contains_destructive_operation(blob)
        production = event.trusted_context.get("environment") == "production"
        signals = ["destructive_operation"] if destructive else []
        if production:
            signals.append("production_environment")
        if destructive and production:
            status = CheckStatus.FAIL
            reason = "A destructive operation targets the production environment."
            severity = "CRITICAL"
        else:
            status = CheckStatus.PASS
            reason = "No prohibited destructive production operation was detected."
            severity = "HIGH" if destructive else "LOW"
        return CheckResult(
            detector_id=self.detector_id,
            status=status,
            severity=severity,
            reason=reason,
            signals=signals,
            latency_ms=(perf_counter() - started) * 1000,
            estimated_cost_units=1,
        )


class SecretDetector(Detector):
    detector_id = "secret_detector"

    async def evaluate(self, event: ControlEvent, policy: PolicyConfig) -> CheckResult:
        started = perf_counter()
        exposed = contains_exposed_secret(event)
        return CheckResult(
            detector_id=self.detector_id,
            status=CheckStatus.FAIL if exposed else CheckStatus.PASS,
            severity="CRITICAL" if exposed else "LOW",
            reason=(
                "A credential-like value appears in the proposed content."
                if exposed
                else "No credential-like value was detected."
            ),
            signals=["exposed_secret"] if exposed else [],
            latency_ms=(perf_counter() - started) * 1000,
            estimated_cost_units=1,
        )


class PermissionDetector(Detector):
    detector_id = "permission_detector"

    async def evaluate(self, event: ControlEvent, policy: PolicyConfig) -> CheckResult:
        started = perf_counter()
        authorized = bool(event.trusted_context.get("authorized", False))
        production = event.trusted_context.get("environment") == "production"
        approval = bool(event.trusted_context.get("approval_present", False))
        if not authorized:
            status = CheckStatus.FAIL
            reason = "The trusted context does not authorize this actor."
            signals = ["unauthorized_actor"]
        elif production and not approval:
            status = CheckStatus.UNKNOWN
            reason = "The actor is authorized, but production approval is missing."
            signals = ["missing_approval"]
        else:
            status = CheckStatus.PASS
            reason = "The actor and required approval are valid."
            signals = []
        return CheckResult(
            detector_id=self.detector_id,
            status=status,
            severity="CRITICAL" if status == CheckStatus.FAIL else "HIGH",
            reason=reason,
            signals=signals,
            latency_ms=(perf_counter() - started) * 1000,
            estimated_cost_units=1,
        )


class ReversibilityDetector(Detector):
    detector_id = "reversibility_detector"

    async def evaluate(self, event: ControlEvent, policy: PolicyConfig) -> CheckResult:
        started = perf_counter()
        rollback = bool(event.trusted_context.get("rollback_available", False))
        production = event.trusted_context.get("environment") == "production"
        rollback_required = requires_rollback(event)
        if production and rollback_required and not rollback:
            status = CheckStatus.FAIL
            reason = "No verified rollback path exists for the production action."
            signals = ["missing_rollback"]
        else:
            status = CheckStatus.PASS
            reason = (
                "A rollback path is available for the mutating production action."
                if production and rollback_required
                else "The action does not require a production rollback path."
            )
            signals = []
        return CheckResult(
            detector_id=self.detector_id,
            status=status,
            severity="CRITICAL" if status == CheckStatus.FAIL else "LOW",
            reason=reason,
            signals=signals,
            latency_ms=(perf_counter() - started) * 1000,
            estimated_cost_units=1,
        )
