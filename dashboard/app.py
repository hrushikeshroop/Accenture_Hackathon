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
    key_value_rows,
    policy_check_rows,
    policy_veto_rows,
    scenario_meta,
    use_case_metric_rows,
    verification_route,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

st.set_page_config(
    page_title="ControlPlane.ai | Decision Console",
    page_icon="CP",
    layout="wide",
)
st.markdown(
    """
    <style>
      :root {
        --cp-blue: #0f62fe;
        --cp-blue-hover: #0353e9;
        --cp-ink: #161616;
        --cp-muted-ink: #525252;
        --cp-subtle-ink: #6f6f6f;
        --cp-canvas: #ffffff;
        --cp-surface: #f4f4f4;
        --cp-surface-strong: #e0e0e0;
        --cp-border: #d6d6d6;
        --cp-green: #198038;
        --cp-amber: #8e6a00;
        --cp-red: #da1e28;
      }
      html, body, [class*="css"] {
        font-family: "IBM Plex Sans", "Segoe UI", Arial, sans-serif;
        letter-spacing: .01rem;
      }
      .stApp {background: var(--cp-canvas); color: var(--cp-ink); color-scheme: light;}
      ::selection {background: #d0e2ff; color: var(--cp-ink);}
      * {scrollbar-color: #8d8d8d var(--cp-surface); scrollbar-width: thin;}
      #MainMenu, footer {visibility: hidden;}
      header[data-testid="stHeader"] {background: var(--cp-canvas);}
      .block-container {
        max-width: 1200px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
      }
      [data-testid="stSidebar"] {
        border-right: 0;
        color: #f4f4f4;
      }
      [data-testid="stSidebar"] > div:first-child {
        background: var(--cp-ink);
      }
      [data-testid="stSidebarUserContent"] {padding-top: 1.5rem;}
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        line-height: 1.45;
        color: inherit;
      }
      .cp-sidebar-brand {
        display: flex;
        align-items: center;
        gap: .75rem;
        margin: 0 0 1rem 0;
      }
      .cp-sidebar-mark {
        display: grid;
        place-items: center;
        width: 2.5rem;
        height: 2.5rem;
        background: var(--cp-blue);
        color: #ffffff;
        font-size: .75rem;
        font-weight: 700;
      }
      .cp-sidebar-product {font-size: .95rem; font-weight: 600; line-height: 1.2;}
      .cp-sidebar-mode {font-size: .72rem; color: #c6c6c6; margin-top: .16rem;}
      .cp-sidebar-intro {
        border-top: 1px solid #393939;
        border-bottom: 1px solid #393939;
        padding: .8rem 0;
        margin: 0 0 1.25rem 0;
        color: #c6c6c6;
        font-size: .72rem;
        line-height: 1.5;
      }
      .cp-sidebar-nav-label {margin: 0 0 .45rem 0; color: #c6c6c6;}
      [data-testid="stSidebar"] [data-testid="stRadio"] > label {display: none;}
      [data-testid="stSidebar"] div[role="radiogroup"] {gap: 0;}
      [data-testid="stSidebar"] div[role="radiogroup"] label {
        min-height: 3rem;
        border: 0;
        border-bottom: 1px solid #393939;
        border-radius: 0;
        padding: .7rem .75rem;
        color: #f4f4f4;
        transition: background-color .12s ease;
      }
      [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: #262626;
      }
      [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: var(--cp-blue);
        color: #ffffff;
      }
      [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
        display: none;
      }
      [data-testid="stSidebar"] div[role="radiogroup"] label p {
        font-size: .8rem;
        font-weight: 500;
        color: inherit !important;
      }
      .cp-sidebar-route {
        border-top: 1px solid #525252;
        padding-top: .9rem;
        margin-top: .9rem;
      }
      .cp-sidebar-route-nodes {
        display: grid;
        grid-template-columns: 1fr auto;
        margin-top: .55rem;
      }
      .cp-sidebar-node {
        border-bottom: 1px solid #393939;
        padding: .42rem 0;
        color: #f4f4f4;
        font-size: .7rem;
        font-weight: 500;
      }
      .cp-sidebar-node-value {
        border-bottom: 1px solid #393939;
        padding: .42rem 0;
        color: #a8a8a8;
        font-size: .68rem;
        text-align: right;
      }
      .cp-sidebar-route-copy {font-size: .68rem; line-height: 1.45; color: #a8a8a8; margin-top: .65rem;}
      [data-testid="stSidebar"] hr {border-color: #393939;}
      [data-testid="stSidebar"] details {border-radius: 0 !important; border-color: #525252 !important;}
      [data-testid="stSidebar"] details summary,
      [data-testid="stSidebar"] label {color: #f4f4f4 !important;}
      [data-testid="stSidebar"] input {
        background: #262626;
        border-color: #6f6f6f;
        color: #f4f4f4;
      }
      [data-testid="stSidebar"] button:not([kind="primary"]) {
        border-color: #6f6f6f;
        border-radius: 0;
        background: #262626;
        color: #f4f4f4;
      }
      [data-testid="stMetric"] {
        background: var(--cp-surface);
        border-top: 2px solid var(--cp-blue);
        border-radius: 0;
        padding: .8rem 1rem;
      }
      .stButton > button[kind="primary"] {
        min-height: 3.05rem;
        border: 0;
        border-radius: 0;
        background: var(--cp-blue);
        box-shadow: none;
        font-weight: 600;
      }
      .stButton > button[kind="primary"]:hover {
        background: var(--cp-blue-hover);
        box-shadow: none;
      }
      .cp-hero {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 2rem;
        border-bottom: 1px solid var(--cp-border);
        padding: .5rem 0 1.25rem 0;
        margin-bottom: 1.5rem;
      }
      .cp-hero h1 {
        margin: 0 0 .35rem 0;
        font-size: clamp(1.7rem, 2.5vw, 2.3rem);
        line-height: 1.12;
        letter-spacing: -.025em;
        font-weight: 600;
      }
      .cp-hero-copy {max-width: 72ch; color: var(--cp-muted-ink); line-height: 1.5;}
      .cp-system-state {
        flex: 0 0 14rem;
        border-left: 1px solid var(--cp-border);
        padding-left: 1rem;
        color: var(--cp-muted-ink);
        font-size: .72rem;
        line-height: 1.5;
      }
      .cp-system-state strong {display: block; color: var(--cp-ink); font-size: .8rem; font-weight: 600;}
      .cp-hero-tags {margin-top: .65rem; color: var(--cp-subtle-ink); font-size: .7rem;}
      .cp-hero-tag {
        display: inline;
      }
      .cp-hero-tag + .cp-hero-tag::before {content: " / "; color: #8d8d8d;}
      .cp-section-heading {
        margin: .4rem 0 .8rem 0;
      }
      .cp-section-title {font-size: 1.05rem; font-weight: 600; letter-spacing: -.01em;}
      .cp-section-subtitle {font-size: .76rem; color: var(--cp-muted-ink); margin-top: .16rem;}
      .cp-card {
        border: 1px solid var(--cp-border);
        padding: .9rem 1rem;
        margin: .4rem 0 .8rem 0;
      }
      .cp-label {
        font-size: .7rem;
        color: var(--cp-muted-ink);
        font-weight: 500;
      }
      .cp-value {font-size: 1.02rem; font-weight: 650; margin-top: .18rem;}
      .cp-conversation {
        display: grid;
        grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr);
        align-items: stretch;
        border: 1px solid var(--cp-border);
        margin: .35rem 0 .75rem 0;
      }
      .cp-message {
        min-width: 0;
        padding: 1rem 1.1rem 1.15rem;
        background: var(--cp-canvas);
      }
      .cp-message-output {
        border-left: 1px solid var(--cp-border);
        background: var(--cp-surface);
      }
      .cp-message-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: .75rem;
        margin-bottom: .7rem;
      }
      .cp-message-role {font-size: .75rem; font-weight: 600;}
      .cp-message-chip {
        color: var(--cp-subtle-ink);
        font-size: .65rem;
        font-weight: 500;
      }
      .cp-message-body {
        max-width: 72ch;
        font-size: .92rem;
        font-weight: 400;
        line-height: 1.58;
        overflow-wrap: anywhere;
        white-space: pre-wrap;
      }
      .cp-context-line {
        display: flex;
        flex-wrap: wrap;
        gap: .7rem;
        align-items: center;
        margin: .35rem 0 .85rem 0;
      }
      .cp-context-chip {
        border-left: 1px solid var(--cp-border);
        padding-left: .7rem;
        color: var(--cp-muted-ink);
        font-size: .7rem;
      }
      .cp-summary-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        border-top: 1px solid var(--cp-border);
        border-bottom: 1px solid var(--cp-border);
        margin: .55rem 0 1rem 0;
      }
      .cp-summary-item {
        min-width: 0;
        padding: .7rem .75rem;
      }
      .cp-summary-item + .cp-summary-item {border-left: 1px solid var(--cp-border);}
      .cp-summary-value {
        font-size: .88rem;
        font-weight: 650;
        line-height: 1.3;
        margin-top: .12rem;
        overflow-wrap: anywhere;
      }
      .cp-pill {
        display: inline-block; padding: .2rem .45rem;
        margin: .12rem .18rem .12rem 0; font-size: .72rem; font-weight: 500;
        background: var(--cp-surface); border: 1px solid var(--cp-border);
      }
      .cp-decision {
        --cp-state: var(--cp-blue);
        border: 1px solid var(--cp-border);
        padding: 0;
        margin: .55rem 0 .95rem 0;
      }
      .cp-decision-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: .75rem;
        background: var(--cp-surface);
        border-bottom: 1px solid var(--cp-border);
        padding: .65rem .85rem;
      }
      .cp-decision-state {
        color: var(--cp-state);
        font-size: .68rem;
        font-weight: 600;
      }
      .cp-decision-main {
        display: grid;
        grid-template-columns: minmax(230px, .75fr) minmax(0, 1.25fr);
        align-items: stretch;
      }
      .cp-decision-main > div:first-child {padding: 1.05rem 1.15rem;}
      .cp-decision-word {
        color: var(--cp-state);
        font-size: clamp(1.6rem, 3vw, 2.25rem);
        line-height: 1.05;
        font-weight: 600;
        letter-spacing: -.025em;
      }
      .cp-decision-copy {margin-top: .48rem; max-width: 520px; font-size: .84rem; line-height: 1.45; opacity: .8;}
      .cp-decision-kpis {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        border-left: 1px solid var(--cp-border);
      }
      .cp-decision-kpi {
        min-width: 0;
        padding: 1rem .7rem;
      }
      .cp-decision-kpi + .cp-decision-kpi {border-left: 1px solid var(--cp-border);}
      .cp-decision-kpi-value {font-size: .84rem; font-weight: 760; margin-top: .12rem; overflow-wrap: anywhere;}
      .cp-decision-reason {
        padding: .75rem 1.15rem;
        border-top: 1px solid var(--cp-border);
        font-size: .79rem;
        line-height: 1.45;
      }
      .cp-route {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        align-items: stretch;
        border: 1px solid var(--cp-border);
        margin: .55rem 0 1rem 0;
      }
      .cp-route-step {
        min-width: 0;
        padding: .75rem .85rem;
      }
      .cp-route-step + .cp-route-step {border-left: 1px solid var(--cp-border);}
      .cp-route-state {font-weight: 600; font-size: .86rem; margin-top: .3rem;}
      .cp-route-detail {font-size: .74rem; opacity: .72; margin-top: .12rem;}
      .cp-route-step[data-state="SKIPPED"], .cp-route-step[data-state="NO CALL"] {color: var(--cp-subtle-ink); background: var(--cp-surface);}
      .cp-route-step[data-state="CALLED"] .cp-route-state {color: var(--cp-blue);}
      .cp-route-step[data-label="Decision"] .cp-route-state {color: var(--cp-blue);}
      .cp-route-note {font-size: .73rem; opacity: .65; margin: -.2rem 0 .45rem 0;}
      .cp-tradeoff {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        border: 1px solid var(--cp-border);
        margin: .4rem 0 .95rem 0;
      }
      .cp-tradeoff-block {padding: .8rem .9rem;}
      .cp-tradeoff-block + .cp-tradeoff-block {border-left: 1px solid var(--cp-border);}
      .cp-tradeoff-copy {font-size: .78rem; line-height: 1.45; opacity: .74; margin-top: .23rem;}
      .cp-tradeoff-value {font-size: .95rem; font-weight: 600; margin-top: .2rem;}
      .cp-check-head {display: flex; align-items: center; justify-content: space-between; gap: .8rem; margin-top: .2rem;}
      .cp-check-counts {display: flex; flex-wrap: wrap; gap: .65rem; justify-content: flex-end;}
      .cp-count-stat {font-size: .68rem; color: var(--cp-muted-ink); white-space: nowrap;}
      .cp-count-stat strong {font-size: .78rem; color: var(--cp-ink); margin-right: .12rem;}
      .cp-check-grid {border: 1px solid var(--cp-border); margin: .55rem 0 .95rem 0;}
      .cp-check-header {
        background: var(--cp-surface);
        padding-top: .48rem;
        padding-bottom: .48rem;
      }
      .cp-check {
        display: grid;
        grid-template-columns: 6.2rem minmax(9rem, 1fr) 5rem minmax(7rem, .8fr) minmax(12rem, 1.35fr);
        align-items: center;
        min-width: 0;
        padding: .68rem .7rem;
      }
      .cp-check + .cp-check {border-top: 1px solid var(--cp-border);}
      .cp-check-title {font-size: .76rem; font-weight: 600; line-height: 1.3;}
      .cp-check-status {
        font-size: .64rem;
        font-weight: 600;
      }
      .cp-check[data-status="PASS"] .cp-check-status {color: var(--cp-green);}
      .cp-check[data-status="FAIL"] .cp-check-status {color: var(--cp-red);}
      .cp-check[data-status="UNKNOWN"] .cp-check-status {color: var(--cp-amber);}
      .cp-check[data-status="NOT_APPLICABLE"] .cp-check-status {color: var(--cp-subtle-ink);}
      .cp-check-metric-value {font-size: .7rem; color: var(--cp-muted-ink); overflow-wrap: anywhere;}
      .cp-check-latency, .cp-check-evidence {font-variant-numeric: tabular-nums;}
      .cp-check-reason {
        font-size: .7rem;
        line-height: 1.42;
        color: var(--cp-muted-ink);
      }
      .cp-check-reason-empty {color: var(--cp-subtle-ink);}
      .cp-good {--cp-state: var(--cp-green);}
      .cp-edit {--cp-state: var(--cp-blue);}
      .cp-warn {--cp-state: var(--cp-amber);}
      .cp-bad {--cp-state: var(--cp-red);}
      div[data-testid="stDataFrame"] {border: 1px solid var(--cp-border); border-radius: 0;}
      div[data-testid="stExpander"] {border-color: var(--cp-border); border-radius: 0;}
      a {text-underline-offset: .18rem;}
      button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {
        outline: 2px solid var(--cp-blue) !important;
        outline-offset: 2px;
      }
      @media (max-width: 900px) {
        .cp-summary-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .cp-decision-main {grid-template-columns: 1fr;}
        .cp-decision-kpis {border-left: 0; border-top: 1px solid var(--cp-border);}
        .cp-decision-kpis {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .cp-tradeoff {grid-template-columns: 1fr;}
        .cp-tradeoff-block + .cp-tradeoff-block {border-left: 0; border-top: 1px solid var(--cp-border);}
        .cp-check-header {display: none;}
        .cp-check {
          grid-template-columns: 6rem minmax(8rem, 1fr) 5rem minmax(7rem, .8fr);
          grid-template-areas:
            "status title latency evidence"
            "reason reason reason reason";
          gap: .5rem;
        }
        .cp-check-status {grid-area: status;}
        .cp-check-title {grid-area: title;}
        .cp-check-latency {grid-area: latency;}
        .cp-check-evidence {grid-area: evidence;}
        .cp-check-reason {grid-area: reason; border-top: 1px solid var(--cp-border); padding-top: .45rem;}
      }
      @media (max-width: 650px) {
        .cp-hero {display: block;}
        .cp-system-state {border-left: 0; border-top: 1px solid var(--cp-border); margin-top: .9rem; padding: .75rem 0 0;}
        .cp-conversation {grid-template-columns: 1fr;}
        .cp-message-output {border-left: 0; border-top: 1px solid var(--cp-border);}
        .cp-route {grid-template-columns: 1fr 1fr;}
        .cp-route-step:nth-child(3) {border-left: 0; border-top: 1px solid var(--cp-border);}
        .cp-route-step:nth-child(4) {border-top: 1px solid var(--cp-border);}
        .cp-summary-grid {grid-template-columns: 1fr;}
        .cp-summary-item + .cp-summary-item {border-left: 0; border-top: 1px solid var(--cp-border);}
        .cp-check {
          grid-template-columns: 1fr 1fr;
          grid-template-areas:
            "title title"
            "status latency"
            "evidence evidence"
            "reason reason";
        }
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
        check_summary += f" / {counts['FAIL']} failed"
    if counts["UNKNOWN"]:
        check_summary += f" / {counts['UNKNOWN']} unknown"
    latency_ms = float(result.get("latency_ms", 0))
    budget_ms = float(result.get("latency_budget_ms", 0))
    latency_value = f"{latency_ms:.1f} ms"
    if budget_ms > 0:
        latency_value = f"{latency_ms:.1f} / {budget_ms:.0f} ms"
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
        '<div class="cp-decision-state">Verification complete</div></div>'
        '<div class="cp-decision-main"><div>'
        f'<div class="cp-decision-word">{html.escape(decision.replace("_", " "))}</div>'
        f'<div class="cp-decision-copy">{html.escape(summary)}</div></div>'
        '<div class="cp-decision-kpis">'
        '<div class="cp-decision-kpi"><div class="cp-label">Risk</div>'
        f'<div class="cp-decision-kpi-value">{html.escape(str(result.get("risk_profile", {}).get("tier", "Not available")))}</div></div>'
        '<div class="cp-decision-kpi"><div class="cp-label">Latency / budget</div>'
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
        '<div class="cp-route-note">Fail fast locally, add governed evidence when needed, '
        "and pay for the live judge only when uncertainty remains.</div>",
        unsafe_allow_html=True,
    )
    stages = verification_route(result)
    parts: list[str] = []
    for stage in stages:
        parts.append(
            '<div class="cp-route-step" '
            f'data-state="{html.escape(str(stage["state"]))}" '
            f'data-label="{html.escape(str(stage["label"]))}">'
            f'<div class="cp-label">{html.escape(str(stage["label"]))}</div>'
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
        '<div class="cp-section-title">What passed and what did not</div></div>'
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

    rows: list[str] = []
    for check in checks:
        status = str(check.get("status", "UNKNOWN")).upper()
        if status not in counts:
            status = "UNKNOWN"
        name = str(check.get("detector_id", "checker")).replace("_", " ").title()
        evidence = (
            str(check.get("evidence_state", "Not available")).replace("_", " ").title()
        )
        latency = float(check.get("latency_ms", 0))
        reason = (
            '<div class="cp-check-reason cp-check-reason-empty">No issue recorded</div>'
        )
        if status in {"FAIL", "UNKNOWN"} and check.get("reason"):
            reason = (
                '<div class="cp-check-reason">'
                f"{html.escape(str(check['reason']))}</div>"
            )
        rows.append(
            f'<div class="cp-check" data-status="{html.escape(status)}">'
            '<div class="cp-check-status">'
            f"{html.escape(status.replace('_', ' '))}</div>"
            f'<div class="cp-check-title">{html.escape(name)}</div>'
            f'<div class="cp-check-metric-value cp-check-latency">{latency:.1f} ms</div>'
            '<div class="cp-check-metric-value cp-check-evidence">'
            f"{html.escape(evidence)}</div>"
            f"{reason}</div>"
        )
    st.markdown(
        '<div class="cp-check-grid">'
        '<div class="cp-check cp-check-header">'
        '<div class="cp-label">Verdict</div>'
        '<div class="cp-label">Checker</div>'
        '<div class="cp-label">Latency</div>'
        '<div class="cp-label">Evidence</div>'
        '<div class="cp-label">Finding</div></div>'
        f"{''.join(rows)}</div>",
        unsafe_allow_html=True,
    )


def render_result_overview(result: dict[str, Any]) -> None:
    risk = result.get("risk_profile", {})
    latency_ms = float(result.get("latency_ms", 0))
    latency_budget_ms = float(result.get("latency_budget_ms", 0))
    budget_used = (
        latency_ms / latency_budget_ms * 100 if latency_budget_ms > 0 else None
    )
    budget_label = "No policy budget"
    budget_caption = f"Observed latency: {latency_ms:.1f} ms"
    budget_status = "No policy budget"
    if budget_used is not None:
        budget_label = f"{latency_ms:.1f} of {latency_budget_ms:.0f} ms"
        budget_caption = f"{budget_used:.1f}% used / " + (
            "within policy budget" if budget_used <= 100 else "policy budget exceeded"
        )
        budget_status = "Within budget" if budget_used <= 100 else "Budget exceeded"
    model_calls = int(result.get("model_calls", 0))
    tradeoff_copy = (
        f"Uncertainty required {model_calls} live Groq judge "
        f"call{'s' if model_calls != 1 else ''}."
        if model_calls
        else "No live judge call was needed; the route stopped when policy had enough signal."
    )
    st.markdown("#### Risk versus latency")
    st.markdown(
        '<div class="cp-tradeoff">'
        '<div class="cp-tradeoff-block"><div class="cp-label">Risk route</div>'
        f'<div class="cp-tradeoff-value">{html.escape(str(risk.get("tier", "Not available")))} risk</div>'
        f'<div class="cp-tradeoff-copy">{int(result.get("checks_executed", 0))} checks / '
        f"Evidence {html.escape(str(result.get('evidence_state', 'Not available')).replace('_', ' ').title())} / "
        f"Authorization {html.escape(str(result.get('authorization_state', 'Not available')).replace('_', ' ').title())}</div></div>"
        '<div class="cp-tradeoff-block"><div class="cp-label">Observed latency</div>'
        f'<div class="cp-tradeoff-value">{html.escape(budget_label)}</div>'
        f'<div class="cp-tradeoff-copy">{html.escape(budget_status)} / {html.escape(budget_caption)}</div></div>'
        '<div class="cp-tradeoff-block"><div class="cp-label">External judge usage</div>'
        f'<div class="cp-tradeoff-value">{model_calls} live call{"s" if model_calls != 1 else ""}</div>'
        f'<div class="cp-tradeoff-copy">{html.escape(tradeoff_copy)}</div></div></div>',
        unsafe_allow_html=True,
    )
    stop = str(result.get("stop_reason", "Not available")).replace("_", " ").title()
    cost = float(result.get("estimated_cost_units", 0))
    st.caption(f"Verification stopped: {stop} / Estimated cost units: {cost:.1f}")

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


def render_human_review_handoff(result: dict[str, Any]) -> None:
    guidance = result.get("action_guidance", {})
    if not guidance.get("human_review_required"):
        return

    evaluation_id = str(result.get("evaluation_id", ""))
    with st.expander("Human review handoff"):
        st.caption(
            "The candidate remains on hold. This records a reviewer outcome in the "
            "existing feedback and audit store; it does not silently release the candidate."
        )
        with st.form(f"human-review-{evaluation_id}"):
            reviewer_id = st.text_input(
                "Reviewer ID", "demo-reviewer", key=f"reviewer-{evaluation_id}"
            )
            outcome = st.selectbox(
                "Review outcome",
                ["Confirm escalation", "Override decision", "False positive"],
                key=f"outcome-{evaluation_id}",
            )
            note = st.text_area("Reviewer note", key=f"review-note-{evaluation_id}")
            submitted = st.form_submit_button(
                "Record review outcome", use_container_width=True
            )
        if submitted:
            if not reviewer_id.strip() or not note.strip():
                st.error("Reviewer ID and a short reviewer note are required.")
            else:
                label = {
                    "Confirm escalation": "CORRECT",
                    "Override decision": "INCORRECT",
                    "False positive": "FALSE_POSITIVE",
                }[outcome]
                api_json(
                    "POST",
                    "/feedback",
                    json={
                        "evaluation_id": evaluation_id,
                        "reviewer_id": reviewer_id,
                        "label": label,
                        "reason": note,
                    },
                )
                st.success("Reviewer outcome recorded in the audit trail.")


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
    stop = str(result.get("stop_reason", "Not available")).replace("_", " ").title()
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
        st.dataframe(check_rows(checks), use_container_width=True, hide_index=True)
    else:
        st.caption("No detector result was recorded.")

    if references:
        st.markdown(f"**Evidence trace ({len(references)} observations)**")
        st.dataframe(references, use_container_width=True, hide_index=True)


def render_result_footer(result: dict[str, Any]) -> None:
    st.caption(
        f"Policy: {result.get('policy_id', 'Not available')} @ "
        f"{result.get('policy_version', 'Not available')} / "
        f"Cost units: {float(result.get('estimated_cost_units', 0)):.1f} / "
        f"Evaluation: {result.get('evaluation_id', 'Not available')}"
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
        render_human_review_handoff(result)
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
    "Audit trail": "Audit trail",
    "Policies": "Policies",
    "Metrics": "Metrics",
    "Feedback": "Feedback",
}

with st.sidebar:
    st.markdown(
        '<div class="cp-sidebar-brand">'
        '<div class="cp-sidebar-mark">CP</div><div>'
        '<div class="cp-sidebar-product">ControlPlane.ai</div>'
        '<div class="cp-sidebar-mode">Decision console / proof of concept</div>'
        "</div></div>"
        '<div class="cp-sidebar-intro">Inspect how each AI candidate is routed, '
        "verified, decided, and preserved for audit.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="cp-sidebar-nav-label cp-label">Console</div>',
        unsafe_allow_html=True,
    )
    page = st.radio(
        "Navigate",
        list(navigation_labels),
        format_func=navigation_labels.get,
        label_visibility="collapsed",
    )
    st.divider()
    with st.expander("Connection settings"):
        API_URL = st.text_input(
            "Middleware API", "http://localhost:8000", label_visibility="collapsed"
        ).rstrip("/")
        if st.button("Test middleware connection", use_container_width=True):
            health = api_json("GET", "/health", timeout=3)
            st.success(
                "API connected" if health.get("status") == "ok" else "API responded"
            )
    st.markdown(
        '<div class="cp-sidebar-route"><div class="cp-label">Verification strategy</div>'
        '<div class="cp-sidebar-route-nodes">'
        '<span class="cp-sidebar-node">Local checks</span><span class="cp-sidebar-node-value">First</span>'
        '<span class="cp-sidebar-node">Governed evidence</span><span class="cp-sidebar-node-value">When required</span>'
        '<span class="cp-sidebar-node">Groq judge</span><span class="cp-sidebar-node-value">Fallback</span></div>'
        '<div class="cp-sidebar-route-copy">The route stops as soon as policy has enough signal. '
        "The live judge is a fallback, not the default.</div></div>",
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="cp-hero">
      <div>
        <h1>AI verification console</h1>
        <div class="cp-hero-copy">Inspect how ControlPlane evaluates an AI candidate against risk,
        policy, evidence, and authorization before release or execution.</div>
        <div class="cp-hero-tags">
          <span class="cp-hero-tag">Risk-adaptive routing</span>
          <span class="cp-hero-tag">Governed evidence</span>
          <span class="cp-hero-tag">Live Groq fallback</span>
        </div>
      </div>
      <div class="cp-system-state"><strong>Stage 2 proof of concept</strong>
      Decision, latency, and failure evidence in one view.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if page == "Run scenario":
    st.subheader("Decision walkthrough")
    st.caption(
        "Choose a prepared case, inspect the AI candidate, then watch the middleware route it."
    )
    scenario_paths = sorted((PROJECT_ROOT / "scenarios").glob("**/*.json"))
    selected = st.selectbox(
        "Choose a scenario",
        scenario_paths,
        format_func=lambda path: scenario_meta(path, PROJECT_ROOT)["title"],
    )
    meta = scenario_meta(selected, PROJECT_ROOT)
    payload = json.loads(selected.read_text(encoding="utf-8"))

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
        '<div class="cp-section-heading"><div>'
        '<div class="cp-section-title">AI candidate under review</div>'
        '<div class="cp-section-subtitle">The middleware receives both the original intent and the proposed output.</div>'
        "</div></div>"
        '<div class="cp-conversation">'
        '<div class="cp-message"><div class="cp-message-head">'
        '<span class="cp-message-role">Scenario request</span>'
        '<span class="cp-message-chip">Scenario</span></div>'
        f'<div class="cp-message-body">{html.escape(str(scenario_input))}</div></div>'
        '<div class="cp-message cp-message-output"><div class="cp-message-head">'
        f'<span class="cp-message-role">{html.escape(preview["label"])}</span>'
        '<span class="cp-message-chip">Candidate</span></div>'
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
            f"Expected decision: {meta['expected']} / "
            f"Fixture: {selected.relative_to(PROJECT_ROOT).as_posix()}"
        )
        st.markdown(
            compact_grid(
                [
                    ("Use case", payload.get("use_case", "Not available")),
                    (
                        "Event",
                        str(payload.get("event_type", "Not available"))
                        .replace("_", " ")
                        .title(),
                    ),
                    (
                        "Actor",
                        actor.get("role", actor.get("id", "Not available")),
                    ),
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
                key_value_rows(arguments), use_container_width=True, hide_index=True
            )
        claims = candidate.get("claims", [])
        if claims:
            st.markdown(f"**Structured claims ({len(claims)})**")
            st.dataframe(
                [
                    {
                        "Claim": claim.get("key", "Not available"),
                        "Value": str(claim.get("value", "Not available")),
                        "Text": claim.get("text", "Not available"),
                    }
                    for claim in claims
                ],
                use_container_width=True,
                hide_index=True,
            )
        st.markdown("**Trusted application context**")
        st.dataframe(key_value_rows(context), use_container_width=True, hide_index=True)

    with st.expander("Raw scenario JSON"):
        st.json(payload, expanded=False)

    if st.button(
        "Run middleware verification", type="primary", use_container_width=True
    ):
        with st.spinner("Routing through the minimum policy checks required..."):
            result = api_json("POST", "/evaluate", json=payload, timeout=20)
        st.session_state["last_result"] = result
        st.session_state["last_scenario"] = str(selected)

    if st.session_state.get("last_scenario") == str(selected):
        st.markdown(
            '<div class="cp-section-heading" style="margin-top:1.15rem;">'
            "<div>"
            '<div class="cp-section-title">Middleware verification result</div>'
            '<div class="cp-section-subtitle">Decision, routing cost, and failure point at a glance.</div>'
            "</div></div>",
            unsafe_allow_html=True,
        )
        render_result(st.session_state["last_result"], progressive=True)

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
                "Created": row.get("created_at", "Not available"),
                "Use case": row["use_case"],
                "Risk": row["risk_tier"],
                "Decision": row["decision"],
                "Policy": f"{row['policy_id']} @ {row['policy_version']}",
                "Replay": "Yes" if row.get("is_replay") else "No",
                "Evaluation ID": row["evaluation_id"],
            }
            for row in records
        ]
        st.dataframe(overview, use_container_width=True, hide_index=True)
        selected_id = st.selectbox(
            "Inspect evaluation",
            [row["evaluation_id"] for row in records],
            format_func=lambda evaluation_id: next(
                f"{row['decision']} / {row['use_case']} / {evaluation_id[:8]}"
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
        "One middleware engine; different checks, budgets, sources, and vetoes per AI use case."
    )
    policies = api_json("GET", "/policies")
    st.dataframe(
        [
            {
                "Policy": policy["policy_id"],
                "Version": policy["version"],
                "Use case": policy["use_case"],
                "Base risk": policy["base_risk"],
                "Latency budget (ms)": policy["latency_budget_ms"],
                "Fail mode": policy["fail_mode"],
                "Sources": len(policy.get("source_ids", [])),
            }
            for policy in policies
        ],
        use_container_width=True,
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
            use_container_width=True,
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
            f"Allowed status: {', '.join(policy.get('allowed_source_statuses', [])) or 'Not available'} / "
            f"Minimum authority: {float(policy.get('minimum_source_authority', 0)):.2f}"
        )
        st.markdown("#### Signal-driven risk")
        st.dataframe(
            [
                {"Signal": signal.replace("_", " ").title(), "Risk": risk}
                for signal, risk in policy.get("signal_risks", {}).items()
            ],
            use_container_width=True,
            hide_index=True,
        )
    veto_rows = policy_veto_rows(policy.get("veto_rules", []))
    if veto_rows:
        st.markdown("#### Non-negotiable vetoes")
        st.dataframe(veto_rows, use_container_width=True, hide_index=True)
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
        st.dataframe(use_case_rows, use_container_width=True, hide_index=True)
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
            use_container_width=True,
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
                f"{record['decision']} / {record['use_case']} / {record_id[:8]}"
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
        if st.button("Record feedback", type="primary", use_container_width=True):
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
