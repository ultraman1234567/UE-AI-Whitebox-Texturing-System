import base64
import json
from pathlib import Path
from typing import Any

from server.app.providers.reference.base import ReferenceGenerationRequest
from server.app.providers.reference.config import ReferenceProviderConfig
from server.app.providers.reference.comfyui_provider import ComfyUIReferenceProvider
from server.app.providers.reference.custom_http_provider import CustomHTTPReferenceProvider
from server.app.providers.reference.doubao_provider import DoubaoReferenceProvider


PNG_1X1 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00"
    b"\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
).decode("ascii")


class CapturingHTTPProvider(CustomHTTPReferenceProvider):
    name = "custom_http"

    def __init__(self, config: ReferenceProviderConfig) -> None:
        super().__init__(config=config)
        self.payload: Any = None

    def _post_json(self, endpoint: str, payload: Any) -> tuple[bytes, str]:
        self.payload = payload
        return json.dumps({"data": [{"b64_json": PNG_1X1}]}).encode("utf-8"), "application/json"


def test_custom_http_template_and_response_mapping(tmp_path: Path) -> None:
    provider = CapturingHTTPProvider(
        ReferenceProviderConfig(
            endpoint="https://example.invalid/generate",
            model="mock-image-model",
            headers={"Authorization": "Bearer server-side-only"},
            request_template={
                "model": "{model}",
                "prompt": "{prompt}",
                "negative": "{negative_prompt}",
                "seed": "{seed}",
            },
            response_mapping={"image_base64": "data.0.b64_json"},
        )
    )

    result = provider.generate(
        ReferenceGenerationRequest(prompt="concrete wall", negative_prompt="watermark", seed=7),
        tmp_path,
    )

    assert provider.payload == {
        "model": "mock-image-model",
        "prompt": "concrete wall",
        "negative": "watermark",
        "seed": 7,
    }
    assert result.output_path == "reference.png"
    assert (tmp_path / "reference.png").is_file()


def test_doubao_provider_is_configurable_adapter() -> None:
    config = ReferenceProviderConfig(
        endpoint="https://example.invalid/doubao-like",
        model="configured-model",
        request_template={"model": "{model}", "prompt": "{prompt}"},
    )
    provider = DoubaoReferenceProvider(config=config)

    payload = provider._build_payload(ReferenceGenerationRequest(prompt="factory floor"))

    assert provider.name == "doubao"
    assert payload == {"model": "configured-model", "prompt": "factory floor"}


class CapturingComfyUIProvider(ComfyUIReferenceProvider):
    def __init__(self, config: ReferenceProviderConfig) -> None:
        super().__init__(config=config)
        self.payload: Any = None

    def _post_json(self, endpoint: str, payload: Any) -> tuple[bytes, str]:
        self.payload = payload
        return json.dumps({"image_base64": PNG_1X1}).encode("utf-8"), "application/json"


def test_comfyui_workflow_template_and_field_mappings(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "6": {"inputs": {"text": "{prompt}"}},
                "7": {"inputs": {"text": ""}},
                "3": {"inputs": {"seed": 0}},
                "10": {"inputs": {"image": ""}},
            }
        ),
        encoding="utf-8",
    )
    provider = CapturingComfyUIProvider(
        ReferenceProviderConfig(
            endpoint="http://127.0.0.1:8188/prompt",
            workflow_path=str(workflow_path),
            field_mappings={
                "negative_prompt": "7.inputs.text",
                "seed": "3.inputs.seed",
                "input_images.whitebox": "10.inputs.image",
            },
            response_mapping={"image_base64": "image_base64"},
        )
    )

    result = provider.generate(
        ReferenceGenerationRequest(
            prompt="clean sci-fi corridor",
            negative_prompt="text, watermark",
            seed=42,
            input_images={"whitebox": "whitebox.png"},
        ),
        tmp_path,
    )

    workflow = provider.payload["prompt"]
    assert workflow["6"]["inputs"]["text"] == "clean sci-fi corridor"
    assert workflow["7"]["inputs"]["text"] == "text, watermark"
    assert workflow["3"]["inputs"]["seed"] == 42
    assert workflow["10"]["inputs"]["image"] == "whitebox.png"
    assert result.output_path == "reference.png"
