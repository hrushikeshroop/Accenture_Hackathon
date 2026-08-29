from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from controlplane.schemas.policy import PolicyConfig


class PolicyRepository:
    def __init__(self, policy_dir: Path):
        self.policy_dir = policy_dir
        self._cache_key: tuple[tuple[str, int, int], ...] | None = None
        self._cache: list[PolicyConfig] = []

    def list(self) -> list[PolicyConfig]:
        paths = sorted(self.policy_dir.glob("*.yaml"))
        cache_key = tuple(
            (str(path.resolve()), path.stat().st_mtime_ns, path.stat().st_size)
            for path in paths
        )
        if cache_key == self._cache_key:
            return [policy.model_copy(deep=True) for policy in self._cache]

        policies: list[PolicyConfig] = []
        for path in paths:
            with path.open("r", encoding="utf-8") as stream:
                policies.append(PolicyConfig.model_validate(yaml.safe_load(stream)))
        self._cache_key = cache_key
        self._cache = policies
        return [policy.model_copy(deep=True) for policy in policies]

    def get_for_use_case(
        self, use_case: str, version: str | None = None
    ) -> PolicyConfig:
        matches = [policy for policy in self.list() if policy.use_case == use_case]
        if version is not None:
            matches = [policy for policy in matches if policy.version == version]
        if not matches:
            suffix = f" version {version}" if version else ""
            raise KeyError(f"No policy for {use_case}{suffix}")
        return max(matches, key=lambda item: self._version_key(item.version))

    @staticmethod
    def checksum(policy: PolicyConfig) -> str:
        canonical = json.dumps(
            policy.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _version_key(version: str) -> tuple[tuple[int, int | str], ...]:
        return tuple(
            (0, int(part)) if part.isdigit() else (1, part)
            for part in version.split(".")
        )
