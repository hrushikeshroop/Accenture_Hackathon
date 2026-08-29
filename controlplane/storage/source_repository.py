from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

MISSING_SOURCE_MARKER = "__MISSING__"


class SourceRepository:
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self._cache_key: tuple[str, int, int] | None = None
        self.sources: dict[str, dict[str, Any]] = {}
        self._load_if_changed()

    def _load_if_changed(self) -> None:
        stat = self.registry_path.stat()
        cache_key = (
            str(self.registry_path.resolve()),
            stat.st_mtime_ns,
            stat.st_size,
        )
        if cache_key == self._cache_key:
            return
        with self.registry_path.open("r", encoding="utf-8") as stream:
            raw = yaml.safe_load(stream) or {}
        if not isinstance(raw, dict) or not isinstance(raw.get("sources", {}), dict):
            raise TypeError("Source registry must contain a 'sources' mapping.")
        sources = raw.get("sources", {})
        self._validate_sources(sources)
        self.sources = sources
        self._cache_key = cache_key

    def _validate_sources(self, sources: dict[str, Any]) -> None:
        root = self.registry_path.parent.resolve()
        for source_id, source in sources.items():
            if not isinstance(source_id, str) or not source_id.strip():
                raise ValueError("Every source ID must be a non-empty string.")
            if not isinstance(source, dict):
                raise TypeError(f"Source '{source_id}' must be a mapping.")
            file_name = source.get("file")
            if not isinstance(file_name, str) or not file_name.strip():
                raise ValueError(f"Source '{source_id}' requires a file path.")
            file_path = (root / file_name).resolve()
            if not file_path.is_relative_to(root):
                raise ValueError(
                    f"Source '{source_id}' file must remain inside the knowledge directory."
                )
            authority = source.get("authority")
            if (
                isinstance(authority, bool)
                or not isinstance(authority, (int, float))
                or not 0 <= float(authority) <= 1
            ):
                raise ValueError(
                    f"Source '{source_id}' authority must be a number between 0 and 1."
                )
            for field in ("status", "version"):
                value = source.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Source '{source_id}' requires a non-empty {field}."
                    )
            if not isinstance(source.get("facts"), dict):
                raise TypeError(f"Source '{source_id}' facts must be a mapping.")

    def get(self, source_id: str) -> dict[str, Any] | None:
        self._load_if_changed()
        source = self.sources.get(source_id)
        if source is None:
            return None
        result = dict(source)
        result["source_id"] = source_id
        file_path = self.registry_path.parent / result["file"]
        try:
            result["content"] = file_path.read_text(encoding="utf-8")
            result["content_available"] = True
        except OSError as exc:
            result["content"] = ""
            result["content_available"] = False
            result["content_error"] = type(exc).__name__
        canonical = json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        result["checksum"] = hashlib.sha256(canonical).hexdigest()
        return result

    def resolve(self, source_ids: list[str]) -> list[dict[str, Any]]:
        return [source for source_id in source_ids if (source := self.get(source_id))]
