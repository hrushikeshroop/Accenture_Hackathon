from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests
from streamlit.testing.v1 import AppTest

from dashboard.view_models import (
    check_rows,
    evidence_rows,
    scenario_meta,
    use_case_metric_rows,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_all_scenarios_have_demo_metadata():
    scenario_paths = sorted((PROJECT_ROOT / "scenarios").glob("**/*.json"))

    assert len(scenario_paths) == 15
    for path in scenario_paths:
        metadata = scenario_meta(path, PROJECT_ROOT)
        assert metadata["title"]
        assert metadata["objective"]
        assert metadata["expected"] in {
            "ALLOW",
            "EDIT_REDACT",
            "REGENERATE",
            "BLOCK",
            "ESCALATE",
        }

    for evaluation_path in sorted((PROJECT_ROOT / "evaluation").glob("*-cases.jsonl")):
        for line in evaluation_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            labelled_case = json.loads(line)
            path = PROJECT_ROOT / labelled_case["scenario"]
            assert scenario_meta(path, PROJECT_ROOT)["expected"] == labelled_case[
                "expected_decision"
            ]


def test_check_and_evidence_rows_are_human_readable():
    checks = [
        {
            "detector_id": "retrieval_detector",
            "status": "PASS",
            "severity": "MEDIUM",
            "evidence_state": "VERIFIED",
            "confidence": 0.9,
            "latency_ms": 1.234,
            "reason": "The claim matched policy.",
            "evidence_references": [
                {
                    "source_id": "refunds-v2",
                    "source_version": "2.0",
                    "source_status": "current",
                    "authority": 1.0,
                    "usable": True,
                    "used_for_decision": True,
                    "claim_key": "refund_window_days",
                    "reason": "Matched.",
                }
            ],
        }
    ]

    assert check_rows(checks)[0]["Check"] == "Retrieval Detector"
    assert check_rows(checks)[0]["Time (ms)"] == "1.23"
    assert evidence_rows(checks)[0]["Usable"] == "Yes"
    assert evidence_rows(checks)[0]["Source"] == "refunds-v2"
    assert evidence_rows(checks)[0]["Version"] == "2.0"
    assert evidence_rows(checks)[0]["Status"] == "current"


def test_use_case_metrics_are_flattened_for_a_table():
    rows = use_case_metric_rows(
        {"support.informational": {"ALLOW": 2, "REGENERATE": 1}}
    )

    assert rows == [
        {
            "Use case": "support.informational",
            "Total": 3,
            "ALLOW": 2,
            "REGENERATE": 1,
        }
    ]


def test_dashboard_default_page_loads_without_api_call():
    app = AppTest.from_file(str(PROJECT_ROOT / "dashboard" / "app.py"))
    app.run(timeout=15)

    assert not app.exception
    assert app.subheader[0].value == "Run a labelled scenario"
    assert len(app.selectbox) == 1
    assert len(app.selectbox[0].options) == 15


def test_dashboard_evaluate_action_renders_readable_decision(monkeypatch):
    result = {
        "evaluation_id": "evaluation-ui-test",
        "event_id": "event-ui-test",
        "use_case": "engineering.production",
        "risk_profile": {
            "tier": "CRITICAL",
            "signals": ["destructive_operation"],
            "reasons": ["Destructive production work is critical."],
            "historical_failure_rate": 0,
            "historical_sample_size": 0,
        },
        "evidence_state": "NOT_APPLICABLE",
        "authorization_state": "AUTHORIZED",
        "decision": "BLOCK",
        "stop_reason": "CRITICAL_VETO",
        "reasons": ["A destructive database operation is blocked."],
        "checks_selected": ["engineering_action"],
        "checks_skipped": ["judge_detector"],
        "check_results": [
            {
                "detector_id": "engineering_action",
                "status": "FAIL",
                "severity": "CRITICAL",
                "evidence_state": "NOT_APPLICABLE",
                "confidence": None,
                "latency_ms": 0.5,
                "reason": "A destructive command was detected.",
                "evidence_references": [],
            }
        ],
        "policy_id": "engineering-production",
        "policy_version": "1.0",
        "policy_checksum": "test-checksum",
        "latency_ms": 1.25,
        "estimated_cost_units": 2,
        "model_calls": 0,
        "checks_executed": 1,
        "source_versions": {},
        "source_checksums": {},
        "sanitized_output": None,
    }

    class FakeResponse:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict[str, Any]:
            return result

    def fake_request(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse()

    monkeypatch.setattr(requests, "request", fake_request)
    app = AppTest.from_file(str(PROJECT_ROOT / "dashboard" / "app.py"))
    app.run(timeout=15)
    evaluate = next(
        button
        for button in app.button
        if button.label == "Evaluate through ControlPlane"
    )
    evaluate.click().run(timeout=15)

    assert not app.exception
    assert any(metric.label == "Risk" and metric.value == "CRITICAL" for metric in app.metric)
    assert any(
        "ControlPlane decision" in markdown.value and "BLOCK" in markdown.value
        for markdown in app.markdown
    )
    assert any("Verification checks" in markdown.value for markdown in app.markdown)
