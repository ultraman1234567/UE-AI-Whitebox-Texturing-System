"""Job orchestration for local mock milestones."""

from __future__ import annotations

from . import storage
from .processing.manifest import build_manifest
from .providers.pbr.base import PBRGenerationRequest, PBRMaterialRequest, PBRProviderError
from .providers.pbr.material_palette_provider import MaterialPaletteProvider
from .providers.pbr.mock_pbr_provider import MockPBRProvider


def generate_mock_pbr(job_id: str, texture_size: int) -> dict:
    return generate_pbr(job_id, provider_name="mock_pbr", texture_size=texture_size, fallback_to_mock=True)


def generate_pbr(job_id: str, provider_name: str, texture_size: int, fallback_to_mock: bool) -> dict:
    metadata = storage.load_job(job_id)
    assignment = storage.load_assignment(job_id)
    reference_image = metadata.get("reference_image")
    if not reference_image:
        raise storage.StorageError(409, "reference image has not been uploaded")

    materials = [
        PBRMaterialRequest(name=material["name"], metallic=material.get("metallic", 0.0))
        for material in assignment.get("materials", [])
    ]
    if not materials:
        raise storage.StorageError(409, "assignment must contain at least one material")

    provider = _get_pbr_provider(provider_name)
    result = provider.generate(
        PBRGenerationRequest(texture_size=texture_size, materials=materials, fallback_to_mock=fallback_to_mock),
        storage.require_job_dir(job_id),
    )
    manifest = build_manifest(
        job_id=job_id,
        assignment=assignment,
        reference_image=reference_image,
        masks=metadata.get("masks", {}),
        texture_outputs=result.textures,
    )
    storage.save_manifest(job_id, manifest)
    return {
        "job_id": job_id,
        "status": result.status,
        "provider": result.provider,
        "material_count": len(result.materials),
        "materials": result.materials,
        "manifest_path": "manifest.json",
        "textures": result.textures,
    }


def _get_pbr_provider(provider_name: str):
    name = (provider_name or "mock_pbr").strip().lower()
    if name == "mock_pbr":
        return MockPBRProvider()
    if name in {"material_palette", "materialpalette"}:
        return MaterialPaletteProvider()
    raise PBRProviderError(400, f"unknown PBR provider: {provider_name}")
