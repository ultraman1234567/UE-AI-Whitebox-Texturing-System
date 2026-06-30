"""Configurable SAM provider skeleton.

The real SAM model is intentionally not imported here. Future deployment can
wire this provider to a server-side command or service without changing API
contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .base import MaskGenerationRequest, MaskGenerationResult, MaskProviderError


@dataclass(frozen=True)
class SAMMaskProviderConfig:
    endpoint: str = ""
    model_path: str = ""
    command_template: str = ""
    timeout: float = 120.0


class SAMMaskProvider:
    name = "sam"

    def __init__(self, config: SAMMaskProviderConfig | None = None) -> None:
        self.config = config or SAMMaskProviderConfig(
            endpoint=os.getenv("MASK_SAM_ENDPOINT", ""),
            model_path=os.getenv("MASK_SAM_MODEL_PATH", ""),
            command_template=os.getenv("MASK_SAM_COMMAND_TEMPLATE", ""),
            timeout=float(os.getenv("MASK_SAM_TIMEOUT", "120")),
        )

    def generate(self, request: MaskGenerationRequest, job_dir: Path) -> MaskGenerationResult:
        raise MaskProviderError(
            501,
            "SAMMaskProvider is configured as a server-side extension point; local tests must use provider='mock'",
        )
