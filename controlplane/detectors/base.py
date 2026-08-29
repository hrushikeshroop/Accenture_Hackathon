from __future__ import annotations

from abc import ABC, abstractmethod

from controlplane.schemas.check_result import CheckResult
from controlplane.schemas.event import ControlEvent
from controlplane.schemas.policy import PolicyConfig


class Detector(ABC):
    detector_id: str
    tier: int = 1
    estimated_cost_units: float = 1

    @abstractmethod
    async def evaluate(
        self, event: ControlEvent, policy: PolicyConfig
    ) -> CheckResult:
        raise NotImplementedError
