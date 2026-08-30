from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests
from streamlit.testing.v1 import AppTest

from dashboard.view_models import (
    candidate_preview,
    check_rows,
    evidence_rows,
    human_review_packet,
    scenario_meta,
    use_case_metric_rows,
    verification_route,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def escalation_result() -> dict[str, Any]:
    return {
        "evaluation_id": "evaluation-escalation-ui",
        "event_id": "event-escalation-ui",
        "use_case": "support.transactional",
        "risk_profile": {
            "tier": "HIGH",
            "signals": ["unsupported_financial_promise"],
            "reasons": ["The promise creates material customer risk."],
            "historical_failure_rate": 0,
            "historical_sample_size": 0,
        },
        "evidence_state": "NO_EVIDENCE",
        "authorization_state": "AUTHORIZED",
        "decision": "ESCALATE",
        "stop_reason": "HUMAN_REVIEW_REQUIRED",
        "reasons": ["A high-risk unsupported promise requires human review."],
        "checks_selected": ["retrieval_detector", "judge_detector"],
        "checks_skipped": [],
        "check_results": [
            {
                "detector_id": "retrieval_detector",
                "status": "UNKNOWN",
                "severity": "HIGH",
                "evidence_state": "NO_EVIDENCE",
                "confidence": None,
                "latency_ms": 2.5,
                "model_calls": 0,
                "reason": "No authoritative evidence supports the promise.",
                "evidence_references": [],
            },
            {
                "detector_id": "judge_detector",
                "status": "UNKNOWN",
                "severity": "HIGH",
                "evidence_state": "UNCERTAIN",
                "confidence": 0.4,
                "latency_ms": 700,
                "model_calls": 1,
                "reason": "The settlement guarantee could not be verified.",
                "evidence_references": [],
            },
        ],
        "policy_id": "support-transactional",
        "policy_version": "1.0",
        "policy_checksum": "test-checksum",
        "latency_budget_ms": 12000,
        "latency_ms": 703.2,
        "estimated_cost_units": 5,
        "model_calls": 1,
        "checks_executed": 2,
        "source_versions": {},
        "source_checksums": {},
        "sanitized_output": None,
        "action_guidance": {
            "summary": "Hold the candidate and route this evaluation to human review.",
            "retryable": False,
            "max_regeneration_attempts": 0,
            "if_retry_exhausted": None,
            "human_review_required": True,
        },
    }


def test_all_scenarios_have_demo_metadata():
    scenario_paths = sorted((PROJECT_ROOT / "scenarios").glob("**/*.json"))

    assert len(scenario_paths) == 17
    for path in scenario_paths:
        metadata = scenario_meta(path, PROJECT_ROOT)
        assert metadata["title"]
        assert metadata["prompt"]
        assert metadata["objective"]
        assert metadata["expected"] in {
            "ALLOW",
            "EDIT_REDACT",
            "REGENERATE",
            "BLOCK",
            "ESCALATE",
        }
        payload = json.loads(path.read_text(encoding="utf-8"))
        preview = candidate_preview(payload)
        assert preview["label"] in {"AI response", "AI proposed action"}
        assert preview["body"]
        assert preview["note"]
        if payload["candidate"].get("text"):
            assert preview["body"] == payload["candidate"]["text"]

    for evaluation_path in sorted((PROJECT_ROOT / "evaluation").glob("*-cases.jsonl")):
        for line in evaluation_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            labelled_case = json.loads(line)
            path = PROJECT_ROOT / labelled_case["scenario"]
            assert (
                scenario_meta(path, PROJECT_ROOT)["expected"]
                == labelled_case["expected_decision"]
            )


def test_candidate_outputs_have_only_the_intentional_claim_extraction_duplicate():
    by_text: dict[str, list[str]] = {}
    for path in sorted((PROJECT_ROOT / "scenarios").glob("**/*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        text = payload.get("candidate", {}).get("text")
        if text:
            by_text.setdefault(text, []).append(
                path.relative_to(PROJECT_ROOT / "scenarios").as_posix()
            )

    duplicates = {text: paths for text, paths in by_text.items() if len(paths) > 1}
    assert duplicates == {
        "Customers may request a refund within seven calendar days of purchase.": [
            "support/auto-extracted-supported-faq.json",
            "support/supported-faq.json",
        ]
    }


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

    support_payload = json.loads(
        (PROJECT_ROOT / "scenarios/support/supported-faq.json").read_text(
            encoding="utf-8"
        )
    )
    support_preview = candidate_preview(support_payload)
    assert support_preview["label"] == "AI response"
    assert support_preview["body"] == support_payload["candidate"]["text"]

    action_payload = json.loads(
        (PROJECT_ROOT / "scenarios/engineering/safe-file-edit.json").read_text(
            encoding="utf-8"
        )
    )
    action_preview = candidate_preview(action_payload)
    assert action_preview["label"] == "AI proposed action"
    assert "File Edit via Edit" in action_preview["body"]
    assert "README.md" in action_preview["body"]
    assert "Improve setup instructions" in action_preview["body"]


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


def test_human_review_packet_surfaces_request_candidate_and_failure_context():
    event = {
        "event_id": "support-event-1",
        "use_case": "support.transactional",
        "candidate": {"text": "The credit is guaranteed today."},
        "trusted_context": {"identity_verified": True},
        "metadata": {
            "request_text": "When will the credit reach my bank?",
            "scenario_title": "Unsupported settlement promise",
        },
    }
    result = {
        "evaluation_id": "evaluation-1",
        "event_id": "support-event-1",
        "use_case": "support.transactional",
        "risk_profile": {"tier": "HIGH"},
        "evidence_state": "NO_EVIDENCE",
        "authorization_state": "AUTHORIZED",
        "reasons": ["A high-risk unsupported promise requires human review."],
        "policy_id": "support-transactional",
        "policy_version": "1.0",
        "latency_ms": 702.5,
        "model_calls": 1,
        "check_results": [
            {
                "detector_id": "judge_detector",
                "status": "UNKNOWN",
                "evidence_state": "UNCERTAIN",
                "reason": "The promise could not be verified.",
                "latency_ms": 700,
                "model_calls": 1,
                "evidence_references": [],
            }
        ],
    }

    packet = human_review_packet(event, result, created_at="2026-08-30 10:00:00")

    assert packet["title"] == "Unsupported settlement promise"
    assert packet["request"] == "When will the credit reach my bank?"
    assert packet["candidate"] == "The credit is guaranteed today."
    assert packet["risk"] == "HIGH"
    assert packet["findings"][0]["Checker"] == "Judge Detector"
    assert packet["judge"]["model_calls"] == 1
    assert packet["trusted_context"] == {"identity_verified": True}


def test_verification_route_distinguishes_local_evidence_and_live_judge():
    route = verification_route(
        {
            "decision": "ESCALATE",
            "stop_reason": "HUMAN_REVIEW_REQUIRED",
            "check_results": [
                {
                    "detector_id": "pii_detector",
                    "latency_ms": 1.2,
                    "model_calls": 0,
                },
                {
                    "detector_id": "retrieval_detector",
                    "latency_ms": 2.3,
                    "model_calls": 0,
                },
                {
                    "detector_id": "judge_detector",
                    "latency_ms": 700,
                    "model_calls": 1,
                },
            ],
        }
    )

    assert [stage["state"] for stage in route] == [
        "RAN",
        "RAN",
        "CALLED",
        "ESCALATE",
    ]
    assert route[2]["detail"] == "1 live call · 700.0 ms"
    assert route[3]["detail"] == "Human Review Required"


def test_dashboard_default_page_loads_without_api_call():
    app = AppTest.from_file(str(PROJECT_ROOT / "dashboard" / "app.py"))
    app.run(timeout=15)

    assert not app.exception
    assert app.subheader[0].value == "Decision walkthrough"
    assert len(app.selectbox) == 1
    assert len(app.selectbox[0].options) == 17
    assert any(
        "AI candidate under review" in markdown.value for markdown in app.markdown
    )
    assert any(
        "Reset the production environment" in markdown.value
        for markdown in app.markdown
    )
    assert any("DROP TABLE customers" in markdown.value for markdown in app.markdown)
    assert {expander.label for expander in app.expander} == {
        "Connection settings",
        "More scenario details",
        "Raw scenario JSON",
    }


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
        "checks_selected": [
            "engineering_action",
            "historical_detector",
            "judge_detector",
        ],
        "checks_skipped": [],
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
            },
            {
                "detector_id": "historical_detector",
                "status": "PASS",
                "severity": "LOW",
                "evidence_state": "NOT_APPLICABLE",
                "confidence": 0.9,
                "latency_ms": 0.2,
                "reason": "No risky history was found.",
                "evidence_references": [],
            },
            {
                "detector_id": "judge_detector",
                "status": "UNKNOWN",
                "severity": "HIGH",
                "evidence_state": "UNCERTAIN",
                "confidence": None,
                "latency_ms": 5,
                "reason": "The judge could not resolve the claim.",
                "evidence_references": [],
            },
        ],
        "policy_id": "engineering-production",
        "policy_version": "1.0",
        "policy_checksum": "test-checksum",
        "latency_budget_ms": 100,
        "latency_ms": 1.25,
        "estimated_cost_units": 2,
        "model_calls": 0,
        "checks_executed": 3,
        "source_versions": {},
        "source_checksums": {},
        "sanitized_output": None,
        "action_guidance": {
            "summary": "Do not execute the action.",
            "retryable": False,
            "max_regeneration_attempts": 0,
            "if_retry_exhausted": None,
            "human_review_required": False,
        },
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
        button for button in app.button if button.label == "Run middleware verification"
    )
    evaluate.click().run(timeout=15)

    assert not app.exception
    assert any(
        "Middleware decision" in markdown.value and "BLOCK" in markdown.value
        for markdown in app.markdown
    )
    assert any(
        "Middleware verification result" in markdown.value for markdown in app.markdown
    )
    assert any("Checker verdicts" in markdown.value for markdown in app.markdown)
    assert any("Risk versus latency" in markdown.value for markdown in app.markdown)
    assert any("Verification route" in markdown.value for markdown in app.markdown)
    assert any(
        "Latency / budget" in markdown.value and "100" in markdown.value
        for markdown in app.markdown
    )
    assert any(
        "Verification stopped: Critical Veto" in caption.value
        for caption in app.caption
    )
    summary = next(
        markdown.value
        for markdown in app.markdown
        if "Checker verdicts" in markdown.value
    )
    assert "<strong>1</strong> passed" in summary
    assert "<strong>1</strong> failed" in summary
    assert "<strong>1</strong> unknown" in summary
    assert "<strong>0</strong> n/a" in summary
    assert any(
        "Engineering Action" in markdown.value
        and "FAIL" in markdown.value
        and "destructive command was detected" in markdown.value
        for markdown in app.markdown
    )
    assert any(
        "Historical Detector" in markdown.value and "PASS" in markdown.value
        for markdown in app.markdown
    )
    assert any(
        "Judge Detector" in markdown.value and "UNKNOWN" in markdown.value
        for markdown in app.markdown
    )
    assert {expander.label for expander in app.expander} == {
        "Connection settings",
        "More scenario details",
        "Raw scenario JSON",
        "More decision details",
        "Raw decision JSON",
    }


