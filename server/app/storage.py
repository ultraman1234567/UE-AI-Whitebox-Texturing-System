"""Local job storage helpers.

All files for a job live under server_data/jobs/{job_id}/ by default. Routes
delegate filesystem work here so user-controlled paths stay validated in one
place.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
import re
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import UploadFile

from .config import get_settings
from .processing.mask_utils import MaskImageError, combine_mask_files, write_mask_png
from .processing.validation import ValidationError, sanitize_material_name

_JOB_ID_RE = re.compile(r"^job_[0-9a-f]{12}$")
_REFERENCE_SUFFIXES = {".png", ".jpg", ".jpeg"}
_MASK_SUFFIXES = {".png"}
_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "application/octet-stream"}


class StorageError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def jobs_root() -> Path:
    root = get_settings().job_storage_dir
    return root.resolve()


def ensure_jobs_root() -> Path:
    root = jobs_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_job_id(job_id: str) -> str:
    if not _JOB_ID_RE.fullmatch(job_id):
        raise StorageError(400, "invalid job_id")
    return job_id


def job_dir(job_id: str) -> Path:
    validate_job_id(job_id)
    root = ensure_jobs_root()
    path = (root / job_id).resolve()
    _ensure_inside(path, root)
    return path


def require_job_dir(job_id: str) -> Path:
    path = job_dir(job_id)
    if not path.exists() or not path.is_dir():
        raise StorageError(404, "job not found")
    return path


def create_job(payload: dict[str, Any]) -> dict[str, Any]:
    root = ensure_jobs_root()
    job_id = f"job_{uuid4().hex[:12]}"
    path = (root / job_id).resolve()
    _ensure_inside(path, root)
    path.mkdir(parents=False, exist_ok=False)
    (path / "masks").mkdir()
    (path / "logs").mkdir()

    metadata = {
        "job_id": job_id,
        "status": "created",
        "stage": "created",
        "progress": 0.0,
        "message": "Job created",
        "job_name": payload["job_name"],
        "description": payload.get("description", ""),
        "ue_project_name": payload.get("ue_project_name", ""),
        "reference_image": None,
        "masks": {},
        "mask_candidates": {},
        "assignment": None,
    }
    _write_json(path / "job.json", metadata)
    return metadata


def load_job(job_id: str) -> dict[str, Any]:
    path = require_job_dir(job_id)
    metadata_path = path / "job.json"
    if not metadata_path.exists():
        raise StorageError(500, "job metadata is missing")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


async def save_reference_upload(job_id: str, upload: UploadFile) -> dict[str, Any]:
    path = require_job_dir(job_id)
    suffix = _validate_upload(upload, _REFERENCE_SUFFIXES)
    output_name = f"reference{suffix}"
    bytes_written = await _write_upload(upload, path / output_name)

    metadata = load_job(job_id)
    metadata["status"] = "reference_uploaded"
    metadata["stage"] = "reference"
    metadata["message"] = "Reference image uploaded"
    metadata["reference_image"] = output_name
    _write_json(path / "job.json", metadata)

    return {
        "job_id": job_id,
        "status": "uploaded",
        "path": output_name,
        "filename": upload.filename or output_name,
        "bytes_written": bytes_written,
    }


async def save_mask_upload(job_id: str, material_name: str, upload: UploadFile) -> dict[str, Any]:
    try:
        safe_name = sanitize_material_name(material_name)
    except ValidationError as exc:
        raise StorageError(400, str(exc)) from exc

    path = require_job_dir(job_id)
    _validate_upload(upload, _MASK_SUFFIXES)
    masks_dir = path / "masks"
    masks_dir.mkdir(exist_ok=True)
    output_path = masks_dir / f"{safe_name}.png"
    bytes_written = await _write_upload(upload, output_path)

    relative_path = f"masks/{safe_name}.png"
    metadata = load_job(job_id)
    metadata["status"] = "mask_uploaded"
    metadata["stage"] = "masks"
    metadata["message"] = f"Mask uploaded for {safe_name}"
    metadata.setdefault("masks", {})[safe_name] = relative_path
    _write_json(path / "job.json", metadata)

    return {
        "job_id": job_id,
        "status": "uploaded",
        "path": relative_path,
        "filename": upload.filename or f"{safe_name}.png",
        "bytes_written": bytes_written,
        "material_name": safe_name,
    }


def save_assignment(job_id: str, assignment: dict[str, Any]) -> dict[str, Any]:
    path = require_job_dir(job_id)
    materials = assignment.get("materials", [])
    material_names: list[str] = []
    for material in materials:
        try:
            safe_name = sanitize_material_name(material["name"])
        except (KeyError, ValidationError) as exc:
            raise StorageError(400, f"invalid material assignment name: {exc}") from exc
        material["name"] = safe_name
        material_names.append(safe_name)

    _write_json(path / "assignment.json", assignment)
    metadata = load_job(job_id)
    metadata["status"] = "assignment_saved"
    metadata["stage"] = "assignment"
    metadata["message"] = "Assignment saved"
    metadata["assignment"] = "assignment.json"
    _write_json(path / "job.json", metadata)

    return {
        "job_id": job_id,
        "status": "saved",
        "path": "assignment.json",
        "material_count": len(material_names),
        "materials": material_names,
    }


def load_assignment(job_id: str) -> dict[str, Any]:
    path = require_job_dir(job_id)
    assignment_path = path / "assignment.json"
    if not assignment_path.exists():
        raise StorageError(409, "assignment has not been submitted")
    return json.loads(assignment_path.read_text(encoding="utf-8"))


def save_manifest(job_id: str, manifest: dict[str, Any]) -> None:
    path = require_job_dir(job_id)
    _write_json(path / "manifest.json", manifest)

    metadata = load_job(job_id)
    metadata["status"] = "pbr_generated"
    metadata["stage"] = "pbr_generation"
    metadata["progress"] = 1.0
    metadata["message"] = "PBR textures generated"
    metadata["manifest"] = "manifest.json"
    _write_json(path / "job.json", metadata)


def mark_reference_generated(job_id: str, relative_path: str, provider: str) -> dict[str, Any]:
    path = require_job_dir(job_id)
    source = (path / relative_path).resolve()
    _ensure_inside(source, path.resolve())
    if not source.is_file():
        raise StorageError(500, f"generated reference is missing: {relative_path}")

    metadata = load_job(job_id)
    metadata["status"] = "reference_generated"
    metadata["stage"] = "reference"
    metadata["message"] = f"Reference image generated by {provider}"
    metadata["reference_image"] = relative_path
    metadata["reference_provider"] = provider
    _write_json(path / "job.json", metadata)
    return metadata


def save_mask_candidates(job_id: str, provider: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path = require_job_dir(job_id)
    candidate_dir = path / "candidate_masks"
    candidate_dir.mkdir(exist_ok=True)

    candidate_map: dict[str, dict[str, Any]] = {}
    response_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        mask_id = str(candidate["mask_id"])
        relative_path = str(candidate["path"])
        source = (path / relative_path).resolve()
        _ensure_inside(source, path.resolve())
        if not source.is_file():
            raise StorageError(500, f"candidate mask is missing: {relative_path}")

        stored = {
            "mask_id": mask_id,
            "path": relative_path,
            "bbox": list(candidate["bbox"]),
            "area": int(candidate["area"]),
            "score": float(candidate["score"]),
            "preview_url": f"/api/jobs/{job_id}/masks/candidates/{mask_id}/preview",
        }
        candidate_map[mask_id] = stored
        response_candidates.append(stored)

    _write_json(candidate_dir / "candidates.json", {"provider": provider, "candidates": response_candidates})
    metadata = load_job(job_id)
    metadata["status"] = "mask_candidates_generated"
    metadata["stage"] = "mask_candidates"
    metadata["message"] = f"Candidate masks generated by {provider}"
    metadata["mask_candidates"] = candidate_map
    _write_json(path / "job.json", metadata)
    return response_candidates


def candidate_preview_path(job_id: str, mask_id: str) -> Path:
    path = require_job_dir(job_id)
    candidate = _load_candidate(path, mask_id)
    source = (path / candidate["path"]).resolve()
    _ensure_inside(source, path.resolve())
    if not source.is_file():
        raise StorageError(404, "candidate mask preview not found")
    return source


def confirm_mask_candidates(job_id: str, material_name: str, candidate_mask_ids: list[str], operation: str) -> dict[str, Any]:
    try:
        safe_name = sanitize_material_name(material_name)
    except ValidationError as exc:
        raise StorageError(400, str(exc)) from exc

    path = require_job_dir(job_id)
    candidates = [_load_candidate(path, mask_id) for mask_id in candidate_mask_ids]
    candidate_paths = []
    for candidate in candidates:
        candidate_path = (path / candidate["path"]).resolve()
        _ensure_inside(candidate_path, path.resolve())
        if not candidate_path.is_file():
            raise StorageError(404, f"candidate mask not found: {candidate['mask_id']}")
        candidate_paths.append(candidate_path)

    try:
        width, height, pixels = combine_mask_files(candidate_paths, operation)
    except MaskImageError as exc:
        raise StorageError(400, str(exc)) from exc

    masks_dir = path / "masks"
    masks_dir.mkdir(exist_ok=True)
    output_path = masks_dir / f"{safe_name}.png"
    write_mask_png(output_path, width, height, pixels)

    relative_path = f"masks/{safe_name}.png"
    metadata = load_job(job_id)
    metadata["status"] = "mask_confirmed"
    metadata["stage"] = "masks"
    metadata["message"] = f"Material mask confirmed for {safe_name}"
    metadata.setdefault("masks", {})[safe_name] = relative_path
    _write_json(path / "job.json", metadata)

    return {
        "job_id": job_id,
        "status": "saved",
        "material_name": safe_name,
        "path": relative_path,
        "operation": operation,
        "candidate_mask_ids": candidate_mask_ids,
    }


def build_result_zip(job_id: str) -> tuple[str, bytes]:
    path = require_job_dir(job_id)
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        raise StorageError(409, "manifest has not been generated")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = _manifest_entries(manifest)
    package = BytesIO()
    with ZipFile(package, "w", compression=ZIP_DEFLATED) as archive:
        archive.write(manifest_path, "manifest.json")
        for relative_path in entries:
            source = (path / relative_path).resolve()
            _ensure_inside(source, path.resolve())
            if not source.exists() or not source.is_file():
                raise StorageError(500, f"package file is missing: {relative_path}")
            archive.write(source, relative_path)
    return f"{job_id}_textures.zip", package.getvalue()


def _validate_upload(upload: UploadFile, allowed_suffixes: set[str]) -> str:
    filename = upload.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_suffixes:
        allowed = ", ".join(sorted(allowed_suffixes))
        raise StorageError(400, f"unsupported file extension; allowed: {allowed}")
    if upload.content_type and upload.content_type not in _IMAGE_MIME_TYPES:
        raise StorageError(400, "unsupported upload content type")
    return suffix


async def _write_upload(upload: UploadFile, destination: Path) -> int:
    root = ensure_jobs_root()
    output = destination.resolve()
    _ensure_inside(output, root)

    max_bytes = get_settings().max_upload_bytes
    bytes_written = 0
    try:
        with output.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise StorageError(413, "uploaded file is too large")
                handle.write(chunk)
    except Exception:
        if output.exists():
            output.unlink()
        raise

    if bytes_written == 0:
        raise StorageError(400, "uploaded file is empty")
    return bytes_written


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    root = ensure_jobs_root()
    output = path.resolve()
    _ensure_inside(output, root)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_inside(path: Path, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise StorageError(400, "resolved path escapes job storage root") from exc


def _load_candidate(job_dir: Path, mask_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"mask_[A-Za-z0-9_-]+", mask_id):
        raise StorageError(400, "invalid candidate mask_id")
    candidates_path = job_dir / "candidate_masks" / "candidates.json"
    if not candidates_path.is_file():
        raise StorageError(409, "candidate masks have not been generated")
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    for candidate in payload.get("candidates", []):
        if candidate.get("mask_id") == mask_id:
            return candidate
    raise StorageError(404, f"candidate mask not found: {mask_id}")


def _manifest_entries(manifest: dict[str, Any]) -> list[str]:
    entries: list[str] = []
    reference = manifest.get("reference_image")
    if reference:
        entries.append(reference)
    for material in manifest.get("materials", []):
        mask = material.get("mask")
        if mask:
            entries.append(mask)
        entries.extend(material.get("textures", {}).values())
    return sorted(set(entries))
