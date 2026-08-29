from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

import controlplane.main as api_module
from controlplane.core.evaluator import ControlPlaneEvaluator
from controlplane.detectors.judge import JudgeDetector
from controlplane.main import app
from controlplane.schemas.check_result import EvidenceState
from controlplane.schemas.decision import DecisionAction
from controlplane.services.metrics_service import MetricsService
from controlplane.settings import PROJECT_ROOT, Settings

from .conftest import load_scenario


class FakeChatCompletionResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    @staticmethod
    def read() -> bytes:
        content = json.dumps(
            {
                "state": "NO_EVIDENCE",
                "reason": "No usable retrieved source establishes the claim.",
            }
        )
        return json.dumps(
            {"choices": [{"message": {"content": content}}]}
        ).encode("utf-8")


def api_request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(request())


def test_mock_judge_path_is_explicit_and_safe(
    tmp_path: Path, monkeypatch
):
    evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "judge.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
            judge_url="mock://local",
            judge_api_key="",
            judge_model="simulated-judge",
        )
    )
    event = load_scenario("support/judge-unavailable-escalation.json")
    event.metadata["mock_judge_state"] = "UNCERTAIN"
    result = asyncio.run(evaluator.evaluate(event))
    judge = next(
        item for item in result.check_results if item.detector_id == "judge_detector"
    )
    assert result.decision == DecisionAction.ESCALATE
    assert result.model_calls == 1
    assert "Simulated secondary-judge" in judge.reason
    assert judge.evidence_references
    assert {item["source_id"] for item in judge.evidence_references} >= {
        "refunds-v2"
    }

    def delayed_provider_call(self, event, evidence_references):
        time.sleep(2.5)
        return (
            EvidenceState.NO_EVIDENCE,
            "No usable retrieved source establishes the claim.",
        )

    monkeypatch.setattr(JudgeDetector, "_call", delayed_provider_call)
    delayed_evaluator = ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "delayed-judge.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
            judge_url="https://provider.test/chat/completions",
            judge_api_key="test-only-key",
            judge_model="test-model",
        )
    )
    delayed_result = asyncio.run(delayed_evaluator.evaluate(event))
    delayed_judge = next(
        item
        for item in delayed_result.check_results
        if item.detector_id == "judge_detector"
    )
    assert delayed_judge.model_calls == 1
    assert delayed_result.stop_reason.value != "LATENCY_BUDGET_REACHED"


def test_judge_is_not_called_without_retrieval_trace(tmp_path: Path):
    settings = Settings(
        db_path=tmp_path / "unused.db",
        judge_url="mock://local",
        judge_api_key="",
        judge_model="simulated-judge",
    )
    detector = JudgeDetector(settings)
    event = load_scenario("support/judge-unavailable-escalation.json")
    policy = ControlPlaneEvaluator(settings).policies.get_for_use_case(event.use_case)

    result = asyncio.run(detector.evaluate(event, policy, prior_results=[]))

    assert result.evidence_state == EvidenceState.NO_EVIDENCE
    assert result.model_calls == 0
    assert "no retrieved evidence trace" in result.reason


def test_openai_compatible_judge_request_contains_evidence_and_auth(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeChatCompletionResponse()

    monkeypatch.setattr("controlplane.detectors.judge.urlopen", fake_urlopen)
    detector = JudgeDetector(
        Settings(judge_api_key="test-only-key")
    )
    event = load_scenario("support/judge-unavailable-escalation.json")
    references = [
        {
            "source_id": "refunds-v2",
            "source_version": "2.0",
            "source_status": "current",
            "claim_key": "lifetime_service_guarantee",
            "usable": False,
            "used_for_decision": False,
            "reason": "Source does not contain this claim key.",
        }
    ]

    state, reason = detector._call(event, references)

    assert state == EvidenceState.NO_EVIDENCE
    assert "No usable retrieved source" in reason
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-only-key"
    assert captured["timeout"] == 10
    payload = captured["payload"]
    assert payload["model"] == "qwen/qwen3.8-27b"
    assert payload["reasoning_effort"] == "none"
    assert payload["max_completion_tokens"] == 180
    assert payload["response_format"] == {"type": "json_object"}
    assert "refunds-v2" in payload["messages"][1]["content"]
    assert "test-only-key" not in json.dumps(payload)


def test_unconfigured_judge_does_not_overwrite_no_evidence(evaluator):
    result = asyncio.run(
        evaluator.evaluate(load_scenario("support/judge-unavailable-escalation.json"))
    )

    judge = next(
        item for item in result.check_results if item.detector_id == "judge_detector"
    )
    assert judge.status.value == "UNKNOWN"
    assert judge.evidence_state == EvidenceState.NOT_APPLICABLE
    assert result.evidence_state == EvidenceState.NO_EVIDENCE
    assert result.decision == DecisionAction.ESCALATE


def test_health_and_policy_endpoints():
    assert api_request("GET", "/health").json() == {"status": "ok"}
    response = api_request("GET", "/policies")
    assert response.status_code == 200
    assert len(response.json()) == 5


def test_invalid_action_contract_returns_422():
    response = api_request(
        "POST",
        "/evaluate",
        json={
            "session_id": "invalid-action",
            "use_case": "engineering.development",
            "event_type": "proposed_action",
            "actor": {"id": "agent", "role": "ai_agent"},
            "candidate": {"operation": "file_edit"},
            "trusted_context": {},
        },
    )
    assert response.status_code == 422


def test_string_false_authorization_is_rejected_at_api_boundary():
    response = api_request(
        "POST",
        "/evaluate",
        json={
            "session_id": "typed-bypass",
            "use_case": "engineering.development",
            "event_type": "proposed_action",
            "actor": {"id": "agent", "role": "ai_agent"},
            "candidate": {"operation": "file_edit"},
            "trusted_context": {
                "environment": "development",
                "authorized": "false",
            },
        },
    )

    assert response.status_code == 422


def test_evaluate_feedback_and_metrics_api(tmp_path: Path, monkeypatch):
    evaluator = ControlPlaneEvaluator(
        Settings(db_path=tmp_path / "api.db")
    )
    monkeypatch.setattr(api_module, "evaluator", evaluator)
    monkeypatch.setattr(api_module, "metrics_service", MetricsService(evaluator.audit))

    event = load_scenario("support/supported-faq.json")
    response = api_request(
        "POST", "/evaluate", json=event.model_dump(mode="json")
    )
    assert response.status_code == 200
    evaluation_id = response.json()["evaluation_id"]

    feedback = api_request(
        "POST",
        "/feedback",
        json={
            "evaluation_id": evaluation_id,
            "reviewer_id": "reviewer-2",
            "label": "CORRECT",
            "reason": "The evidence and decision are correct.",
        },
    )
    assert feedback.status_code == 200

    metrics = api_request("GET", "/metrics").json()
    assert metrics["total_evaluations"] == 1
    assert metrics["feedback_labels"] == {"CORRECT": 1}