def test_escalated_decision_renders_the_reviewer_packet(monkeypatch):
    result = escalation_result()

    class FakeResponse:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict[str, Any]:
            return result

    monkeypatch.setattr(requests, "request", lambda *args, **kwargs: FakeResponse())
    app = AppTest.from_file(str(PROJECT_ROOT / "dashboard" / "app.py"))
    app.run(timeout=15)
    evaluate = next(
        button for button in app.button if button.label == "Run middleware verification"
    )
    evaluate.click().run(timeout=15)

    assert not app.exception
    assert any("Human review handoff" in item.value for item in app.markdown)
    assert any("Original request" in item.value for item in app.markdown)
    assert any("AI proposed action" in item.value for item in app.markdown)
    assert any(
        "high-risk unsupported promise requires human review" in item.value
        for item in app.markdown
    )
    assert any("Groq judge:" in item.value for item in app.info)
    assert "Reviewer context and evidence" in {
        expander.label for expander in app.expander
    }
    assert any(button.label == "Record reviewer decision" for button in app.button)


def test_human_review_queue_loads_redacted_escalation_context(monkeypatch):
    result = escalation_result()
    event = {
        "event_id": "event-escalation-ui",
        "use_case": "support.transactional",
        "candidate": {
            "text": "A $5,000 credit is guaranteed to reach your bank today."
        },
        "trusted_context": {
            "customer_id": "customer-95",
            "identity_verified": True,
        },
        "metadata": {
            "request_text": "When will the goodwill credit reach my bank?",
            "scenario_title": "High-risk financial guarantee",
        },
    }
    record = {
        "evaluation_id": result["evaluation_id"],
        "event_id": result["event_id"],
        "use_case": result["use_case"],
        "created_at": "2026-08-30 10:00:00",
        "event": event,
        "result": result,
    }

    class FakeResponse:
        def __init__(self, payload: Any):
            self.payload = payload

        @staticmethod
        def raise_for_status() -> None:
            return None

        def json(self) -> Any:
            return self.payload

    def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        if url.endswith("/evaluations"):
            return FakeResponse([record])
        if url.endswith("/feedback"):
            return FakeResponse([])
        raise AssertionError(f"Unexpected dashboard API request: {method} {url}")

    monkeypatch.setattr(requests, "request", fake_request)
    app = AppTest.from_file(str(PROJECT_ROOT / "dashboard" / "app.py"))
    app.run(timeout=15)
    app.radio[0].set_value("Human review").run(timeout=15)

    assert not app.exception
    assert app.subheader[0].value == "Human review queue"
    assert any("High-risk financial guarantee" in item.value for item in app.markdown)
    assert any(
        "When will the goodwill credit reach my bank?" in item.value
        for item in app.markdown
    )
    assert any("A $5,000 credit is guaranteed" in item.value for item in app.markdown)
    assert any(button.label == "Record reviewer decision" for button in app.button)
    assert "Raw redacted escalation record" in {
        expander.label for expander in app.expander
    }
