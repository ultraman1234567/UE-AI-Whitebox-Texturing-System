from __future__ import annotations

from ...config import get_settings
from .base import MaskProvider, MaskProviderError
from .mock_mask_provider import MockMaskProvider
from .sam_provider import SAMMaskProvider
from .user_mask_provider import UserMaskProvider


def get_mask_provider(provider_name: str | None = None) -> MaskProvider:
    settings = get_settings()
    name = (provider_name or settings.default_mask_provider or "mock").strip().lower()
    if name in {"mock", "mock_sam"}:
        return MockMaskProvider()
    if name in {"user_upload", "user_mask"}:
        return UserMaskProvider()
    if name in {"sam", "sam_auto"}:
        if not settings.enable_external_providers:
            raise MaskProviderError(403, "SAM provider is disabled; set ENABLE_EXTERNAL_PROVIDERS=true on the server")
        return SAMMaskProvider()
    raise MaskProviderError(400, f"unknown mask provider: {name}")
