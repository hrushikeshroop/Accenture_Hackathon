from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from controlplane.core.evaluator import ControlPlaneEvaluator
from controlplane.schemas.event import ControlEvent
from controlplane.services.metrics_service import MetricsService

app = FastAPI(
    title="ControlPlane.ai PoC",
    version="0.1.0",
    description="Adaptive verification middleware for AI responses and agent actions.",
)
evaluator = ControlPlaneEvaluator()
metrics_service = MetricsService(evaluator.audit)


class ReplayRequest(BaseModel):
    policy_version: str | None = None


class FeedbackLabel(StrEnum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    UNSAFE_ESCAPE = "UNSAFE_ESCAPE"


class FeedbackRequest(BaseModel):
    evaluation_id: str
    reviewer_id: str
    label: FeedbackLabel
    reason: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/evaluate")
async def evaluate(event: ControlEvent) -> dict[str, Any]:
    try:
        result = await evaluator.evaluate(event)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@app.get("/evaluations")
async def evaluations(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict[str, Any]]:
    return evaluator.audit.list(limit=limit)


@app.get("/evaluations/{evaluation_id}")
async def evaluation(evaluation_id: str) -> dict[str, Any]:
    record = evaluator.audit.get(evaluation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return record


@app.post("/evaluations/{evaluation_id}/replay")
async def replay(evaluation_id: str, request: ReplayRequest) -> dict[str, Any]:
    try:
        result = await evaluator.replay(evaluation_id, request.policy_version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@app.post("/feedback")
async def feedback(request: FeedbackRequest) -> dict[str, str]:
    if evaluator.audit.get(request.evaluation_id) is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    evaluator.audit.add_feedback(
        request.evaluation_id,
        request.reviewer_id,
        request.label.value,
        request.reason,
    )
    return {"status": "recorded"}


@app.get("/policies")
async def policies() -> list[dict[str, Any]]:
    return [policy.model_dump(mode="json") for policy in evaluator.policies.list()]


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    return metrics_service.summary()
