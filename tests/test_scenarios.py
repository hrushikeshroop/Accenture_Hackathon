from __future__ import annotations

import asyncio
import json

import pytest

from controlplane.schemas.check_result import EvidenceState
from controlplane.schemas.decision import DecisionAction, StopReason
from controlplane.schemas.event import ControlEvent
from controlplane.settings import PROJECT_ROOT

from .conftest import load_scenario


def test_labelled_evaluation_covers_every_scenario_exactly_once():
    scenario_paths = {
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in (PROJECT_ROOT / "scenarios").glob("**/*.json")
    }
    labelled_paths: list[str] = []
    for path in sorted((PROJECT_ROOT / "evaluation").glob("*-cases.jsonl")):
        labelled_paths.extend(
            json.loads(line)["scenario"]
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    assert len(labelled_paths) == len(set(labelled_paths))
    assert set(labelled_paths) == scenario_paths


def test_scenario_event_ids_are_unique_and_contract_valid():
    events = [
        ControlEvent.model_validate_json(path.read_text(encoding="utf-8"))
        for path in (PROJECT_ROOT / "scenarios").glob("**/*.json")
    ]

    assert len(events) == 17
    assert len({event.event_id for event in events}) == len(events)


@pytest.mark.parametrize(
    ("scenario", "decision"),
    [
        ("engineering/safe-file-edit.json", DecisionAction.ALLOW),
        ("engineering/destructive-production-command.json", DecisionAction.BLOCK),
        ("engineering/unbounded-delete-with-explanation.json", DecisionAction.BLOCK),
        ("engineering/reversible-migration.json", DecisionAction.ESCALATE),
        ("engineering/secret-exposure.json", DecisionAction.BLOCK),
        ("engineering/production-read-no-rollback.json", DecisionAction.ALLOW),
        ("support/supported-faq.json", DecisionAction.ALLOW),
        ("support/contradicted-refund-answer.json", DecisionAction.REGENERATE),
        ("support/no-evidence-answer.json", DecisionAction.REGENERATE),
        ("support/pii-leak.json", DecisionAction.EDIT_REDACT),
        ("support/unauthorized-cancellation.json", DecisionAction.BLOCK),
        ("support/overlap-pii-contradiction.json", DecisionAction.REGENERATE),
        ("support/phone-pii.json", DecisionAction.EDIT_REDACT),
        ("support/auto-extracted-supported-faq.json", DecisionAction.ALLOW),
        ("support/judge-unavailable-escalation.json", DecisionAction.ESCALATE),
        ("support/judge-mixed-evidence-refund.json", DecisionAction.ESCALATE),
        ("support/judge-plan-change-promise.json", DecisionAction.ESCALATE),
    ],
)
def test_expected_scenario_decision(evaluator, scenario, decision):
    result = asyncio.run(evaluator.evaluate(load_scenario(scenario)))
    assert result.decision == decision


def test_authoritative_source_beats_stale_source(evaluator):
    result = asyncio.run(
        evaluator.evaluate(load_scenario("support/contradicted-refund-answer.json"))
    )
    assert result.evidence_state == EvidenceState.CONTRADICTED
    retrieval = next(
        item for item in result.check_results if item.detector_id == "retrieval_detector"
    )
    selected = [
        reference
        for reference in retrieval.evidence_references
        if reference.get("used_for_decision")
    ]
    assert selected[0]["source_id"] == "refunds-v2"
    assert result.source_versions == {"refunds-v1": "1.0", "refunds-v2": "2.0"}
    assert set(result.source_checksums) == {"refunds-v1", "refunds-v2"}


def test_resolved_evidence_stops_before_model_judge(evaluator):
    result = asyncio.run(evaluator.evaluate(load_scenario("support/supported-faq.json")))
    assert "judge_detector" in result.checks_skipped
    assert result.model_calls == 0
    assert result.stop_reason == StopReason.RESOLVED


def test_pii_is_redacted(evaluator):
    result = asyncio.run(evaluator.evaluate(load_scenario("support/pii-leak.json")))
    assert result.sanitized_output is not None
    assert "alice@example.com" not in result.sanitized_output
    assert "4111 1111 1111 1111" not in result.sanitized_output


def test_overlapping_pii_does_not_skip_hallucination_check(evaluator):
    result = asyncio.run(
        evaluator.evaluate(load_scenario("support/overlap-pii-contradiction.json"))
    )
    assert result.decision == DecisionAction.REGENERATE
    assert result.evidence_state == EvidenceState.CONTRADICTED
    assert "retrieval_detector" not in result.checks_skipped
    assert any("sensitive-data" in reason for reason in result.reasons)


def test_phone_number_is_redacted(evaluator):
    result = asyncio.run(evaluator.evaluate(load_scenario("support/phone-pii.json")))
    assert result.decision == DecisionAction.EDIT_REDACT
    assert result.sanitized_output is not None
    assert "98765 43210" not in result.sanitized_output


def test_bounded_claim_parser_feeds_retrieval(evaluator):
    result = asyncio.run(
        evaluator.evaluate(load_scenario("support/auto-extracted-supported-faq.json"))
    )
    extraction = next(
        item for item in result.check_results if item.detector_id == "claim_extractor"
    )
    assert "bounded PoC parser" in extraction.reason
    assert result.evidence_state == EvidenceState.VERIFIED
