"""Mock PBR provider skeleton for local, offline development."""

from pathlib import Path

from ...processing.pbr_pack import MaterialTextureSpec, generate_mock_texture_sets
from .base import PBRGenerationRequest, PBRGenerationResult


class MockPBRProvider:
    name = "mock_pbr"

    def generate(self, request: PBRGenerationRequest, job_dir: Path) -> PBRGenerationResult:
        specs = [MaterialTextureSpec(name=material.name, metallic=material.metallic) for material in request.materials]
        textures = generate_mock_texture_sets(job_dir, specs, request.texture_size)
        return PBRGenerationResult(
            provider=self.name,
            status="done",
            materials=list(textures.keys()),
            textures=textures,
        )
