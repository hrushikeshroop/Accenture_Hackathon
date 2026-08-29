from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GROQ_JUDGE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_JUDGE_MODEL = "qwen/qwen3.8-27b"

# Local secrets stay in the ignored .env file. Existing shell/CI variables win so
# teammates can use the same code without copying one machine's credentials.
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    db_path: Path = PROJECT_ROOT / os.getenv("CONTROLPLANE_DB_PATH", "controlplane.db")
    policy_dir: Path = PROJECT_ROOT / os.getenv("CONTROLPLANE_POLICY_DIR", "policies")
    source_registry: Path = PROJECT_ROOT / os.getenv(
        "CONTROLPLANE_SOURCE_REGISTRY", "knowledge/source_registry.yaml"
    )
    # Groq is the fixed AI-as-a-judge provider for this demo. These fields remain
    # injectable so the hermetic mock and request-shape tests never call a network.
    judge_url: str = GROQ_JUDGE_URL
    judge_api_key: str = os.getenv("GROQ_API_KEY", "")
    judge_model: str = GROQ_JUDGE_MODEL
    judge_timeout_seconds: float = float(
        os.getenv("CONTROLPLANE_JUDGE_TIMEOUT_SECONDS", "10")
    )

    def __post_init__(self) -> None:
        if self.judge_timeout_seconds <= 0:
            raise ValueError("judge_timeout_seconds must be positive")


settings = Settings()
