"""Doubao reference provider as a generic configurable HTTP adapter.

No Doubao API details are hard-coded here. Configure endpoint, model, headers,
request_template, and response_mapping on the server.
"""

from .config import ReferenceProviderConfig, load_reference_provider_config
from .custom_http_provider import CustomHTTPReferenceProvider


class DoubaoReferenceProvider(CustomHTTPReferenceProvider):
    name = "doubao"

    def __init__(self, config: ReferenceProviderConfig | None = None) -> None:
        self.config = config or load_reference_provider_config(self.name)
