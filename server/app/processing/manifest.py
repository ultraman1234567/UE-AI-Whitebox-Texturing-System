"""Manifest generation helpers."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


class ManifestError(ValueError):
    """Raised when manifest paths or contents are unsafe."""


def build_manifest(
    job_id: str,
    assignment: dict[str, Any],
    reference_image: str,
    masks: dict[str, str],
    texture_outputs: dict[str, dict[str, str]],
) -> dict[str, Any]:
    manifest = {
        "schema_version": "0.1.0",
        "job_id": job_id,
        "reference_image": reference_image,
        "unreal": assignment["unreal"],
        "materials": [],
    }

    _ensure_relative_zip_path(reference_image)
    for material in assignment.get("materials", []):
        name = material["name"]
        mask_path = masks.get(name, f"masks/{name}.png")
        textures = texture_outputs[name]
        _ensure_relative_zip_path(mask_path)
        for texture_path in textures.values():
            _ensure_relative_zip_path(texture_path)

        manifest["materials"].append(
            {
                "name": name,
                "display_name": material.get("display_name") or name,
                "mask": mask_path,
                "textures": textures,
                "assign_patterns": material.get("assign_patterns", []),
                "parameters": {
                    "tiling": material.get("tiling", 1.0),
                    "normal_strength": material.get("normal_strength", 1.0),
                    "roughness_mult": material.get("roughness_mult", 1.0),
                    "metallic": material.get("metallic", 0.0),
                },
            }
        )

    validate_manifest_paths(manifest)
    return manifest


def validate_manifest_paths(manifest: dict[str, Any]) -> None:
    _ensure_relative_zip_path(manifest["reference_image"])
    for material in manifest.get("materials", []):
        _ensure_relative_zip_path(material["mask"])
        for texture_path in material["textures"].values():
            _ensure_relative_zip_path(texture_path)


def _ensure_relative_zip_path(path: str) -> None:
    if not path or "\\" in path:
        raise ManifestError(f"manifest path must use zip-relative POSIX form: {path!r}")
    posix = PurePosixPath(path)
    windows = PureWindowsPath(path)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ManifestError(f"manifest path must be relative: {path!r}")
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise ManifestError(f"manifest path contains unsafe segments: {path!r}")
