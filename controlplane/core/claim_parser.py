from __future__ import annotations

import re

from controlplane.schemas.event import Claim

NUMBER_WORDS = {
    "seven": 7,
    "thirty": 30,
}


def extract_known_claims(text: str | None) -> list[Claim]:
    """Extract a deliberately bounded set of demonstrable policy claims.

    This is a PoC parser, not a general factual-claim extraction model. Unknown
    statements remain unstructured and therefore cannot be silently verified.
    """
    if not text:
        return []

    normalized = " ".join(text.lower().split())
    claims: list[Claim] = []

    refund_window = re.search(
        r"refund(?:s|ed)?[^.]{0,60}?within\s+(\d+|seven|thirty)\s+"
        r"(?:calendar\s+)?days?",
        normalized,
    )
    if refund_window:
        token = refund_window.group(1)
        value = NUMBER_WORDS.get(token, int(token) if token.isdigit() else 0)
        claims.append(
            Claim(key="refund_window_days", value=value, text=refund_window.group(0))
        )

    if re.search(r"refund[^.]{0,80}?(?:at any time|after (?:the )?window)", normalized):
        claims.append(
            Claim(
                key="refunds_after_window",
                value=True,
                text="Refund remains available after the approved window.",
            )
        )

    if "lifetime service guarantee" in normalized or "lifetime guarantee" in normalized:
        claims.append(
            Claim(
                key="lifetime_service_guarantee",
                value=True,
                text="A lifetime service guarantee is available.",
            )
        )

    return claims
