"""Shared input validation helpers."""

import re


class ValidationError(ValueError):
    """Raised when user-controlled names are unsafe."""


def sanitize_material_name(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValidationError("material_name is required")
    if "/" in raw or "\\" in raw or ".." in raw:
        raise ValidationError("material_name must not contain path traversal characters")

    name = re.sub(r"[^a-z0-9_]+", "_", raw.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValidationError("material_name must contain only letters, numbers, and underscores")
    return name
