"""Mock reference provider for local, offline development."""

from pathlib import Path

from ...processing.pbr_pack import write_solid_rgb_png
from .base import ReferenceGenerationRequest, ReferenceGenerationResult


class MockReferenceProvider:
    name = "mock"

    def generate(self, request: ReferenceGenerationRequest, job_dir: Path) -> ReferenceGenerationResult:
        output_path = job_dir / "reference.png"
        color = _color_from_prompt(request.prompt)
        write_solid_rgb_png(output_path, request.width, request.height, color)
        return ReferenceGenerationResult(
            provider=self.name,
            status="done",
            output_path="reference.png",
            message="Mock reference image generated",
            metadata={"width": request.width, "height": request.height},
        )


def _color_from_prompt(prompt: str) -> tuple[int, int, int]:
    seed = sum(prompt.encode("utf-8")) if prompt else 128
    return (80 + seed % 120, 80 + (seed * 3) % 120, 80 + (seed * 7) % 120)
