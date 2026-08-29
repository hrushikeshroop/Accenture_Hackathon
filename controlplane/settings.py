from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    db_path: Path = PROJECT_ROOT / os.getenv("CONTROLPLANE_DB_PATH", "controlplane.db")
    policy_dir: Path = PROJECT_ROOT / os.getenv("CONTROLPLANE_POLICY_DIR", "policies")
    source_registry: Path = PROJECT_ROOT / os.getenv(
        "CONTROLPLANE_SOURCE_REGISTRY", "knowledge/source_registry.yaml"
    )
    judge_url: str = os.getenv("CONTROLPLANE_JUDGE_URL", "")
    judge_api_key: str = os.getenv("CONTROLPLANE_JUDGE_API_KEY", "")
    judge_model: str = os.getenv("CONTROLPLANE_JUDGE_MODEL", "")
    judge_timeout_seconds: float = float(
        os.getenv("CONTROLPLANE_JUDGE_TIMEOUT_SECONDS", "10")
    )

    def __post_init__(self) -> None:
        if self.judge_timeout_seconds <= 0:
            raise ValueError("judge_timeout_seconds must be positive")


settings = Settings()
