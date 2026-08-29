from __future__ import annotations

import re
from typing import Any

PATTERNS = [
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    re.compile(r"(?<!\w)(?:\+?91[ .-]?)?[6-9]\d{4}[ .-]?\d{5}(?!\w)"),
    re.compile(
        r"(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\(?\d{3}\)?[ .-]?)?"
        r"\d{3}[ .-]?\d{4}(?!\w)"
    ),
    re.compile(r"(?i)(?:api[_-]?key|password|secret)\s*[:=]\s*['\"]?[^\s'\"]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
]

SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(?:password|passwd|secret|api[_-]?key|access[_-]?token|"
    r"card[_-]?(?:number|no)|credit[_-]?card|cvv|ssn)"
)


def redact_text(value: str) -> str:
    result = value
    for pattern in PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            SENSITIVE_KEY_PATTERN.fullmatch(str(key))
            or contains_sensitive_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(contains_sensitive_key(item) for item in value)
    return False


def redact_data(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            redact_text(str(key)): (
                "[REDACTED]"
                if SENSITIVE_KEY_PATTERN.fullmatch(str(key))
                else redact_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, tuple):
        return [redact_data(item) for item in value]
    if isinstance(value, int) and not isinstance(value, bool):
        text = str(value)
        return "[REDACTED]" if redact_text(text) != text else value
    return value
