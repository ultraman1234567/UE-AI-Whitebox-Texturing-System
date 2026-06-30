from __future__ import annotations

from ...config import get_settings
from .base import ReferenceImageProvider, ReferenceProviderError
from .comfyui_provider import ComfyUIReferenceProvider
from .custom_http_provider import CustomHTTPReferenceProvider
from .doubao_provider import DoubaoReferenceProvider
from .mock_reference_provider import MockReferenceProvider
from .user_upload_provider import UserUploadReferenceProvider


_LOCAL_PROVIDERS = {"mock", "user_upload"}
_EXTERNAL_PROVIDERS = {"custom_http", "doubao", "comfyui"}


def get_reference_provider(provider_name: str | None = None) -> ReferenceImageProvider:
    settings = get_settings()
    name = (provider_name or settings.default_reference_provider or "mock").strip().lower()
    if name in _EXTERNAL_PROVIDERS and not settings.enable_external_providers:
        raise ReferenceProviderError(403, f"reference provider '{name}' is disabled; set ENABLE_EXTERNAL_PROVIDERS=true on the server")

    if name == "mock":
        return MockReferenceProvider()
    if name == "user_upload":
        return UserUploadReferenceProvider()
    if name == "custom_http":
        return CustomHTTPReferenceProvider()
    if name == "doubao":
        return DoubaoReferenceProvider()
    if name == "comfyui":
        return ComfyUIReferenceProvider()
    raise ReferenceProviderError(400, f"unknown reference provider: {name}")
