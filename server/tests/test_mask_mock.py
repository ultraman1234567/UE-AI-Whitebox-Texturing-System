from pathlib import Path

from fastapi.testclient import TestClient

from server.app.processing.validation import sanitize_material_name
from server.app.processing.mask_utils import read_mask_png
from server.app.providers.mask.base import MaskGenerationRequest
from server.app.providers.mask.mock_mask_provider import MockMaskProvider
from server.app.providers.mask.registry import get_mask_provider
from server.tests.helpers import create_job


def test_upload_mask_sanitizes_material_name(client: TestClient, jobs_root: Path) -> None:
    job_id = create_job(client)

    response = client.post(
        f"/api/jobs/{job_id}/masks/upload/Wall-Concrete",
        files={"file": ("mask.png", b"fake-mask-bytes", "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["material_name"] == "wall_concrete"
    assert body["path"] == "masks/wall_concrete.png"
    assert (jobs_root / job_id / "masks" / "wall_concrete.png").read_bytes() == b"fake-mask-bytes"


def test_upload_mask_rejects_path_traversal(client: TestClient) -> None:
    job_id = create_job(client)

    response = client.post(
        f"/api/jobs/{job_id}/masks/upload/bad..name",
        files={"file": ("mask.png", b"fake-mask-bytes", "image/png")},
    )

    assert response.status_code == 400


def test_sanitize_material_name() -> None:
    assert sanitize_material_name("Floor Tiles") == "floor_tiles"
    assert sanitize_material_name("rusty_metal") == "rusty_metal"


def test_mock_mask_provider_interface(tmp_path: Path) -> None:
    provider = MockMaskProvider()
    result = provider.generate(MaskGenerationRequest(material_name="floor_tiles", params={"width": 8, "height": 8}), tmp_path)

    assert provider.name == "mock"
    assert result.provider == "mock"
    assert result.status == "done"
    assert result.masks == ["floor_tiles"]
    assert len(result.candidates) == 3
    assert (tmp_path / result.candidates[0].path).is_file()


def test_auto_sam_mock_returns_candidates(client: TestClient, jobs_root: Path) -> None:
    job_id = create_job(client)

    response = client.post(
        f"/api/jobs/{job_id}/masks/auto-sam",
        json={"provider": "mock", "mode": "automatic", "params": {"width": 8, "height": 8}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert len(body["candidates"]) == 3
    first = body["candidates"][0]
    assert first["mask_id"] == "mask_001"
    assert first["bbox"] == [0, 0, 4, 8]
    assert first["area"] == 32
    assert first["preview_url"] == f"/api/jobs/{job_id}/masks/candidates/mask_001/preview"
    assert (jobs_root / job_id / "candidate_masks" / "mask_001.png").is_file()


def test_auto_sam_falls_back_to_mock_when_sam_disabled(client: TestClient) -> None:
    job_id = create_job(client)

    response = client.post(
        f"/api/jobs/{job_id}/masks/auto-sam",
        json={"provider": "sam", "params": {"width": 8, "height": 8}, "fallback_to_mock": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert len(body["candidates"]) == 3


def test_candidate_preview(client: TestClient) -> None:
    job_id = create_job(client)
    client.post(
        f"/api/jobs/{job_id}/masks/auto-sam",
        json={"provider": "mock", "params": {"width": 8, "height": 8}},
    )

    response = client.get(f"/api/jobs/{job_id}/masks/candidates/mask_001/preview")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_confirm_candidate_replace_as_material_mask(client: TestClient, jobs_root: Path) -> None:
    job_id = create_job(client)
    client.post(
        f"/api/jobs/{job_id}/masks/auto-sam",
        json={"provider": "mock", "params": {"width": 8, "height": 8}},
    )

    response = client.post(
        f"/api/jobs/{job_id}/masks/confirm",
        json={"material_name": "Wall Concrete", "candidate_mask_ids": ["mask_001"], "operation": "replace"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["material_name"] == "wall_concrete"
    assert body["path"] == "masks/wall_concrete.png"
    width, height, pixels = read_mask_png(jobs_root / job_id / "masks" / "wall_concrete.png")
    assert (width, height) == (8, 8)
    assert sum(pixels) == 32
    status = client.get(f"/api/jobs/{job_id}").json()
    assert status["masks"]["wall_concrete"] == "masks/wall_concrete.png"


def test_confirm_candidate_operations(client: TestClient, jobs_root: Path) -> None:
    job_id = create_job(client)
    client.post(
        f"/api/jobs/{job_id}/masks/auto-sam",
        json={"provider": "mock", "params": {"width": 8, "height": 8}},
    )

    cases = {
        "union": (["mask_001", "mask_002"], 64),
        "intersect": (["mask_001", "mask_003"], 8),
        "subtract": (["mask_001", "mask_003"], 24),
    }
    for operation, (mask_ids, expected_area) in cases.items():
        material = f"{operation}_material"
        response = client.post(
            f"/api/jobs/{job_id}/masks/confirm",
            json={"material_name": material, "candidate_mask_ids": mask_ids, "operation": operation},
        )
        assert response.status_code == 200
        _width, _height, pixels = read_mask_png(jobs_root / job_id / "masks" / f"{material}.png")
        assert sum(pixels) == expected_area


def test_sam_provider_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_EXTERNAL_PROVIDERS", raising=False)

    try:
        get_mask_provider("sam")
    except Exception as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("SAM provider should be disabled by default")
