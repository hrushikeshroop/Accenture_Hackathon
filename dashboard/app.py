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
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

st.set_page_config(page_title="ControlPlane.ai", page_icon="CP", layout="wide")
st.markdown(
    """
    <style>
      .block-container {max-width: 1280px; padding-top: 1.7rem; padding-bottom: 3rem;}
      [data-testid="stMetric"] {
        background: rgba(99, 102, 241, 0.06);
        border: 1px solid rgba(99, 102, 241, 0.16);
        border-radius: 0.8rem;
        padding: 0.75rem 0.9rem;
      }
      .cp-hero {
        border: 1px solid rgba(99, 102, 241, 0.25);
        background: linear-gradient(120deg, rgba(79,70,229,.13), rgba(14,165,233,.07));
        border-radius: 1rem;
        padding: 1rem 1.25rem;
        margin-bottom: 1.2rem;
      }
      .cp-hero h2 {margin: 0 0 .25rem 0;}
      .cp-card {
        border: 1px solid rgba(128,128,128,.22);
        border-radius: .8rem;
        padding: .9rem 1rem;
        margin: .4rem 0 .8rem 0;
      }
      .cp-label {font-size: .76rem; opacity: .65; text-transform: uppercase; letter-spacing: .06em;}
      .cp-value {font-size: 1.02rem; font-weight: 650; margin-top: .18rem;}
      .cp-summary-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .55rem;
        margin: .55rem 0 1rem 0;
      }
      .cp-summary-item {
        min-width: 0;
        border: 1px solid rgba(128,128,128,.20);
        background: rgba(99,102,241,.035);
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
      .cp-ai-output {
        border: 1px solid rgba(14,165,233,.28);
        border-left: 4px solid rgb(14,165,233);
        background: rgba(14,165,233,.065);
        border-radius: .8rem;
        padding: .9rem 1rem;
        margin: .45rem 0 .75rem 0;
      }
      .cp-ai-body {
        font-size: 1rem;
        font-weight: 560;
        line-height: 1.55;
        margin: .28rem 0;
        overflow-wrap: anywhere;
        white-space: pre-wrap;
      }
      .cp-ai-note {font-size: .78rem; opacity: .7;}
      .cp-pill {
        display: inline-block; border-radius: 999px; padding: .2rem .65rem;
        margin: .12rem .18rem .12rem 0; font-size: .78rem; font-weight: 650;
        background: rgba(99,102,241,.12); border: 1px solid rgba(99,102,241,.2);
      }
      .cp-decision {border-radius: .85rem; padding: .9rem 1rem; margin: .7rem 0 1rem 0;}
      .cp-decision strong {font-size: 1.18rem;}
      .cp-good {background: rgba(16,185,129,.11); border: 1px solid rgba(16,185,129,.32);}
      .cp-edit {background: rgba(14,165,233,.11); border: 1px solid rgba(14,165,233,.32);}
      .cp-warn {background: rgba(245,158,11,.12); border: 1px solid rgba(245,158,11,.34);}
      .cp-bad {background: rgba(239,68,68,.11); border: 1px solid rgba(239,68,68,.34);}
      div[data-testid="stDataFrame"] {border: 1px solid rgba(128,128,128,.16); border-radius: .6rem;}
      @media (max-width: 900px) {
        .cp-summary-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
      }
      @media (max-width: 560px) {
        .cp-summary-grid {grid-template-columns: 1fr;}
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


def render_decision_banner(result: dict[str, Any]) -> None:
    decision = str(result.get("decision", "UNKNOWN"))
    explanation = {
        "ALLOW": "Mandatory checks resolved. The candidate may continue.",
        "EDIT_REDACT": "Localized sensitive data was removed before release.",
        "REGENERATE": "The response must be generated again before release.",
        "BLOCK": "A policy veto prevents this action from executing.",
        "ESCALATE": "A human decision is required before continuing.",
    }.get(decision, "The middleware returned an unrecognized outcome.")
    st.markdown(
        f'<div class="cp-decision {decision_tone(decision)}">'
        f'<div class="cp-label">ControlPlane decision</div>'
        f'<strong>{html.escape(decision.replace("_", " "))}</strong><br>'
        f'{html.escape(explanation)}</div>',
        unsafe_allow_html=True,
    )


def render_checker_summary(checks: list[dict[str, Any]]) -> None:
    """Show checker outcomes and surface the exact point of failure."""
    st.markdown("#### Checks at a glance")
    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0, "NOT_APPLICABLE": 0}
    for check in checks:
        status = str(check.get("status", "UNKNOWN")).upper()
        counts[status if status in counts else "UNKNOWN"] += 1

    st.markdown(
        f"**Passed:** {counts['PASS']} · "
        f"**Failed:** {counts['FAIL']} · "
        f"**Unknown:** {counts['UNKNOWN']} · "
        f"**N/A:** {counts['NOT_APPLICABLE']}"
    )
    if not checks:
        st.caption("No checker was required for this route.")
        return

    status_icons = {
        "PASS": "✅",
        "FAIL": "❌",
        "UNKNOWN": "⚠️",
        "NOT_APPLICABLE": "➖",
    }
    for check in checks:
        status = str(check.get("status", "UNKNOWN")).upper()
        if status not in status_icons:
            status = "UNKNOWN"
        name = str(check.get("detector_id", "checker")).replace("_", " ").title()
        line = f"- {status_icons[status]} **{name}** — {status.replace('_', ' ')}"
        if status in {"FAIL", "UNKNOWN"} and check.get("reason"):
            line += f": {check['reason']}"
        st.markdown(line)


def render_result_overview(result: dict[str, Any]) -> None:
    risk = result.get("risk_profile", {})
    st.markdown("#### Risk, latency, and verification depth")
    st.markdown(
        compact_grid(
            [
                ("Risk", risk.get("tier", "—")),
                ("Evidence", result.get("evidence_state", "—")),
                ("Authorization", result.get("authorization_state", "—")),
                ("Checks run", result.get("checks_executed", 0)),
                ("Latency", f"{float(result.get('latency_ms', 0)):.1f} ms"),
                ("Model calls", result.get("model_calls", 0)),
            ]
        ),
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
        st.dataframe(check_rows(checks), use_container_width=True, hide_index=True)
    else:
        st.caption("No detector result was recorded.")

    if references:
        st.markdown(f"**Evidence trace ({len(references)} observations)**")
        st.dataframe(references, use_container_width=True, hide_index=True)


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


with st.sidebar:
    st.markdown("## ControlPlane.ai")
    st.caption("Adaptive verification · PoC console")
    API_URL = st.text_input("Middleware API", "http://localhost:8000").rstrip("/")
    if st.button("Check API connection", use_container_width=True):
        health = api_json("GET", "/health", timeout=3)
        st.success("API connected" if health.get("status") == "ok" else "API responded")
    st.divider()
    page = st.radio(
        "Workspace", ["Run scenario", "Audit trail", "Policies", "Metrics", "Feedback"]
    )
    st.divider()
    st.caption("Candidate → Verify → Decide → Audit")

st.markdown(
    """
    <div class="cp-hero">
      <h2>ControlPlane.ai</h2>
      <div>Risk-adaptive verification between an AI candidate and the user or tool it could affect.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if page == "Run scenario":
    st.subheader("Scenario demonstration")
    scenario_paths = sorted((PROJECT_ROOT / "scenarios").glob("**/*.json"))
    selected = st.selectbox(
        "Scenario",
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
    st.markdown("### 1 · AI input and candidate output")
    st.markdown(
        '<div class="cp-card">'
        '<div class="cp-label">User / workflow request</div>'
        f'<div class="cp-value">{html.escape(str(scenario_input))}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    preview = candidate_preview(payload)
    st.markdown(
        '<div class="cp-ai-output">'
        f'<div class="cp-label">{html.escape(preview["label"])}</div>'
        f'<div class="cp-ai-body">{html.escape(preview["body"])}</div>'
        "</div>",
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
                key_value_rows(arguments), use_container_width=True, hide_index=True
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
                use_container_width=True,
                hide_index=True,
            )
        st.markdown("**Trusted application context**")
        st.dataframe(
            key_value_rows(context), use_container_width=True, hide_index=True
        )

    with st.expander("Raw scenario JSON"):
        st.json(payload, expanded=False)

    if st.button(
        "Run ControlPlane verification", type="primary", use_container_width=True
    ):
        with st.spinner("Selecting a risk-proportional verification route..."):
            result = api_json("POST", "/evaluate", json=payload, timeout=20)
        st.session_state["last_result"] = result
        st.session_state["last_scenario"] = str(selected)

    if st.session_state.get("last_scenario") == str(selected):
        st.markdown("### 2 · Middleware decision")
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
        st.dataframe(overview, use_container_width=True, hide_index=True)
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
            f"Allowed status: {', '.join(policy.get('allowed_source_statuses', [])) or '—'} · "
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
        if st.button("Record feedback", type="primary", use_container_width=True):
            if not reviewer_id.strip() or not reason.strip():
                st.warning("Reviewer ID and a short reason are required in the demo console.")
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
