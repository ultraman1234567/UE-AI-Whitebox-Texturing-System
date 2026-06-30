from pathlib import Path

from fastapi.testclient import TestClient

from server.app.providers.reference.base import ReferenceGenerationRequest
from server.app.providers.reference.mock_reference_provider import MockReferenceProvider
from server.app.providers.reference.registry import get_reference_provider
from server.tests.helpers import create_job
from server.tests.png_utils import read_png_first_pixel


def test_upload_reference(client: TestClient, jobs_root: Path) -> None:
    job_id = create_job(client)

    response = client.post(
        f"/api/jobs/{job_id}/reference/upload",
        files={"file": ("reference.png", b"fake-png-bytes", "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "reference.png"
    assert body["bytes_written"] == len(b"fake-png-bytes")
    assert (jobs_root / job_id / "reference.png").read_bytes() == b"fake-png-bytes"


def test_mock_reference_provider_interface(tmp_path: Path) -> None:
    provider = MockReferenceProvider()
    result = provider.generate(ReferenceGenerationRequest(prompt="mock corridor", width=2, height=2), tmp_path)

    assert provider.name == "mock"
    assert result.provider == "mock"
    assert result.status == "done"
    assert result.output_path == "reference.png"
    assert (tmp_path / "reference.png").is_file()
    assert read_png_first_pixel((tmp_path / "reference.png").read_bytes()) != (0, 0, 0)


def test_generate_reference_mock_api(client: TestClient, jobs_root: Path) -> None:
    job_id = create_job(client)

    response = client.post(
        f"/api/jobs/{job_id}/reference/generate",
        json={"provider": "mock", "prompt": "industrial concrete corridor", "width": 4, "height": 4},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["path"] == "reference.png"
    assert (jobs_root / job_id / "reference.png").is_file()

    status = client.get(f"/api/jobs/{job_id}").json()
    assert status["reference_image"] == "reference.png"
    assert status["stage"] == "reference"


def test_generate_reference_falls_back_to_mock_when_external_disabled(client: TestClient, jobs_root: Path) -> None:
    job_id = create_job(client)

    response = client.post(
        f"/api/jobs/{job_id}/reference/generate",
        json={
            "provider": "custom_http",
            "prompt": "fallback reference",
            "width": 4,
            "height": 4,
            "fallback_to_mock": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["metadata"]["fallback_from"] == "custom_http"
    assert (jobs_root / job_id / "reference.png").is_file()


def test_external_reference_provider_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_EXTERNAL_PROVIDERS", raising=False)

    try:
        get_reference_provider("custom_http")
    except Exception as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("custom_http should be disabled by default")
