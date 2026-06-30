from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any

from ...config import get_settings


@dataclass(frozen=True)
class ReferenceProviderConfig:
    endpoint: str = ""
    model: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    request_template: Any = field(default_factory=dict)
    response_mapping: dict[str, str] = field(default_factory=dict)
    workflow_path: str = ""
    field_mappings: dict[str, str] = field(default_factory=dict)
    timeout: float = 120.0


def load_reference_provider_config(provider_name: str) -> ReferenceProviderConfig:
    provider_key = provider_name.lower()
    file_config = _config_from_file(provider_key)
    env_config = _config_from_env(provider_key)
    merged = {**file_config, **{key: value for key, value in env_config.items() if value not in ("", None, {}, [])}}
    return ReferenceProviderConfig(
        endpoint=str(merged.get("endpoint", "")),
        model=str(merged.get("model", "")),
        headers=_string_map(merged.get("headers", {})),
        request_template=merged.get("request_template", {}),
        response_mapping=_string_map(merged.get("response_mapping", {})),
        workflow_path=str(merged.get("workflow_path", "")),
        field_mappings=_string_map(merged.get("field_mappings", {})),
        timeout=float(merged.get("timeout", 120.0)),
    )


def _config_from_file(provider_key: str) -> dict[str, Any]:
    settings = get_settings()
    candidates = []
    if settings.provider_config_path:
        candidates.append(settings.provider_config_path)
    candidates.extend([Path("server_config.yaml"), Path("server_config.yml"), Path("server_config.json")])

    for path in candidates:
        if not path.is_file():
            continue
        data = _read_config_file(path)
        provider_config = (
            data.get("reference_providers", {}).get(provider_key)
            or data.get("providers", {}).get("reference", {}).get(provider_key)
            or {}
        )
        if provider_config:
            return _expand_env(provider_config)
    return {}


def _config_from_env(provider_key: str) -> dict[str, Any]:
    prefix = f"REFERENCE_{provider_key.upper()}_"
    return {
        "endpoint": os.getenv(prefix + "ENDPOINT", ""),
        "model": os.getenv(prefix + "MODEL", ""),
        "headers": _json_env(prefix + "HEADERS_JSON", {}),
        "request_template": _json_env(prefix + "REQUEST_TEMPLATE_JSON", {}),
        "response_mapping": _json_env(prefix + "RESPONSE_MAPPING_JSON", {}),
        "workflow_path": os.getenv(prefix + "WORKFLOW_PATH", ""),
        "field_mappings": _json_env(prefix + "FIELD_MAPPINGS_JSON", {}),
        "timeout": os.getenv(prefix + "TIMEOUT", ""),
    }


def _read_config_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to read YAML provider config") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"provider config must be an object: {path}")
    return data


def _json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name)
    if not raw:
        return default
    return _expand_env(json.loads(raw))


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}
