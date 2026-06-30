"""Material Palette PBR provider.

This provider invokes an external Material Palette installation through a fully
configurable command. Local tests use fake outputs and never require the real
model, CUDA, or repository.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from ...config import get_settings
from ...processing.pbr_pack import MaterialTextureSpec, generate_texture_set_from_sources
from ...processing.validation import sanitize_material_name
from .base import PBRGenerationRequest, PBRGenerationResult, PBRProviderError
from .mock_pbr_provider import MockPBRProvider


BASECOLOR_KEYWORDS = ("albedo", "basecolor", "base_color", "diffuse", "color")
NORMAL_KEYWORDS = ("normal", "nrm")
ROUGHNESS_KEYWORDS = ("roughness", "rough")


@dataclass(frozen=True)
class MaterialPaletteConfig:
    material_palette_repo_path: str = ""
    conda_env: str = ""
    command_template: str = ""
    timeout: float = 900.0
    output_dir: str = ""


class MaterialPaletteProvider:
    name = "material_palette"

    def __init__(self, config: MaterialPaletteConfig | None = None) -> None:
        self.config = config or load_material_palette_config()

    def generate(self, request: PBRGenerationRequest, job_dir: Path) -> PBRGenerationResult:
        log_path = _log_path(job_dir)
        try:
            return self._generate_with_material_palette(request, job_dir, log_path)
        except Exception as exc:
            _append_log(log_path, f"fallback reason: {exc}")
            if request.fallback_to_mock:
                _append_log(log_path, "falling back to MockPBRProvider")
                result = MockPBRProvider().generate(request, job_dir)
                return PBRGenerationResult(
                    provider=result.provider,
                    status=result.status,
                    materials=result.materials,
                    textures=result.textures,
                    metadata={"fallback_reason": str(exc), "fallback_from": self.name},
                )
            if isinstance(exc, PBRProviderError):
                raise
            raise PBRProviderError(502, f"Material Palette failed: {exc}") from exc

    def _generate_with_material_palette(self, request: PBRGenerationRequest, job_dir: Path, log_path: Path) -> PBRGenerationResult:
        if not self.config.command_template:
            raise PBRProviderError(400, "material_palette command_template is not configured")

        input_dir, reference_path, masks_dir = self._prepare_input_dir(job_dir)
        output_dir = self._resolve_output_dir(job_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        command = self._render_command(job_dir, input_dir, reference_path, masks_dir, output_dir)
        _append_log(log_path, f"calling command: {command}")
        _append_log(log_path, f"input dir: {input_dir}")
        _append_log(log_path, f"output dir: {output_dir}")

        completed = subprocess.run(
            command,
            cwd=self._cwd(job_dir),
            shell=True,
            capture_output=True,
            text=True,
            timeout=self.config.timeout,
        )
        _append_log(log_path, f"return code: {completed.returncode}")
        if completed.stdout:
            _append_log(log_path, f"stdout:\n{completed.stdout}")
        if completed.stderr:
            _append_log(log_path, f"stderr:\n{completed.stderr}")
        if completed.returncode != 0:
            raise PBRProviderError(502, f"Material Palette command failed with code {completed.returncode}")

        textures: dict[str, dict[str, str]] = {}
        for material in request.materials:
            material_name = sanitize_material_name(material.name)
            sources = collect_material_outputs(output_dir, material_name)
            _append_log(log_path, f"collected files for {material_name}: {_format_sources(sources)}")
            textures[material_name] = generate_texture_set_from_sources(
                job_dir,
                MaterialTextureSpec(name=material_name, metallic=material.metallic),
                sources,
                request.texture_size,
            )

        return PBRGenerationResult(
            provider=self.name,
            status="done",
            materials=list(textures.keys()),
            textures=textures,
            metadata={"output_dir": str(output_dir), "input_dir": str(input_dir)},
        )

    def _prepare_input_dir(self, job_dir: Path) -> tuple[Path, Path, Path]:
        input_dir = job_dir / "material_palette_input"
        if input_dir.exists():
            shutil.rmtree(input_dir)
        masks_dir = input_dir / "masks"
        masks_dir.mkdir(parents=True, exist_ok=True)

        reference_path = _find_reference(job_dir)
        copied_reference = input_dir / reference_path.name
        shutil.copyfile(reference_path, copied_reference)

        for mask_path in sorted((job_dir / "masks").glob("*.png")):
            shutil.copyfile(mask_path, masks_dir / mask_path.name)
        return input_dir, copied_reference, masks_dir

    def _resolve_output_dir(self, job_dir: Path) -> Path:
        if not self.config.output_dir:
            return job_dir / "material_palette_output"
        output_dir = Path(_render_config_string(self.config.output_dir, {"job_dir": str(job_dir)}))
        if not output_dir.is_absolute():
            output_dir = job_dir / output_dir
        return output_dir

    def _render_command(self, job_dir: Path, input_dir: Path, reference_path: Path, masks_dir: Path, output_dir: Path) -> str:
        values = {
            "repo_path": self.config.material_palette_repo_path,
            "conda_env": self.config.conda_env,
            "job_dir": str(job_dir),
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "reference_path": str(reference_path),
            "masks_dir": str(masks_dir),
        }
        return _render_config_string(self.config.command_template, values)

    def _cwd(self, job_dir: Path) -> str:
        if self.config.material_palette_repo_path:
            return str(Path(self.config.material_palette_repo_path))
        return str(job_dir)


def collect_material_outputs(output_dir: Path, material_name: str) -> dict[str, Path]:
    files = sorted(
        path for path in output_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )
    return {
        "basecolor": _choose_file(files, material_name, BASECOLOR_KEYWORDS),
        "normal": _choose_file(files, material_name, NORMAL_KEYWORDS),
        "roughness": _choose_file(files, material_name, ROUGHNESS_KEYWORDS),
    }


def load_material_palette_config() -> MaterialPaletteConfig:
    file_config = _config_from_file()
    env_config = {
        "material_palette_repo_path": os.getenv("MATERIAL_PALETTE_REPO_PATH", ""),
        "conda_env": os.getenv("MATERIAL_PALETTE_CONDA_ENV", ""),
        "command_template": os.getenv("MATERIAL_PALETTE_COMMAND_TEMPLATE", ""),
        "timeout": os.getenv("MATERIAL_PALETTE_TIMEOUT", ""),
        "output_dir": os.getenv("MATERIAL_PALETTE_OUTPUT_DIR", ""),
    }
    merged = {**file_config, **{key: value for key, value in env_config.items() if value not in ("", None)}}
    return MaterialPaletteConfig(
        material_palette_repo_path=str(merged.get("material_palette_repo_path", "")),
        conda_env=str(merged.get("conda_env", "")),
        command_template=str(merged.get("command_template", "")),
        timeout=float(merged.get("timeout", 900.0)),
        output_dir=str(merged.get("output_dir", "")),
    )


def _config_from_file() -> dict[str, Any]:
    settings = get_settings()
    candidates = []
    if settings.provider_config_path:
        candidates.append(settings.provider_config_path)
    candidates.extend([Path("server_config.yaml"), Path("server_config.yml"), Path("server_config.json")])
    for path in candidates:
        if not path.is_file():
            continue
        data = _read_config_file(path)
        config = (
            data.get("pbr_providers", {}).get("material_palette")
            or data.get("providers", {}).get("pbr", {}).get("material_palette")
            or {}
        )
        if config:
            return _expand_env(config)
    return {}


def _read_config_file(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to read YAML provider config") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"provider config must be an object: {path}")
    return data


def _choose_file(files: list[Path], material_name: str, keywords: tuple[str, ...]) -> Path | None:
    material_token = material_name.lower()
    matching = [path for path in files if any(keyword in path.as_posix().lower() for keyword in keywords)]
    preferred = [path for path in matching if material_token in path.as_posix().lower()]
    return (preferred or matching or [None])[0]


def _find_reference(job_dir: Path) -> Path:
    for name in ("reference.png", "reference.jpg", "reference.jpeg"):
        path = job_dir / name
        if path.is_file():
            return path
    raise PBRProviderError(409, "Material Palette input requires reference.png, reference.jpg, or reference.jpeg")


def _format_sources(sources: dict[str, Path | None]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sources.items() if value) or "<none>"


def _log_path(job_dir: Path) -> Path:
    path = job_dir / "logs" / "material_palette.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append_log(path: Path, message: str) -> None:
    path.write_text((path.read_text(encoding="utf-8") if path.exists() else "") + message + "\n", encoding="utf-8")


def _render_config_string(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return os.path.expandvars(rendered)


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value
