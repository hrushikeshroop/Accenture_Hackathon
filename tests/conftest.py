from __future__ import annotations

from pathlib import Path

import pytest

from controlplane.core.evaluator import ControlPlaneEvaluator
from controlplane.schemas.event import ControlEvent
from controlplane.settings import PROJECT_ROOT, Settings


@pytest.fixture
def evaluator(tmp_path: Path) -> ControlPlaneEvaluator:
    return ControlPlaneEvaluator(
        Settings(
            db_path=tmp_path / "test.db",
            policy_dir=PROJECT_ROOT / "policies",
            source_registry=PROJECT_ROOT / "knowledge" / "source_registry.yaml",
            judge_url="",
            judge_api_key="",
            judge_model="",
        )
    )


def load_scenario(relative_path: str) -> ControlEvent:
    path = PROJECT_ROOT / "scenarios" / relative_path
    return ControlEvent.model_validate_json(path.read_text(encoding="utf-8"))
