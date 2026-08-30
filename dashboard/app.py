from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import requests
import streamlit as st

from dashboard.view_models import (
    candidate_preview,
    check_rows,
    evidence_rows,
    human_review_packet,
    key_value_rows,
    policy_check_rows,
    policy_veto_rows,
    scenario_meta,
    use_case_metric_rows,
    verification_route,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCENARIO_GROUPS = {
    "Engineering · Production": "engineering.production",
    "Engineering · Development": "engineering.development",
    "Support · Transactional": "support.transactional",
    "Support · Informational": "support.informational",
}

st.set_page_config(
    page_title="ControlPlane.ai · Decision Console",
    page_icon="CP",
    layout="wide",
)
st.markdown(
    """
    <style>
      :root {
        --cp-indigo: #6558e8;
        --cp-cyan: #0891b2;
        --cp-green: #059669;
        --cp-amber: #d97706;
        --cp-red: #dc2626;
        --cp-border: rgba(128, 128, 128, .19);
        --cp-muted: rgba(128, 128, 128, .08);
      }
      #MainMenu, footer {visibility: hidden;}
      header[data-testid="stHeader"] {background: transparent;}
      .block-container {
        max-width: none;
        width: 100%;
        box-sizing: border-box;
        padding-top: 4.25rem;
        padding-left: 1.25rem;
        padding-right: 1.25rem;
        padding-bottom: 3rem;
      }
      [data-testid="stSidebar"], [data-testid="collapsedControl"] {display: none;}
      [data-testid="stHorizontalBlock"]:has(.cp-topbar-brand) {
        align-items: center;
        border: 1px solid var(--cp-border);
        border-radius: .9rem;
        background: rgba(128,128,128,.025);
        padding: .42rem .55rem;
        margin-bottom: .7rem;
      }
      [data-testid="stHorizontalBlock"]:has(.cp-topbar-brand) [data-testid="column"] {
        min-width: 0;
      }
      .cp-topbar-brand {
        display: flex;
        align-items: center;
        gap: .68rem;
        min-width: 0;
        min-height: 2.5rem;
      }
      .cp-topbar-mark {
        display: grid;
        place-items: center;
        width: 2.1rem;
        height: 2.1rem;
        border-radius: .62rem;
        background: #6558e8;
        color: white;
        font-size: .7rem;
        font-weight: 820;
      }
      .cp-topbar-product {font-size: .9rem; font-weight: 780; line-height: 1.15;}
      .cp-topbar-mode {font-size: .65rem; opacity: .58; margin-top: .14rem;}
      [data-testid="stHorizontalBlock"]:has(.cp-topbar-brand) [data-testid="stPopover"] button {
        min-height: 2.5rem;
        white-space: nowrap;
      }
      [data-testid="stMetric"] {
        background: rgba(99, 88, 232, .045);
        border: 1px solid rgba(99, 88, 232, .14);
        border-radius: .75rem;
        padding: .75rem .9rem;
      }
      .stButton > button[kind="primary"] {
        min-height: 3.05rem;
        border: 0;
        border-radius: .75rem;
        background: linear-gradient(100deg, #574bd6, #6558e8 55%, #397bc6);
        box-shadow: 0 8px 22px rgba(87, 75, 214, .2);
        font-weight: 720;
        letter-spacing: .01em;
      }
      .stButton > button[kind="primary"]:hover {
        box-shadow: 0 10px 28px rgba(87, 75, 214, .28);
        transform: translateY(-1px);
      }
      .cp-hero {
        position: relative;
        overflow: hidden;
        border: 1px solid var(--cp-border);
        background: rgba(128,128,128,.025);
        border-radius: 1.1rem;
        padding: .9rem 1.1rem;
        margin-bottom: 1.1rem;
      }
      .cp-hero-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
      }
      .cp-hero h1 {
        margin: .12rem 0 .28rem 0;
        font-size: clamp(1.65rem, 2.5vw, 2.25rem);
        line-height: 1.08;
        letter-spacing: -.035em;
      }
      .cp-hero-copy {max-width: 760px; opacity: .78; line-height: 1.55;}
      .cp-system-state {
        flex: 0 0 auto;
        display: inline-flex;
        align-items: center;
        gap: .42rem;
        border: 1px solid rgba(5,150,105,.25);
        background: rgba(5,150,105,.08);
        border-radius: 999px;
        padding: .38rem .62rem;
        font-size: .7rem;
        font-weight: 760;
        letter-spacing: .05em;
      }
      .cp-system-dot {
        width: .45rem;
        height: .45rem;
        border-radius: 50%;
        background: var(--cp-green);
        box-shadow: 0 0 0 4px rgba(5,150,105,.1);
      }
      .cp-section-heading {
        display: flex;
        align-items: center;
        gap: .65rem;
        margin: .25rem 0 .75rem 0;
      }
      .cp-section-number {
        display: inline-grid;
        place-items: center;
        width: 1.75rem;
        height: 1.75rem;
        border-radius: .55rem;
        color: white;
        background: #6558e8;
        font-size: .72rem;
        font-weight: 800;
      }
      .cp-section-title {font-size: 1.08rem; font-weight: 760; letter-spacing: -.01em;}
      .cp-section-subtitle {font-size: .75rem; opacity: .62; margin-top: .04rem;}
      .cp-card {
        border: 1px solid var(--cp-border);
        border-radius: .85rem;
        padding: .9rem 1rem;
        margin: .4rem 0 .8rem 0;
      }
      .cp-label {
        font-size: .68rem;
        opacity: .63;
        text-transform: uppercase;
        letter-spacing: .085em;
        font-weight: 720;
      }
      .cp-value {font-size: 1.02rem; font-weight: 650; margin-top: .18rem;}
      .cp-conversation {
        display: grid;
        grid-template-columns: minmax(0, .88fr) 2.2rem minmax(0, 1.12fr);
        align-items: stretch;
        gap: .4rem;
        margin: .35rem 0 .65rem 0;
      }
      .cp-message {
        min-width: 0;
        border: 1px solid var(--cp-border);
        border-radius: .9rem;
        padding: 1rem 1.05rem;
        background: rgba(128,128,128,.025);
      }
      .cp-message-output {
        border-color: rgba(8,145,178,.27);
        background: linear-gradient(130deg, rgba(8,145,178,.075), rgba(99,88,232,.025));
      }
      .cp-message-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: .75rem;
        margin-bottom: .62rem;
      }
      .cp-message-role {font-size: .72rem; font-weight: 760; letter-spacing: .035em;}
      .cp-message-chip {
        border-radius: 999px;
        padding: .16rem .43rem;
        background: rgba(128,128,128,.1);
        font-size: .61rem;
        font-weight: 800;
        letter-spacing: .07em;
        opacity: .7;
      }
      .cp-message-body {
        font-size: .94rem;
        font-weight: 560;
        line-height: 1.56;
        overflow-wrap: anywhere;
        white-space: pre-wrap;
      }
      .cp-message-arrow {
        align-self: center;
        text-align: center;
        color: #6558e8;
        font-size: 1.35rem;
        opacity: .72;
      }
      .cp-context-line {
        display: flex;
        flex-wrap: wrap;
        gap: .35rem;
        align-items: center;
        margin: .35rem 0 .85rem 0;
      }
      .cp-context-chip {
        padding: .22rem .52rem;
        border: 1px solid var(--cp-border);
        border-radius: 999px;
        font-size: .69rem;
        opacity: .72;
      }
      .cp-summary-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .55rem;
        margin: .55rem 0 1rem 0;
      }
      .cp-summary-item {
        min-width: 0;
        border: 1px solid var(--cp-border);
        background: rgba(99,88,232,.035);
        border-radius: .7rem;
        padding: .62rem .72rem;
      }
      .cp-summary-value {
        font-size: .88rem;
        font-weight: 650;
        line-height: 1.3;
        margin-top: .12rem;
        overflow-wrap: anywhere;
      }
      .cp-pill {
        display: inline-block; border-radius: 999px; padding: .2rem .65rem;
        margin: .12rem .18rem .12rem 0; font-size: .78rem; font-weight: 650;
        background: rgba(99,88,232,.1); border: 1px solid rgba(99,88,232,.18);
      }
      .cp-decision {
        position: relative;
        overflow: hidden;
        border-radius: 1rem;
        padding: 1.05rem 1.15rem;
        margin: .55rem 0 .95rem 0;
      }
      .cp-decision::after {
        content: "";
        position: absolute;
        width: 9rem;
        height: 9rem;
        right: -3rem;
        top: -4.8rem;
        border-radius: 50%;
        background: currentColor;
        opacity: .04;
      }
      .cp-decision-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: .75rem;
        margin-bottom: .72rem;
      }
      .cp-decision-state {
        display: inline-flex;
        align-items: center;
        gap: .36rem;
        border: 1px solid currentColor;
        border-radius: 999px;
        padding: .2rem .5rem;
        font-size: .62rem;
        font-weight: 820;
        letter-spacing: .07em;
        opacity: .72;
      }
      .cp-decision-dot {width: .4rem; height: .4rem; border-radius: 50%; background: currentColor;}
      .cp-decision-main {
        display: grid;
        grid-template-columns: minmax(220px, .82fr) minmax(0, 1.18fr);
        gap: 1.2rem;
        align-items: end;
      }
      .cp-decision-word {
        margin-top: .12rem;
        font-size: clamp(1.65rem, 3vw, 2.35rem);
        line-height: 1;
        font-weight: 830;
        letter-spacing: -.045em;
      }
      .cp-decision-copy {margin-top: .48rem; max-width: 520px; font-size: .84rem; line-height: 1.45; opacity: .8;}
      .cp-decision-kpis {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .4rem;
      }
      .cp-decision-kpi {
        min-width: 0;
        border: 1px solid rgba(128,128,128,.17);
        background: rgba(255,255,255,.23);
        border-radius: .66rem;
        padding: .52rem .58rem;
      }
      .cp-decision-kpi-value {font-size: .84rem; font-weight: 760; margin-top: .12rem; overflow-wrap: anywhere;}
      .cp-decision-reason {
        margin-top: .78rem;
        padding-top: .68rem;
        border-top: 1px solid rgba(128,128,128,.16);
        font-size: .79rem;
        line-height: 1.45;
      }
      .cp-route {
        display: grid;
        grid-template-columns: 1fr auto 1fr auto 1fr auto 1fr;
        align-items: stretch;
        gap: .35rem;
        margin: .55rem 0 1rem 0;
      }
      .cp-route-step {
        min-width: 0;
        border: 1px solid var(--cp-border);
        border-radius: .78rem;
        padding: .7rem .75rem;
        background: rgba(128,128,128,.025);
      }
      .cp-route-top {display: flex; align-items: center; justify-content: space-between; gap: .4rem;}
      .cp-route-index {
        display: inline-grid;
        place-items: center;
        width: 1.2rem;
        height: 1.2rem;
        border-radius: .38rem;
        background: rgba(99,88,232,.1);
        color: #6558e8;
        font-size: .6rem;
        font-weight: 820;
      }
      .cp-route-state {font-weight: 780; font-size: .86rem; margin-top: .28rem;}
      .cp-route-detail {font-size: .74rem; opacity: .72; margin-top: .12rem;}
      .cp-route-arrow {align-self: center; color: #6558e8; opacity: .42; font-size: 1.05rem;}
      .cp-route-step[data-state="SKIPPED"], .cp-route-step[data-state="NO CALL"] {opacity: .52; background: transparent;}
      .cp-route-step[data-state="CALLED"] {border-color: rgba(126,34,206,.32); background: rgba(126,34,206,.065);}
      .cp-route-step[data-label="Decision"] {border-color: rgba(8,145,178,.32); background: rgba(8,145,178,.055);}
      .cp-route-note {font-size: .73rem; opacity: .65; margin: -.2rem 0 .45rem 0;}
      .cp-tradeoff {
        display: grid;
        grid-template-columns: .92fr 1.08fr;
        gap: .85rem;
        border: 1px solid var(--cp-border);
        background: rgba(128,128,128,.022);
        border-radius: .85rem;
        padding: .8rem .9rem;
        margin: .4rem 0 .95rem 0;
      }
      .cp-tradeoff-copy {font-size: .78rem; line-height: 1.45; opacity: .74; margin-top: .23rem;}
      .cp-check-head {display: flex; align-items: center; justify-content: space-between; gap: .8rem; margin-top: .2rem;}
      .cp-check-counts {display: flex; flex-wrap: wrap; gap: .65rem; justify-content: flex-end;}
      .cp-count-stat {font-size: .65rem; opacity: .64; white-space: nowrap;}
      .cp-count-stat strong {font-size: .76rem; opacity: 1; margin-right: .12rem;}
      .cp-check-grid {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .45rem; margin: .55rem 0 .95rem 0;}
      .cp-check {
        min-width: 0;
        border: 1px solid var(--cp-border);
        border-radius: .78rem;
        padding: .68rem .72rem;
        background: rgba(128,128,128,.018);
      }
      .cp-check-top {display: flex; align-items: flex-start; justify-content: space-between; gap: .5rem;}
      .cp-check-title {font-size: .76rem; font-weight: 750; line-height: 1.28;}
      .cp-check-status {
        display: inline-flex;
        flex: 0 0 auto;
        align-items: center;
        gap: .22rem;
        border-radius: .4rem;
        padding: .16rem .3rem;
        font-size: .56rem;
        font-weight: 820;
        letter-spacing: .045em;
      }
      .cp-status-mark {
        display: inline-grid;
        place-items: center;
        width: .82rem;
        height: .82rem;
        border-radius: 50%;
        font-size: .58rem;
        font-weight: 900;
      }
      .cp-check[data-status="PASS"] .cp-check-status {color: var(--cp-green); background: rgba(5,150,105,.09);}
      .cp-check[data-status="FAIL"] .cp-check-status {color: var(--cp-red); background: rgba(220,38,38,.085);}
      .cp-check[data-status="UNKNOWN"] .cp-check-status {color: var(--cp-amber); background: rgba(217,119,6,.09);}
      .cp-check[data-status="NOT_APPLICABLE"] .cp-check-status {color: #64748b; background: rgba(100,116,139,.09);}
      .cp-check-metrics {
        display: grid;
        grid-template-columns: .72fr 1.28fr;
        gap: .45rem;
        margin-top: .55rem;
        padding-top: .48rem;
        border-top: 1px solid rgba(128,128,128,.12);
      }
      .cp-check-metric-label {display: block; font-size: .55rem; text-transform: uppercase; letter-spacing: .06em; opacity: .5;}
      .cp-check-metric-value {display: block; margin-top: .12rem; font-size: .64rem; font-weight: 680; overflow-wrap: anywhere;}
      .cp-check-reason {
        border-top: 1px solid rgba(128,128,128,.12);
        font-size: .67rem;
        line-height: 1.42;
        margin-top: .48rem;
        padding-top: .42rem;
        opacity: .76;
      }
      .cp-check-reason-label {font-size: .54rem; font-weight: 800; letter-spacing: .06em; opacity: .62; margin-right: .28rem;}
      .cp-review-panel {
        border: 1px solid rgba(217,119,6,.3);
        border-radius: .85rem;
        background: rgba(217,119,6,.055);
        padding: .9rem 1rem;
        margin: .45rem 0 .85rem 0;
      }
      .cp-review-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: .8rem;
        padding-bottom: .65rem;
        border-bottom: 1px solid rgba(128,128,128,.15);
      }
      .cp-review-title {font-size: 1rem; font-weight: 760; margin-top: .14rem;}
      .cp-review-state {
        flex: 0 0 auto;
        border: 1px solid rgba(217,119,6,.34);
        border-radius: .42rem;
        padding: .2rem .42rem;
        color: var(--cp-amber);
        font-size: .62rem;
        font-weight: 800;
      }
      .cp-review-state[data-status="REVIEWED"] {
        border-color: rgba(5,150,105,.32);
        background: rgba(5,150,105,.08);
        color: var(--cp-green);
      }
      .cp-review-kpis {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .45rem;
        margin-top: .65rem;
      }
      .cp-review-kpi {
        border-top: 1px solid rgba(128,128,128,.18);
        padding-top: .48rem;
        min-width: 0;
      }
      .cp-review-kpi-value {font-size: .74rem; font-weight: 720; margin-top: .12rem; overflow-wrap: anywhere;}
      .cp-review-reason {
        margin-top: .65rem;
        font-size: .78rem;
        line-height: 1.48;
      }
      .cp-good {background: rgba(16,185,129,.11); border: 1px solid rgba(16,185,129,.32);}
      .cp-edit {background: rgba(14,165,233,.11); border: 1px solid rgba(14,165,233,.32);}
      .cp-warn {background: rgba(245,158,11,.12); border: 1px solid rgba(245,158,11,.34);}
      .cp-bad {background: rgba(239,68,68,.11); border: 1px solid rgba(239,68,68,.34);}
      div[data-testid="stDataFrame"] {border: 1px solid rgba(128,128,128,.16); border-radius: .6rem;}
      div[data-testid="stExpander"] {border-color: var(--cp-border); border-radius: .72rem;}
      @media (max-width: 900px) {
        .cp-summary-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .cp-decision-main {grid-template-columns: 1fr;}
        .cp-decision-kpis {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .cp-check-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .cp-review-kpis {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .cp-tradeoff {grid-template-columns: 1fr;}
        .cp-route {grid-template-columns: 1fr;}
        .cp-route-arrow {display: none;}
      }
      @media (max-width: 650px) {
        .block-container {padding-left: .75rem; padding-right: .75rem;}
        .cp-hero-top {display: block;}
        .cp-system-state {margin-top: .75rem;}
        .cp-conversation {grid-template-columns: 1fr;}
        .cp-message-arrow {transform: rotate(90deg);}
        .cp-check-grid {grid-template-columns: 1fr;}
        .cp-summary-grid {grid-template-columns: 1fr;}
        .cp-review-kpis {grid-template-columns: 1fr;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_json(
    method: str,
    path: str,
    *,
    timeout: int = 10,
    **kwargs: Any,
) -> Any:
    try:
        response = requests.request(
            method, f"{API_URL}{path}", timeout=timeout, **kwargs
        )
        response.raise_for_status()
        return response.json()
    except requests.ConnectionError:
        st.error(
            "ControlPlane API is not reachable. Start the demo with "
            "`python scripts/run_demo.py --fresh-db`, then retry."
        )
    except requests.Timeout:
        st.error("The ControlPlane API timed out. Retry or restart the local demo.")
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        detail = ""
        if exc.response is not None:
            try:
                detail = str(exc.response.json().get("detail", ""))
            except (ValueError, AttributeError):
                detail = ""
        st.error(f"The ControlPlane API returned HTTP {status}. {detail}".strip())
    except (requests.RequestException, ValueError):
        st.error("The ControlPlane API returned an unreadable response.")
    st.stop()


@st.cache_data(show_spinner=False)
def load_scenario_payloads(
    file_signatures: tuple[tuple[str, int], ...],
) -> dict[str, dict[str, Any]]:
    """Parse unchanged demo fixtures once instead of on every widget rerun."""
    return {
        path: json.loads(Path(path).read_text(encoding="utf-8"))
        for path, _modified_at in file_signatures
    }


def pill(value: Any) -> str:
    return f'<span class="cp-pill">{html.escape(str(value))}</span>'


def compact_grid(items: list[tuple[str, Any]]) -> str:
    cards = "".join(
        '<div class="cp-summary-item">'
        f'<div class="cp-label">{html.escape(label)}</div>'
        f'<div class="cp-summary-value">{html.escape(str(value))}</div>'
        "</div>"
        for label, value in items
    )
    return f'<div class="cp-summary-grid">{cards}</div>'


def decision_tone(decision: str) -> str:
    return {
        "ALLOW": "cp-good",
        "EDIT_REDACT": "cp-edit",
        "REGENERATE": "cp-warn",
        "ESCALATE": "cp-warn",
        "BLOCK": "cp-bad",
    }.get(decision, "cp-warn")


def checker_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0, "NOT_APPLICABLE": 0}
    for check in checks:
        status = str(check.get("status", "UNKNOWN")).upper()
        counts[status if status in counts else "UNKNOWN"] += 1
    return counts


def render_decision_banner(result: dict[str, Any]) -> None:
    decision = str(result.get("decision", "UNKNOWN"))
    explanation = {
        "ALLOW": "Mandatory checks resolved. The candidate may continue.",
        "EDIT_REDACT": "Localized sensitive data was removed before release.",
        "REGENERATE": "Return this response for correction; do not release this version.",
        "BLOCK": "A policy veto prevents this action from executing.",
        "ESCALATE": "A human decision is required before continuing.",
    }.get(decision, "The middleware returned an unrecognized outcome.")
    checks = result.get("check_results", [])
    counts = checker_counts(checks)
    check_summary = f"{counts['PASS']} passed"
    if counts["FAIL"]:
        check_summary += f" · {counts['FAIL']} failed"
    if counts["UNKNOWN"]:
        check_summary += f" · {counts['UNKNOWN']} unknown"
    latency_ms = float(result.get("latency_ms", 0))
    latency_value = f"{latency_ms:.1f} ms"
    model_calls = int(result.get("model_calls", 0))
    judge_value = (
        "Not needed"
        if model_calls == 0
        else f"{model_calls} live call{'s' if model_calls != 1 else ''}"
    )
    guidance = result.get("action_guidance", {})
    reasons = result.get("reasons", [])
    summary = str(guidance.get("summary") or explanation)
    primary_reason = str(reasons[0]) if reasons else explanation
    st.markdown(
        f'<div class="cp-decision {decision_tone(decision)}">'
        '<div class="cp-decision-head">'
        '<div class="cp-label">Middleware decision</div>'
        '<div class="cp-decision-state"><span class="cp-decision-dot"></span>'
        "VERIFICATION COMPLETE</div></div>"
        '<div class="cp-decision-main"><div>'
        f'<div class="cp-decision-word">{html.escape(decision.replace("_", " "))}</div>'
        f'<div class="cp-decision-copy">{html.escape(summary)}</div></div>'
        '<div class="cp-decision-kpis">'
        '<div class="cp-decision-kpi"><div class="cp-label">Risk</div>'
        f'<div class="cp-decision-kpi-value">{html.escape(str(result.get("risk_profile", {}).get("tier", "—")))}</div></div>'
        '<div class="cp-decision-kpi"><div class="cp-label">Observed latency</div>'
        f'<div class="cp-decision-kpi-value">{html.escape(latency_value)}</div></div>'
        '<div class="cp-decision-kpi"><div class="cp-label">Check outcome</div>'
        f'<div class="cp-decision-kpi-value">{html.escape(check_summary)}</div></div>'
        '<div class="cp-decision-kpi"><div class="cp-label">Groq judge</div>'
        f'<div class="cp-decision-kpi-value">{html.escape(judge_value)}</div></div>'
        "</div></div>"
        '<div class="cp-decision-reason"><span class="cp-label">Primary reason</span><br>'
        f"{html.escape(primary_reason)}</div></div>",
        unsafe_allow_html=True,
    )


def render_adaptive_route(result: dict[str, Any]) -> None:
    st.markdown("#### Verification route")
    st.markdown(
        '<div class="cp-route-note">Local checks run first. Governed evidence and Groq '
        "are used only when earlier stages do not resolve the case.</div>",
        unsafe_allow_html=True,
    )
    stages = verification_route(result)
    parts: list[str] = []
    for index, stage in enumerate(stages):
        if index:
            parts.append('<div class="cp-route-arrow">→</div>')
        parts.append(
            '<div class="cp-route-step" '
            f'data-state="{html.escape(str(stage["state"]))}" '
            f'data-label="{html.escape(str(stage["label"]))}">'
            '<div class="cp-route-top">'
            f'<div class="cp-label">{html.escape(str(stage["label"]))}</div>'
            f'<div class="cp-route-index">{index + 1:02d}</div></div>'
            f'<div class="cp-route-state">{html.escape(str(stage["state"]))}</div>'
            f'<div class="cp-route-detail">{html.escape(str(stage["detail"]))}</div>'
            "</div>"
        )
    st.markdown(
        f'<div class="cp-route">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def render_checker_summary(checks: list[dict[str, Any]]) -> None:
    """Show checker outcomes and surface the exact point of failure."""
    counts = checker_counts(checks)
    st.markdown(
        '<div class="cp-check-head"><div><div class="cp-label">Checker verdicts</div>'
        '<div class="cp-section-title">What passed—and what did not</div></div>'
        '<div class="cp-check-counts">'
        f'<span class="cp-count-stat"><strong>{counts["PASS"]}</strong> passed</span>'
        f'<span class="cp-count-stat"><strong>{counts["FAIL"]}</strong> failed</span>'
        f'<span class="cp-count-stat"><strong>{counts["UNKNOWN"]}</strong> unknown</span>'
        f'<span class="cp-count-stat"><strong>{counts["NOT_APPLICABLE"]}</strong> n/a</span>'
        "</div></div>",
        unsafe_allow_html=True,
    )
    if not checks:
        st.caption("No checker was required for this route.")
        return

    cards: list[str] = []
    status_marks = {
        "PASS": "✓",
        "FAIL": "×",
        "UNKNOWN": "?",
        "NOT_APPLICABLE": "–",
    }
    for check in checks:
        status = str(check.get("status", "UNKNOWN")).upper()
        if status not in counts:
            status = "UNKNOWN"
        name = str(check.get("detector_id", "checker")).replace("_", " ").title()
        evidence = str(check.get("evidence_state", "—")).replace("_", " ").title()
        latency = float(check.get("latency_ms", 0))
        reason = ""
        if status in {"FAIL", "UNKNOWN"} and check.get("reason"):
            reason = (
                '<div class="cp-check-reason"><span class="cp-check-reason-label">'
                "FINDING</span>"
                f"{html.escape(str(check['reason']))}</div>"
            )
        cards.append(
            f'<div class="cp-check" data-status="{html.escape(status)}">'
            '<div class="cp-check-top">'
            f'<div class="cp-check-title">{html.escape(name)}</div>'
            '<div class="cp-check-status">'
            f'<span class="cp-status-mark">{status_marks[status]}</span>'
            f"{html.escape(status.replace('_', ' '))}</div></div>"
            '<div class="cp-check-metrics">'
            '<div><span class="cp-check-metric-label">Latency</span>'
            f'<span class="cp-check-metric-value">{latency:.1f} ms</span></div>'
            '<div><span class="cp-check-metric-label">Evidence state</span>'
            f'<span class="cp-check-metric-value">{html.escape(evidence)}</span></div></div>'
            f"{reason}</div>"
        )
    st.markdown(
        f'<div class="cp-check-grid">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def render_result_overview(result: dict[str, Any]) -> None:
    risk = result.get("risk_profile", {})
    latency_ms = float(result.get("latency_ms", 0))
    model_calls = int(result.get("model_calls", 0))
    route_cost = (
        f"{model_calls} live Groq judge call{'s' if model_calls != 1 else ''}"
        if model_calls
        else "Local and evidence checks only"
    )
    st.markdown("#### Risk and runtime")
    st.markdown(
        '<div class="cp-tradeoff"><div>'
        '<div class="cp-label">Decision context</div>'
        f'<div class="cp-summary-value">{html.escape(str(risk.get("tier", "—")))} risk · '
        f"{int(result.get('checks_executed', 0))} checks</div>"
        '<div class="cp-tradeoff-copy">'
        f"Evidence: {html.escape(str(result.get('evidence_state', '—')).replace('_', ' ').title())} · "
        f"Authorization: {html.escape(str(result.get('authorization_state', '—')).replace('_', ' ').title())}</div>"
        '</div><div><div class="cp-label">Observed runtime</div>'
        f'<div class="cp-summary-value">{latency_ms:.1f} ms</div>'
        f'<div class="cp-tradeoff-copy">{html.escape(route_cost)}</div></div></div>',
        unsafe_allow_html=True,
    )
    stop = str(result.get("stop_reason", "—")).replace("_", " ").title()
    cost = float(result.get("estimated_cost_units", 0))
    st.caption(f"Verification stopped: {stop} · Estimated cost units: {cost:.1f}")

    st.markdown("#### Why this decision")
    reasons = result.get("reasons", [])
    if reasons:
        for reason in reasons:
            st.markdown(f"- {reason}")
    else:
        st.caption("No additional decision reason was recorded.")

    if result.get("sanitized_output") is not None:
        st.markdown("#### Safe output released by ControlPlane")
        st.success(result["sanitized_output"])

    guidance = result.get("action_guidance", {})
    if guidance.get("retryable"):
        exhausted = str(guidance.get("if_retry_exhausted", "ESCALATE")).replace(
            "_", " "
        )
        st.warning(
            f"Retry contract: regenerate at most "
            f"{guidance.get('max_regeneration_attempts', 1)} time. "
            f"If still unresolved: {exhausted}."
        )


def render_human_review_handoff(
    result: dict[str, Any],
    *,
    event: dict[str, Any] | None = None,
    created_at: str | None = None,
    latest_review: dict[str, Any] | None = None,
    key_scope: str = "inline",
) -> None:
    guidance = result.get("action_guidance", {})
    if not guidance.get("human_review_required"):
        return

    evaluation_id = str(result.get("evaluation_id", ""))
    packet = human_review_packet(event or {}, result, created_at=created_at)
    review_status = "REVIEWED" if latest_review else "PENDING REVIEW"
    status_value = "REVIEWED" if latest_review else "PENDING"
    primary_reason = (
        packet["reasons"][0]
        if packet["reasons"]
        else "The middleware requires a human decision before continuing."
    )
    st.markdown("#### Human review handoff")
    st.markdown(
        '<div class="cp-review-panel">'
        '<div class="cp-review-head"><div>'
        '<div class="cp-label">Escalation case</div>'
        f'<div class="cp-review-title">{html.escape(str(packet["title"]))}</div></div>'
        f'<div class="cp-review-state" data-status="{status_value}">{review_status}</div></div>'
        '<div class="cp-review-kpis">'
        '<div class="cp-review-kpi"><div class="cp-label">Risk</div>'
        f'<div class="cp-review-kpi-value">{html.escape(str(packet["risk"]))}</div></div>'
        '<div class="cp-review-kpi"><div class="cp-label">Evidence</div>'
        f'<div class="cp-review-kpi-value">{html.escape(str(packet["evidence_state"]))}</div></div>'
        '<div class="cp-review-kpi"><div class="cp-label">Authorization</div>'
        f'<div class="cp-review-kpi-value">{html.escape(str(packet["authorization_state"]))}</div></div>'
        '<div class="cp-review-kpi"><div class="cp-label">Policy</div>'
        f'<div class="cp-review-kpi-value">{html.escape(str(packet["policy"]))}</div></div>'
        "</div>"
        '<div class="cp-review-reason"><strong>Why it was escalated:</strong> '
        f"{html.escape(primary_reason)}</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="cp-conversation">'
        '<div class="cp-message"><div class="cp-message-head">'
        '<span class="cp-message-role">Original request</span>'
        '<span class="cp-message-chip">HELD CASE</span></div>'
        f'<div class="cp-message-body">{html.escape(str(packet["request"]))}</div></div>'
        '<div class="cp-message-arrow">→</div>'
        '<div class="cp-message cp-message-output"><div class="cp-message-head">'
        f'<span class="cp-message-role">{html.escape(str(packet["candidate_label"]))}</span>'
        '<span class="cp-message-chip">NOT RELEASED</span></div>'
        f'<div class="cp-message-body">{html.escape(str(packet["candidate"]))}</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    if len(packet["reasons"]) > 1:
        st.markdown("**Additional middleware reasons**")
        for reason in packet["reasons"][1:]:
            st.markdown(f"- {reason}")
    if packet["findings"]:
        st.markdown("**Checks requiring reviewer attention**")
        st.dataframe(packet["findings"], width="stretch", hide_index=True)
    judge = packet["judge"]
    if judge is not None:
        st.info(
            f"Groq judge: {judge['status']} / {judge['evidence_state']} / "
            f"{judge['latency_ms']:.1f} ms. {judge['reason']}"
        )
    if latest_review:
        disposition = str(latest_review.get("label", "REVIEWED")).replace("_", " ")
        st.success(
            f"Latest reviewer disposition: {disposition.title()} by "
            f"{latest_review.get('reviewer_id', 'reviewer')} at "
            f"{latest_review.get('created_at', 'the recorded time')}."
        )
    with st.expander("Reviewer context and evidence"):
        st.caption(
            "This packet comes from the redacted event and decision stored by the "
            "middleware audit trail."
        )
        if packet["trusted_context"]:
            st.markdown("**Trusted application context**")
            st.dataframe(
                key_value_rows(packet["trusted_context"]),
                width="stretch",
                hide_index=True,
            )
        if packet["evidence"]:
            st.markdown("**Evidence reviewed by ControlPlane**")
            st.dataframe(packet["evidence"], width="stretch", hide_index=True)
        st.markdown(
            compact_grid(
                [
                    ("Evaluation", packet["evaluation_id"]),
                    ("Event", packet["event_id"]),
                    ("Created", packet["created_at"]),
                    (
                        "Route cost",
                        f"{packet['latency_ms']:.1f} ms / {packet['model_calls']} model calls",
                    ),
                ]
            ),
            unsafe_allow_html=True,
        )

    st.markdown("**Record reviewer disposition**")
    st.caption(
        "The candidate remains held until the host application enforces this disposition."
    )
    outcomes = {
        "Approve candidate": "REVIEW_APPROVE",
        "Return for regeneration": "REVIEW_REGENERATE",
        "Keep blocked": "REVIEW_BLOCK",
    }
    form_key = f"human-review-{key_scope}-{evaluation_id}"
    with st.form(form_key):
        reviewer_id = st.text_input(
            "Reviewer ID",
            "demo-reviewer",
            key=f"reviewer-{key_scope}-{evaluation_id}",
        )
        outcome = st.selectbox(
            "Disposition",
            list(outcomes),
            key=f"outcome-{key_scope}-{evaluation_id}",
        )
        note = st.text_area(
            "Reviewer note", key=f"review-note-{key_scope}-{evaluation_id}"
        )
        submitted = st.form_submit_button(
            "Record reviewer decision", width="stretch"
        )
    if submitted:
        if not reviewer_id.strip() or not note.strip():
            st.error("Reviewer ID and a short reviewer note are required.")
        else:
            api_json(
                "POST",
                "/feedback",
                json={
                    "evaluation_id": evaluation_id,
                    "reviewer_id": reviewer_id,
                    "label": outcomes[outcome],
                    "reason": note,
                },
            )
            st.session_state["review_flash"] = (
                "Reviewer disposition recorded in the audit trail."
            )
            st.rerun()


def render_verification_trace(result: dict[str, Any]) -> None:
    risk = result.get("risk_profile", {})
    checks = result.get("check_results", [])
    references = evidence_rows(checks)
    selected = result.get("checks_selected", [])
    skipped = result.get("checks_skipped", [])
    st.markdown("**Verification route**")
    st.markdown(
        " ".join(pill(item.replace("_", " ").title()) for item in selected)
        if selected
        else "No detector was required for this low-risk route.",
        unsafe_allow_html=True,
    )
    stop = str(result.get("stop_reason", "—")).replace("_", " ").title()
    st.caption(f"Stopped because: {stop}")
    if skipped:
        st.caption(
            "Skipped after the decision was known: "
            + ", ".join(item.replace("_", " ").title() for item in skipped)
        )

    if risk.get("signals") or risk.get("reasons"):
        st.markdown("**Risk assessment**")
        if risk.get("signals"):
            st.markdown(
                " ".join(pill(signal) for signal in risk.get("signals", [])),
                unsafe_allow_html=True,
            )
        for reason in risk.get("reasons", []):
            st.markdown(f"- {reason}")

    st.markdown("**Checks performed**")
    if checks:
        st.dataframe(check_rows(checks), width="stretch", hide_index=True)
    else:
        st.caption("No detector result was recorded.")

    if references:
        st.markdown(f"**Evidence trace ({len(references)} observations)**")
        st.dataframe(references, width="stretch", hide_index=True)


def render_result_footer(result: dict[str, Any]) -> None:
    st.caption(
        f"Policy: {result.get('policy_id', '—')} @ {result.get('policy_version', '—')}  ·  "
        f"Cost units: {float(result.get('estimated_cost_units', 0)):.1f}  ·  "
        f"Evaluation: {result.get('evaluation_id', '—')}"
    )


def render_result(
    result: dict[str, Any],
    *,
    include_raw: bool = True,
    progressive: bool = False,
) -> None:
    render_decision_banner(result)
    render_adaptive_route(result)

    if progressive:
        render_result_overview(result)
        render_checker_summary(result.get("check_results", []))
        with st.expander("More decision details"):
            render_verification_trace(result)
            render_result_footer(result)
    else:
        render_result_overview(result)
        with st.expander("How ControlPlane reached this decision"):
            render_verification_trace(result)
        render_result_footer(result)

    if include_raw:
        with st.expander("Raw decision JSON"):
            st.json(result, expanded=False)


navigation_labels = {
    "Run scenario": "Run scenario",
    "Human review": "Human review",
    "Audit trail": "Audit trail",
    "Policies": "Policies",
    "Metrics": "Metrics",
    "Feedback": "Feedback",
}

brand_column, navigation_column, connection_column = st.columns(
    [1.45, 4.8, 1.05], gap="small", vertical_alignment="center"
)
with brand_column:
    st.markdown(
        '<div class="cp-topbar-brand"><div class="cp-topbar-mark">CP</div><div>'
        '<div class="cp-topbar-product">ControlPlane.ai</div>'
        '<div class="cp-topbar-mode">Stage 2 decision console</div>'
        "</div></div>",
        unsafe_allow_html=True,
    )
with navigation_column:
    page = st.segmented_control(
        "Navigate",
        list(navigation_labels),
        default="Run scenario",
        format_func=navigation_labels.get,
        label_visibility="collapsed",
        width="stretch",
        key="top-navigation-control",
    )
with connection_column:
    with st.popover("Connection", width="stretch"):
        API_URL = st.text_input(
            "Middleware API",
            "http://localhost:8000",
            key="middleware-api-url",
        ).rstrip("/")
        if st.button("Test middleware connection", width="stretch"):
            health = api_json("GET", "/health", timeout=3)
            st.success(
                "API connected" if health.get("status") == "ok" else "API responded"
            )

st.markdown(
    """
    <div class="cp-hero">
      <div class="cp-hero-top">
        <div>
          <h1>Inspect the middleware decision for an AI output.</h1>
          <div class="cp-hero-copy">Each run shows the candidate, risk tier, selected checks,
          evidence, observed latency, and final action before release.</div>
        </div>
        <div class="cp-system-state"><span class="cp-system-dot"></span>STAGE 2 POC</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

review_flash = st.session_state.pop("review_flash", None)
if review_flash:
    st.success(review_flash)

if page == "Run scenario":
    st.subheader("Evaluate a scenario")
    st.caption(
        "Select a prepared case, review its AI candidate, then run ControlPlane verification."
    )
    scenario_paths = sorted((PROJECT_ROOT / "scenarios").glob("**/*.json"))
    scenario_signatures = tuple(
        (str(path), path.stat().st_mtime_ns) for path in scenario_paths
    )
    cached_payloads = load_scenario_payloads(scenario_signatures)
    scenario_payloads = {path: cached_payloads[str(path)] for path in scenario_paths}
    available_groups = {
        label: use_case
        for label, use_case in SCENARIO_GROUPS.items()
        if any(
            payload.get("use_case") == use_case
            for payload in scenario_payloads.values()
        )
    }
    group_column, scenario_column = st.columns([1, 2])
    with group_column:
        selected_group = st.selectbox("Scenario group", list(available_groups))
    grouped_paths = [
        path
        for path, scenario_payload in scenario_payloads.items()
        if scenario_payload.get("use_case") == available_groups[selected_group]
    ]
    with scenario_column:
        selected = st.selectbox(
            "Scenario",
            grouped_paths,
            format_func=lambda path: scenario_meta(path, PROJECT_ROOT)["title"],
        )
    meta = scenario_meta(selected, PROJECT_ROOT)
    payload = scenario_payloads[selected]

    request_key = next(
        (
            key
            for key in ("question", "prompt", "request", "user_input", "input")
            if isinstance(payload.get(key), str) and payload.get(key)
        ),
        None,
    )
    scenario_input = payload.get(request_key) if request_key else meta["prompt"]
    preview = candidate_preview(payload)
    st.markdown(
        '<div class="cp-section-heading"><span class="cp-section-number">01</span><div>'
        '<div class="cp-section-title">AI candidate under review</div>'
        '<div class="cp-section-subtitle">The middleware receives both the original intent and the proposed output.</div>'
        "</div></div>"
        '<div class="cp-conversation">'
        '<div class="cp-message"><div class="cp-message-head">'
        '<span class="cp-message-role">Scenario request</span>'
        '<span class="cp-message-chip">INPUT</span></div>'
        f'<div class="cp-message-body">{html.escape(str(scenario_input))}</div></div>'
        '<div class="cp-message-arrow">→</div>'
        '<div class="cp-message cp-message-output"><div class="cp-message-head">'
        f'<span class="cp-message-role">{html.escape(preview["label"])}</span>'
        '<span class="cp-message-chip">CANDIDATE</span></div>'
        f'<div class="cp-message-body">{html.escape(preview["body"])}</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    use_case_label = (
        str(payload.get("use_case", "unknown"))
        .replace(".", " / ")
        .replace("_", " ")
        .title()
    )
    event_label = str(payload.get("event_type", "unknown")).replace("_", " ").title()
    st.markdown(
        '<div class="cp-context-line"><span class="cp-label">Trusted context</span>'
        f'<span class="cp-context-chip">{html.escape(use_case_label)}</span>'
        f'<span class="cp-context-chip">{html.escape(event_label)}</span></div>',
        unsafe_allow_html=True,
    )

    actor = payload.get("actor", {})
    context = payload.get("trusted_context", {})
    candidate = payload.get("candidate", {})
    with st.expander("More scenario details"):
        st.markdown(f"**Purpose:** {meta['objective']}")
        st.caption(
            f"Expected decision: {meta['expected']} · "
            f"Fixture: {selected.relative_to(PROJECT_ROOT).as_posix()}"
        )
        st.markdown(
            compact_grid(
                [
                    ("Use case", payload.get("use_case", "—")),
                    (
                        "Event",
                        str(payload.get("event_type", "—")).replace("_", " ").title(),
                    ),
                    ("Actor", actor.get("role", actor.get("id", "—"))),
                    ("Environment", context.get("environment", "Customer support")),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.caption(
            "Trusted context comes from the host application, not from the candidate model."
        )
        operation_bits = [candidate.get("tool"), candidate.get("operation")]
        operation_bits = [str(item) for item in operation_bits if item]
        if operation_bits:
            st.markdown(
                " ".join(
                    pill(item.replace("_", " ").title()) for item in operation_bits
                ),
                unsafe_allow_html=True,
            )
        arguments = candidate.get("arguments", {})
        if arguments:
            st.dataframe(
                key_value_rows(arguments), width="stretch", hide_index=True
            )
        claims = candidate.get("claims", [])
        if claims:
            st.markdown(f"**Structured claims ({len(claims)})**")
            st.dataframe(
                [
                    {
                        "Claim": claim.get("key", "—"),
                        "Value": str(claim.get("value", "—")),
                        "Text": claim.get("text", "—"),
                    }
                    for claim in claims
                ],
                width="stretch",
                hide_index=True,
            )
        st.markdown("**Trusted application context**")
        st.dataframe(key_value_rows(context), width="stretch", hide_index=True)

    with st.expander("Raw scenario JSON"):
        st.json(payload, expanded=False)

    if st.button(
        "Run middleware verification", type="primary", width="stretch"
    ):
        evaluation_payload = {
            **payload,
            "metadata": {
                **payload.get("metadata", {}),
                "request_text": scenario_input,
                "scenario_title": meta["title"],
            },
        }
        with st.spinner("Routing through the minimum policy checks required..."):
            result = api_json("POST", "/evaluate", json=evaluation_payload, timeout=20)
        st.session_state["last_result"] = result
        st.session_state["last_scenario"] = str(selected)

    if st.session_state.get("last_scenario") == str(selected):
        st.markdown(
            '<div class="cp-section-heading" style="margin-top:1.15rem;">'
            '<span class="cp-section-number">02</span><div>'
            '<div class="cp-section-title">Middleware verification result</div>'
            '<div class="cp-section-subtitle">Decision, routing cost, and failure point at a glance.</div>'
            "</div></div>",
            unsafe_allow_html=True,
        )
        render_result(
            st.session_state["last_result"],
            progressive=True,
        )

elif page == "Human review":
    st.subheader("Human review queue")
    st.caption(
        "Escalated candidates remain held here with the redacted context a reviewer "
        "needs to record a disposition."
    )
    records = api_json("GET", "/evaluations")
    escalations = [
        record
        for record in records
        if record.get("result", {}).get("decision") == "ESCALATE"
    ]
    feedback = api_json("GET", "/feedback")
    latest_reviews: dict[str, dict[str, Any]] = {}
    for review in feedback:
        if str(review.get("label", "")).startswith("REVIEW_"):
            latest_reviews.setdefault(str(review.get("evaluation_id", "")), review)

    reviewed_count = sum(
        1 for record in escalations if record["evaluation_id"] in latest_reviews
    )
    queue_metrics = st.columns(3)
    queue_metrics[0].metric("Escalated cases", len(escalations))
    queue_metrics[1].metric("Pending review", len(escalations) - reviewed_count)
    queue_metrics[2].metric("Reviewed", reviewed_count)

    if not escalations:
        st.info(
            "No human-review cases are waiting. Run an ESCALATE scenario to create one."
        )
    else:
        queue_view = st.selectbox(
            "Queue view",
            ["Pending", "Reviewed", "All"],
            key="human-review-queue-view",
        )
        visible_escalations = [
            record
            for record in escalations
            if queue_view == "All"
            or (
                queue_view == "Reviewed"
                and record["evaluation_id"] in latest_reviews
            )
            or (
                queue_view == "Pending"
                and record["evaluation_id"] not in latest_reviews
            )
        ]
        if not visible_escalations:
            message = (
                "No pending reviews. Every escalated case has a recorded disposition."
                if queue_view == "Pending"
                else f"No {queue_view.lower()} escalation cases are available."
            )
            if queue_view == "Pending":
                st.success(message)
            else:
                st.info(message)
        else:
            selected_evaluation = st.selectbox(
                "Open escalation case",
                [record["evaluation_id"] for record in visible_escalations],
                format_func=lambda evaluation_id: next(
                    (
                        f"{'Reviewed' if evaluation_id in latest_reviews else 'Pending'} · "
                        f"{record['result'].get('use_case', record['use_case'])} · "
                        f"{evaluation_id[:8]}"
                    )
                    for record in visible_escalations
                    if record["evaluation_id"] == evaluation_id
                ),
            )
            selected_record = next(
                record
                for record in visible_escalations
                if record["evaluation_id"] == selected_evaluation
            )
            render_human_review_handoff(
                selected_record["result"],
                event=selected_record["event"],
                created_at=selected_record.get("created_at"),
                latest_review=latest_reviews.get(selected_evaluation),
                key_scope="queue",
            )
            with st.expander("Raw redacted escalation record"):
                st.json(selected_record, expanded=False)

elif page == "Audit trail":
    st.subheader("Audit trail")
    st.caption(
        "Every decision retains its policy, evidence, checks, stop reason, and redacted input."
    )
    records = api_json("GET", "/evaluations")
    if not records:
        st.info("No audit records yet. Run a scenario first.")
    else:
        overview = [
            {
                "Created": row.get("created_at", "—"),
                "Use case": row["use_case"],
                "Risk": row["risk_tier"],
                "Decision": row["decision"],
                "Policy": f"{row['policy_id']} @ {row['policy_version']}",
                "Replay": "Yes" if row.get("is_replay") else "No",
                "Evaluation ID": row["evaluation_id"],
            }
            for row in records
        ]
        st.dataframe(overview, width="stretch", hide_index=True)
        selected_id = st.selectbox(
            "Inspect evaluation",
            [row["evaluation_id"] for row in records],
            format_func=lambda evaluation_id: next(
                f"{row['decision']} · {row['use_case']} · {evaluation_id[:8]}"
                for row in records
                if row["evaluation_id"] == evaluation_id
            ),
        )
        selected_record = next(
            row for row in records if row["evaluation_id"] == selected_id
        )
        st.markdown("#### Stored decision")
        render_result(selected_record["result"], include_raw=False)
        with st.expander("Redacted audited input"):
            st.json(selected_record["event"], expanded=False)
        with st.expander("Complete audit record"):
            st.json(selected_record, expanded=False)

elif page == "Policies":
    st.subheader("Versioned policy profiles")
    st.caption(
        "Checks, evidence sources, and vetoes vary by AI use case."
    )
    policies = api_json("GET", "/policies")
    if not policies:
        st.info(
            "No policy profiles are available. Check the middleware policy directory "
            "and restart the API."
        )
        st.stop()
    st.dataframe(
        [
            {
                "Policy": policy["policy_id"],
                "Version": policy["version"],
                "Use case": policy["use_case"],
                "Base risk": policy["base_risk"],
                "Fail mode": policy["fail_mode"],
                "Sources": len(policy.get("source_ids", [])),
            }
            for policy in policies
        ],
        width="stretch",
        hide_index=True,
    )
    selected_policy_id = st.selectbox(
        "Inspect policy",
        range(len(policies)),
        format_func=lambda index: (
            f"{policies[index]['policy_id']} @ {policies[index]['version']}"
        ),
    )
    policy = policies[selected_policy_id]
    left, right = st.columns([1.05, 0.95])
    with left:
        st.markdown("#### Checks by risk tier")
        st.dataframe(
            policy_check_rows(policy.get("required_checks", {})),
            width="stretch",
            hide_index=True,
        )
    with right:
        st.markdown("#### Governed evidence")
        st.markdown(
            " ".join(pill(source) for source in policy.get("source_ids", []))
            or "No sources required",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Allowed status: {', '.join(policy.get('allowed_source_statuses', [])) or '—'} · "
            f"Minimum authority: {float(policy.get('minimum_source_authority', 0)):.2f}"
        )
        st.markdown("#### Signal-driven risk")
        st.dataframe(
            [
                {"Signal": signal.replace("_", " ").title(), "Risk": risk}
                for signal, risk in policy.get("signal_risks", {}).items()
            ],
            width="stretch",
            hide_index=True,
        )
    veto_rows = policy_veto_rows(policy.get("veto_rules", []))
    if veto_rows:
        st.markdown("#### Non-negotiable vetoes")
        st.dataframe(veto_rows, width="stretch", hide_index=True)
    with st.expander("Raw policy configuration"):
        st.json(policy, expanded=False)

elif page == "Metrics":
    st.subheader("Operational metrics")
    st.caption("Bounded PoC telemetry from the current local audit database.")
    metrics = api_json("GET", "/metrics")
    top = st.columns(4)
    top[0].metric("Evaluations", metrics["total_evaluations"])
    top[1].metric("Average latency", f"{metrics['average_latency_ms']:.2f} ms")
    top[2].metric("Average checks", f"{metrics['average_checks_executed']:.2f}")
    top[3].metric("External/model calls", metrics["total_model_calls"])
    left, right = st.columns(2)
    with left:
        st.markdown("#### Decisions")
        if metrics["decisions"]:
            st.bar_chart(metrics["decisions"])
        else:
            st.info("Run scenarios to populate decision metrics.")
    with right:
        st.markdown("#### Stopping reasons")
        if metrics["stop_reasons"]:
            st.bar_chart(metrics["stop_reasons"])
        else:
            st.info("No stopping-reason data yet.")
    st.markdown("#### Use-case breakdown")
    use_case_rows = use_case_metric_rows(metrics["by_use_case"])
    if use_case_rows:
        st.dataframe(use_case_rows, width="stretch", hide_index=True)
    else:
        st.caption("No use-case data yet.")
    bottom = st.columns(3)
    bottom[0].metric("Average cost units", f"{metrics['average_cost_units']:.2f}")
    bottom[1].metric("Reviewer feedback", metrics["feedback_count"])
    bottom[2].metric("Feedback categories", len(metrics["feedback_labels"]))
    if metrics["feedback_labels"]:
        st.markdown("#### Feedback labels")
        st.dataframe(
            [
                {"Label": label, "Count": count}
                for label, count in metrics["feedback_labels"].items()
            ],
            width="stretch",
            hide_index=True,
        )

else:
    st.subheader("Reviewer feedback")
    st.caption(
        "Human labels inform offline calibration; they do not silently rewrite policy."
    )
    records = api_json("GET", "/evaluations")
    if not records:
        st.info("Run at least one scenario before recording feedback.")
    else:
        evaluation_id = st.selectbox(
            "Evaluation",
            [record["evaluation_id"] for record in records],
            format_func=lambda record_id: next(
                f"{record['decision']} · {record['use_case']} · {record_id[:8]}"
                for record in records
                if record["evaluation_id"] == record_id
            ),
        )
        reviewer_id = st.text_input("Reviewer ID", "demo-reviewer")
        label = st.selectbox(
            "Label", ["CORRECT", "INCORRECT", "FALSE_POSITIVE", "UNSAFE_ESCAPE"]
        )
        reason = st.text_area(
            "Reason", placeholder="Explain why this label is appropriate."
        )
        if st.button("Record feedback", type="primary", width="stretch"):
            if not reviewer_id.strip() or not reason.strip():
                st.warning(
                    "Reviewer ID and a short reason are required in the demo console."
                )
            else:
                api_json(
                    "POST",
                    "/feedback",
                    json={
                        "evaluation_id": evaluation_id,
                        "reviewer_id": reviewer_id,
                        "label": label,
                        "reason": reason,
                    },
                )
                st.success("Feedback recorded for offline calibration and monitoring.")
