from __future__ import annotations

import zipfile
from pathlib import Path

from scripts.build_release_zip import build_release_zip


def test_release_zip_is_clean_and_contains_submission_readme(tmp_path: Path):
    output = build_release_zip(tmp_path / "ControlPlane-test-release.zip")

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert archive.testzip() is None
        assert "controlplane-ai-poc/README.md" in names
        assert "controlplane-ai-poc/README.pdf" in names
        assert "controlplane-ai-poc/assets/controlplane-architecture.svg" in names
        assert "controlplane-ai-poc/requirements.txt" in names
        assert "controlplane-ai-poc/tests/test_live_judge_integration.py" in names
        assert "controlplane-ai-poc/evaluation/results/baseline.json" in names
        assert all("__pycache__" not in name for name in names)
        assert all(".pytest_cache" not in name for name in names)
        assert all(".ruff_cache" not in name for name in names)
        assert all(not name.endswith("controlplane.db") for name in names)
        assert all(not name.endswith("evaluation/results/latest.json") for name in names)
        assert all(not name.endswith(".pyc") for name in names)
        assert all(not name.endswith("/.env") for name in names)
