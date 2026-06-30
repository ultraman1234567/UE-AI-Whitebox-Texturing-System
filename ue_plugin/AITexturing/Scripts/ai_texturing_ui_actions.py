"""Server-side button actions for the AI Texturing editor panel.

These helpers run inside Unreal Python and use only the Python standard library.
They never store or transmit external provider API keys from the UE client.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import mimetypes
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from uuid import uuid4
from zipfile import ZipFile
from typing import Optional

try:
    import unreal  # type: ignore
except ImportError:
    unreal = None  # type: ignore


LOG_PREFIX = "[AITexturing]"


def run_action(action: str, server_url: str, job_id: str = "", local_package_path: str = "") -> None:
    server_url = server_url.rstrip("/")
    action = action.strip().lower()
    _log(f"Action '{action}' using server {server_url or '<empty>'}")

    if action == "create_job":
        result = create_job(server_url, local_package_path)
        _log(f"Created job_id={result.get('job_id')}. Paste it into the Job ID field and save settings.")
    elif action == "upload_reference":
        upload_reference(server_url, job_id, local_package_path)
    elif action == "generate_reference":
        generate_reference(server_url, job_id, local_package_path)
    elif action == "upload_mask":
        upload_masks(server_url, job_id, local_package_path)
    elif action == "auto_sam":
        auto_sam(server_url, job_id, local_package_path)
    elif action == "confirm_sam_masks":
        confirm_sam_masks(server_url, job_id, local_package_path)
    elif action == "submit_assignment":
        submit_assignment(server_url, job_id, local_package_path)
    elif action == "start_pbr":
        start_pbr(server_url, job_id, local_package_path)
    elif action == "poll_status":
        poll_status(server_url, job_id)
    elif action == "download_package":
        download_package(server_url, job_id, local_package_path)
    else:
        raise ValueError(f"Unknown AI Texturing action: {action}")


def create_job(server_url: str, package_path: str = "") -> dict:
    job_name = Path(package_path).stem if package_path else f"ue_job_{int(time.time())}"
    payload = {
        "job_name": job_name or "ue_ai_texturing_job",
        "description": "Created from Unreal AI Texturing panel",
        "ue_project_name": _project_name(),
    }
    return _request_json("POST", f"{server_url}/api/jobs", payload)


def upload_reference(server_url: str, job_id: str, package_path: str) -> None:
    _require_job(job_id)
    with _prepared_package(package_path) as root:
        reference = _find_first(root, ["reference.png", "reference.jpg", "reference.jpeg"])
        _multipart_upload(f"{server_url}/api/jobs/{job_id}/reference/upload", reference)
        _log(f"Uploaded reference: {reference}")


def generate_reference(server_url: str, job_id: str, package_path: str) -> None:
    _require_job(job_id)
    payload = _load_optional_json(
        package_path,
        ["reference_request.json"],
        {
            "provider": "mock",
            "prompt": "AI texturing reference for a whitebox Unreal scene",
            "width": 1024,
            "height": 1024,
            "fallback_to_mock": True,
        },
    )
    result = _request_json("POST", f"{server_url}/api/jobs/{job_id}/reference/generate", payload)
    _log(f"Generated reference with provider={result.get('provider')}: {result.get('path')}")
    if result.get("metadata", {}).get("fallback_from"):
        _log(f"Reference fallback: {result['metadata'].get('fallback_from')} -> mock")


def upload_masks(server_url: str, job_id: str, package_path: str) -> None:
    _require_job(job_id)
    with _prepared_package(package_path) as root:
        masks_dir = root / "masks"
        if not masks_dir.is_dir():
            raise FileNotFoundError(f"masks directory not found: {masks_dir}")
        masks = sorted(masks_dir.glob("*.png"))
        if not masks:
            raise FileNotFoundError(f"no PNG masks found in {masks_dir}")
        for mask in masks:
            material_name = mask.stem
            _multipart_upload(f"{server_url}/api/jobs/{job_id}/masks/upload/{material_name}", mask)
            _log(f"Uploaded mask {material_name}: {mask}")


def auto_sam(server_url: str, job_id: str, package_path: str) -> None:
    _require_job(job_id)
    payload = _load_optional_json(
        package_path,
        ["sam_request.json"],
        {"provider": "mock", "mode": "automatic", "params": {}, "fallback_to_mock": True},
    )
    result = _request_json("POST", f"{server_url}/api/jobs/{job_id}/masks/auto-sam", payload)
    sidecar = _write_workflow_sidecar(package_path, job_id, "sam_candidates", result)
    _log(f"Generated {len(result.get('candidates', []))} mask candidates with provider={result.get('provider')}")
    _log(f"Saved SAM candidate response: {sidecar}")


def confirm_sam_masks(server_url: str, job_id: str, package_path: str) -> None:
    _require_job(job_id)
    payload = _load_required_json(
        package_path,
        ["mask_confirm_requests.json", "mask_confirm.json", "sam_confirm_requests.json", "sam_confirm.json"],
    )
    requests = _normalize_confirm_payloads(payload)
    for confirm_request in requests:
        result = _request_json("POST", f"{server_url}/api/jobs/{job_id}/masks/confirm", confirm_request)
        _log(
            "Confirmed mask "
            f"{result.get('material_name')} from {result.get('candidate_mask_ids')} using {result.get('operation')}"
        )


def submit_assignment(server_url: str, job_id: str, package_path: str) -> None:
    _require_job(job_id)
    with _prepared_package(package_path) as root:
        assignment_path = root / "assignment.json"
        if assignment_path.is_file():
            payload = json.loads(assignment_path.read_text(encoding="utf-8"))
        else:
            payload = _assignment_from_manifest(root / "manifest.json")
        result = _request_json("POST", f"{server_url}/api/jobs/{job_id}/assignment", payload)
        _log(f"Submitted assignment: {result}")


def start_pbr(server_url: str, job_id: str, package_path: str = "") -> None:
    _require_job(job_id)
    payload = _load_optional_json(
        package_path,
        ["pbr_request.json"],
        {"provider": "material_palette", "texture_size": 1024, "fallback_to_mock": True},
    )
    result = _request_json("POST", f"{server_url}/api/jobs/{job_id}/pbr/generate", payload)
    _log(f"Started PBR generation: {result}")
    if payload.get("provider") != "mock_pbr" and result.get("provider") in {"mock", "mock_pbr"}:
        _log("PBR provider fell back to mock. Check server job logs for the Material Palette fallback reason.")


def poll_status(server_url: str, job_id: str) -> None:
    _require_job(job_id)
    result = _request_json("GET", f"{server_url}/api/jobs/{job_id}")
    _log(f"Job status: {result}")


def download_package(server_url: str, job_id: str, local_package_path: str) -> Path:
    _require_job(job_id)
    output = _download_output_path(job_id, local_package_path)
    response = _request_bytes("GET", f"{server_url}/api/jobs/{job_id}/download")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(response)
    _log(f"Downloaded package: {output}")
    return output


def _load_optional_json(package_path: str, names: list[str], default: dict) -> dict:
    if not package_path:
        return dict(default)
    try:
        with _prepared_package(package_path) as root:
            for name in names:
                path = root / name
                if path.is_file():
                    _log(f"Loaded request config: {path}")
                    return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(default)
    return dict(default)


def _load_required_json(package_path: str, names: list[str]):
    if not package_path:
        raise ValueError(f"Local Package Path is required and must contain one of: {names}")
    with _prepared_package(package_path) as root:
        for name in names:
            path = root / name
            if path.is_file():
                _log(f"Loaded request config: {path}")
                return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Package must contain one of: {names}")


def _normalize_confirm_payloads(payload) -> list[dict]:
    if isinstance(payload, dict) and "requests" in payload:
        payload = payload["requests"]
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return payload
    raise ValueError("SAM confirm config must be an object, a list, or {\"requests\": [...]}")


def _write_workflow_sidecar(package_path: str, job_id: str, label: str, payload: dict) -> Path:
    output = _workflow_output_path(package_path, job_id, label)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def _workflow_output_path(package_path: str, job_id: str, label: str) -> Path:
    if package_path:
        path = Path(package_path)
        if path.suffix:
            root = path.parent
        else:
            root = path
    elif unreal is not None:
        root = Path(unreal.Paths.project_saved_dir()) / "AITexturing"
    else:
        root = Path.cwd()
    return root / f"{job_id}_{label}.json"


def _request_json(method: str, url: str, payload: Optional[dict] = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _request_bytes(method: str, url: str) -> bytes:
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _multipart_upload(url: str, file_path: Path) -> dict:
    boundary = f"----AITexturing{uuid4().hex}"
    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"upload {file_path} failed: HTTP {exc.code} {detail}") from exc


@contextmanager
def _prepared_package(package_path: str):
    if not package_path:
        raise ValueError("Local Package Path is required for this action")
    path = Path(package_path)
    if path.is_dir():
        yield path
        return
    if path.is_file() and path.suffix.lower() == ".zip":
        temp_dir = Path(tempfile.mkdtemp(prefix="ai_texturing_ui_"))
        try:
            _safe_extract_zip(path, temp_dir)
            yield temp_dir
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return
    if path.is_file() and path.name.lower() == "manifest.json":
        yield path.parent
        return
    raise FileNotFoundError(f"Package path must be a zip, manifest.json, or extracted directory: {path}")


def _safe_extract_zip(zip_path: Path, destination: Path) -> None:
    root = destination.resolve()
    with ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            output = _resolve_member(root, member.filename)
            output.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, output.open("wb") as target:
                shutil.copyfileobj(source, target)


def _resolve_member(root: Path, relative_path: str) -> Path:
    if not relative_path or "\\" in relative_path:
        raise ValueError(f"Unsafe package path: {relative_path}")
    posix = PurePosixPath(relative_path)
    windows = PureWindowsPath(relative_path)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"Unsafe package path: {relative_path}")
    output = root.joinpath(*posix.parts).resolve()
    output.relative_to(root)
    return output


def _assignment_from_manifest(manifest_path: Path) -> dict:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"assignment.json or manifest.json is required: {manifest_path.parent}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    materials = []
    for material in manifest.get("materials", []):
        params = material.get("parameters", {})
        materials.append(
            {
                "name": material["name"],
                "display_name": material.get("display_name", material["name"]),
                "assign_patterns": material.get("assign_patterns", []),
                "tiling": params.get("tiling", 1.0),
                "normal_strength": params.get("normal_strength", 1.0),
                "roughness_mult": params.get("roughness_mult", 1.0),
                "metallic": params.get("metallic", 0.0),
            }
        )
    return {"unreal": manifest.get("unreal", {}), "materials": materials}


def _find_first(root: Path, names: list[str]) -> Path:
    for name in names:
        path = root / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"None of these files exist in {root}: {names}")


def _download_output_path(job_id: str, local_package_path: str) -> Path:
    if local_package_path:
        path = Path(local_package_path)
        if path.suffix.lower() == ".zip":
            return path
        if path.is_dir() or not path.suffix:
            return path / f"{job_id}_textures.zip"
    if unreal is not None:
        return Path(unreal.Paths.project_saved_dir()) / "AITexturing" / f"{job_id}_textures.zip"
    return Path.cwd() / f"{job_id}_textures.zip"


def _require_job(job_id: str) -> None:
    if not job_id:
        raise ValueError("Job ID is required for this action")


def _project_name() -> str:
    if unreal is not None:
        try:
            return unreal.SystemLibrary.get_project_name()
        except Exception:
            pass
    return "UnrealProject"


def _log(message: str) -> None:
    if unreal is not None:
        unreal.log(f"{LOG_PREFIX} {message}")
    else:
        print(f"{LOG_PREFIX} {message}")
