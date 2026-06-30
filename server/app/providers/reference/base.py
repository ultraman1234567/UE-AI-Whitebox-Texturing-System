from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class ReferenceProviderError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class ReferenceGenerationRequest:
    provider: str = "mock"
    prompt: str = ""
    negative_prompt: str = ""
    seed: int | None = None
    width: int = 1024
    height: int = 1024
    strength: float = 0.65
    input_images: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    fallback_to_mock: bool = False


@dataclass(frozen=True)
class ReferenceGenerationResult:
    provider: str
    status: str
    output_path: str | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ReferenceImageProvider(Protocol):
    name: str

    def generate(self, request: ReferenceGenerationRequest, job_dir: Path) -> ReferenceGenerationResult:
        ...
