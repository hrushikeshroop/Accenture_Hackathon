from __future__ import annotations

from controlplane.settings import Settings
from controlplane.storage.audit_repository import AuditRepository
from controlplane.storage.source_repository import SourceRepository

from .base import Detector
from .engineering import (
    EngineeringActionDetector,
    PermissionDetector,
    ReversibilityDetector,
    SecretDetector,
)
from .historical import HistoricalSignalDetector
from .judge import JudgeDetector
from .support import (
    ClaimExtractorDetector,
    EntitlementDetector,
    PiiDetector,
    RetrievalDetector,
)


class DetectorRegistry:
    def __init__(
        self, settings: Settings, audit: AuditRepository, sources: SourceRepository
    ):
        detectors: list[Detector] = [
            EngineeringActionDetector(),
            SecretDetector(),
            PermissionDetector(),
            ReversibilityDetector(),
            PiiDetector(),
            ClaimExtractorDetector(),
            RetrievalDetector(sources),
            EntitlementDetector(),
            JudgeDetector(settings),
            HistoricalSignalDetector(audit),
        ]
        self.detectors = {detector.detector_id: detector for detector in detectors}

    def get(self, detector_id: str) -> Detector:
        try:
            return self.detectors[detector_id]
        except KeyError as exc:
            raise KeyError(f"Unknown detector: {detector_id}") from exc

    def ids(self) -> list[str]:
        return sorted(self.detectors)
