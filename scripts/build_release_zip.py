from __future__ import annotations

import argparse
import hashlib
import os
import re
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT.parent / "ControlPlane-ai-PoC-Submission.zip"
ARCHIVE_ROOT = "controlplane-ai-poc"

INCLUDED_DIRECTORIES = {
    "controlplane",
    "dashboard",
    "evaluation",
    "knowledge",
    "policies",
    "scenarios",
    "scripts",
    "tests",
}
INCLUDED_FILES = {
    ".env.example",
    ".gitattributes",
    ".gitignore",
    ".python-version",
    "ARCHITECTURE.md",
    "ASSUMPTIONS.md",
    "AUDIT_REPORT.md",
    "DEMO_GUIDE.md",
    "KNOWN_LIMITATIONS.md",
    "PROJECT_HANDOFF.md",
    "README.md",
    "REQUIREMENTS.md",
    "SUBMISSION_MANIFEST.md",
    "TRACEABILITY.md",
    "pytest.ini",
    "requirements-demo.txt",
    "requirements.txt",
}
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}
EXCLUDED_FILE_NAMES = {".env", "controlplane.db", "latest.json"}
EXCLUDED_SUFFIXES = {".db", ".log", ".pyc", ".pyo", ".tmp"}
SECRET_PATTERNS = {
    "Groq API key": re.compile(rb"\bgsk_[A-Za-z0-9]{16,}\b"),
}


def included_source_files() -> list[Path]:
    paths: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if relative.parts[0] not in INCLUDED_DIRECTORIES:
            if len(relative.parts) == 1 and relative.name in INCLUDED_FILES:
                paths.append(path)
            continue
        if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts[:-1]):
            continue
        if relative.name in EXCLUDED_FILE_NAMES:
            continue
        if relative.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(PROJECT_ROOT).as_posix())


def assert_secret_free(paths: list[Path]) -> None:
    findings: list[str] = []
    for path in paths:
        content = path.read_bytes()
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{label}: {path.relative_to(PROJECT_ROOT)}")
    if findings:
        raise ValueError("Release blocked by secret scan: " + "; ".join(findings))


def build_release_zip(output: Path = DEFAULT_OUTPUT) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output == PROJECT_ROOT or PROJECT_ROOT in output.parents:
        raise ValueError("Release ZIP must be written outside the project source tree.")

    files = included_source_files()
    missing = sorted(INCLUDED_FILES - {path.name for path in files})
    if missing:
        raise ValueError("Required release files are missing: " + ", ".join(missing))
    assert_secret_free(files)

    temporary = output.with_name(f".{output.stem}.tmp{output.suffix}")
    if temporary.exists():
        temporary.unlink()
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in files:
                relative = path.relative_to(PROJECT_ROOT).as_posix()
                archive.write(path, f"{ARCHIVE_ROOT}/{relative}")
        with zipfile.ZipFile(temporary) as archive:
            corrupt_entry = archive.testzip()
            if corrupt_entry is not None:
                raise ValueError(f"Release archive is corrupt at {corrupt_entry}.")
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Release archive contains duplicate entries.")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the clean ControlPlane PoC ZIP.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = build_release_zip(args.output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with zipfile.ZipFile(output) as archive:
        entry_count = len(archive.namelist())
    print(f"Release ZIP: {output}")
    print(f"Entries: {entry_count}")
    print(f"Size: {output.stat().st_size} bytes")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
