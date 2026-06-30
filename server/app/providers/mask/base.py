from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class MaskProviderError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class CandidateMask:
    mask_id: str
    path: str
    bbox: list[int]
    area: int
    score: float
    preview_url: str = ""


@dataclass(frozen=True)
class MaskGenerationRequest:
    provider: str = "mock"
    material_name: str = ""
    mode: str = "automatic"
    params: dict[str, Any] = field(default_factory=dict)
    fallback_to_mock: bool = False


@dataclass(frozen=True)
class MaskGenerationResult:
    provider: str
    status: str
    masks: list[str] = field(default_factory=list)
    candidates: list[CandidateMask] = field(default_factory=list)


class MaskProvider(Protocol):
    name: str

    def generate(self, request: MaskGenerationRequest, job_dir: Path) -> MaskGenerationResult:
        ...
