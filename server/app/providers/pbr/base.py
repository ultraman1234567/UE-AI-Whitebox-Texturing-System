from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class PBRProviderError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class PBRMaterialRequest:
    name: str
    metallic: float = 0.0


@dataclass(frozen=True)
class PBRGenerationRequest:
    texture_size: int = 1024
    materials: list[PBRMaterialRequest] = field(default_factory=list)
    fallback_to_mock: bool = True


@dataclass(frozen=True)
class PBRGenerationResult:
    provider: str
    status: str
    materials: list[str] = field(default_factory=list)
    textures: dict[str, dict[str, str]] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)


class PBRProvider(Protocol):
    name: str

    def generate(self, request: PBRGenerationRequest, job_dir: Path) -> PBRGenerationResult:
        ...
