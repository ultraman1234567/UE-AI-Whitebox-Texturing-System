from __future__ import annotations

import base64
import json
from pathlib import Path
import re
from typing import Any

from .base import ReferenceGenerationRequest

_TOKEN_RE = re.compile(r"\{([a-zA-Z0-9_.]+)\}")


def render_template(value: Any, request: ReferenceGenerationRequest, model: str = "") -> Any:
    context = {
        "provider": request.provider,
        "prompt": request.prompt,
        "negative_prompt": request.negative_prompt,
        "seed": request.seed,
        "width": request.width,
        "height": request.height,
        "strength": request.strength,
        "model": model,
        "input_images": request.input_images,
        "extra": request.extra,
    }
    return _render(value, context)


def get_path(data: Any, dotted_path: str) -> Any:
    current = data
    for part in dotted_path.split("."):
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(dotted_path)
    return current


def set_path(data: Any, dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    current = data
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(dotted_path)
    last = parts[-1]
    if isinstance(current, dict):
        current[last] = value
    elif isinstance(current, list):
        current[int(last)] = value
    else:
        raise KeyError(dotted_path)


def read_input_image(value: str, job_dir: Path) -> str:
    if not value:
        return ""
    path = Path(value)
    if not path.is_absolute():
        path = job_dir / value
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _render(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        full_match = _TOKEN_RE.fullmatch(value)
        if full_match:
            replacement = _lookup(context, full_match.group(1))
            return replacement
        return _TOKEN_RE.sub(lambda match: str(_lookup(context, match.group(1)) or ""), value)
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render(item, context) for key, item in value.items()}
    return value


def _lookup(context: dict[str, Any], dotted_path: str) -> Any:
    try:
        return get_path(context, dotted_path)
    except (KeyError, IndexError, ValueError, TypeError):
        return ""


def json_dumps_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")
