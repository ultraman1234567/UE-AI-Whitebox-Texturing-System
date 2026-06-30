import json
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from server.tests.helpers import create_job
from server.tests.png_utils import read_png_first_pixel


def test_milestone_1_api_flow(client: TestClient, jobs_root: Path) -> None:
    job_id = create_job(client)

    reference_response = client.post(
        f"/api/jobs/{job_id}/reference/upload",
        files={"file": ("reference.png", b"reference", "image/png")},
    )
    assert reference_response.status_code == 200

    mask_response = client.post(
        f"/api/jobs/{job_id}/masks/upload/floor_tiles",
        files={"file": ("mask.png", b"mask", "image/png")},
    )
    assert mask_response.status_code == 200

    assignment = {
        "unreal": {
            "master_material": "/Game/AI_Texturing/Materials/M_AI_PBR_Master.M_AI_PBR_Master",
            "texture_root": "/Game/AI_Texturing/Generated/Textures",
            "instance_root": "/Game/AI_Texturing/Generated/Instances",
        },
        "materials": [
            {
                "name": "floor_tiles",
                "display_name": "Floor Tiles",
                "assign_patterns": ["SM_Floor_*", "Floor_*", "*floor*"],
                "tiling": 4.0,
                "normal_strength": 1.2,
                "roughness_mult": 1.0,
                "metallic": 0.0,
            }
        ],
    }
    assignment_response = client.post(f"/api/jobs/{job_id}/assignment", json=assignment)

    assert assignment_response.status_code == 200
    assert assignment_response.json()["materials"] == ["floor_tiles"]
    assert (jobs_root / job_id / "reference.png").is_file()
    assert (jobs_root / job_id / "masks" / "floor_tiles.png").is_file()

    saved_assignment = json.loads((jobs_root / job_id / "assignment.json").read_text(encoding="utf-8"))
    assert saved_assignment["materials"][0]["name"] == "floor_tiles"

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["stage"] == "assignment"


def test_milestone_2_mock_pbr_zip_flow(client: TestClient) -> None:
    job_id = create_job(client)
    client.post(
        f"/api/jobs/{job_id}/reference/upload",
        files={"file": ("reference.png", b"reference", "image/png")},
    )
    client.post(
        f"/api/jobs/{job_id}/masks/upload/wall_concrete",
        files={"file": ("mask.png", b"wall-mask", "image/png")},
    )
    client.post(
        f"/api/jobs/{job_id}/masks/upload/floor_tiles",
        files={"file": ("mask.png", b"floor-mask", "image/png")},
    )

    assignment = {
        "unreal": {
            "master_material": "/Game/AI_Texturing/Materials/M_AI_PBR_Master.M_AI_PBR_Master",
            "texture_root": "/Game/AI_Texturing/Generated/Textures",
            "instance_root": "/Game/AI_Texturing/Generated/Instances",
        },
        "materials": [
            {
                "name": "wall_concrete",
                "display_name": "Wall Concrete",
                "assign_patterns": ["SM_Wall_*", "Wall_*", "*wall*"],
                "tiling": 3.0,
                "normal_strength": 1.0,
                "roughness_mult": 1.0,
                "metallic": 0.0,
            },
            {
                "name": "floor_tiles",
                "display_name": "Floor Tiles",
                "assign_patterns": ["SM_Floor_*", "Floor_*", "*floor*"],
                "tiling": 4.0,
                "normal_strength": 1.2,
                "roughness_mult": 1.0,
                "metallic": 0.25,
            },
        ],
    }
    assignment_response = client.post(f"/api/jobs/{job_id}/assignment", json=assignment)
    assert assignment_response.status_code == 200

    pbr_response = client.post(
        f"/api/jobs/{job_id}/pbr/generate",
        json={"provider": "mock_pbr", "texture_size": 4},
    )
    assert pbr_response.status_code == 200
    assert pbr_response.json()["materials"] == ["wall_concrete", "floor_tiles"]

    download_response = client.get(f"/api/jobs/{job_id}/download")
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/zip"

    with ZipFile(BytesIO(download_response.content)) as package:
        names = set(package.namelist())
        assert "manifest.json" in names
        assert "reference.png" in names
        assert "masks/wall_concrete.png" in names
        assert "masks/floor_tiles.png" in names

        manifest = json.loads(package.read("manifest.json").decode("utf-8"))
        assert manifest["job_id"] == job_id
        for material in manifest["materials"]:
            assert "\\" not in material["mask"]
            for texture_path in material["textures"].values():
                assert texture_path in names
                assert "\\" not in texture_path
                assert ":" not in texture_path

        floor = next(material for material in manifest["materials"] if material["name"] == "floor_tiles")
        assert read_png_first_pixel(package.read(floor["textures"]["normal"])) == (128, 128, 255)
        assert read_png_first_pixel(package.read(floor["textures"]["ao"])) == (255, 255, 255)
        assert read_png_first_pixel(package.read(floor["textures"]["roughness"])) == (179, 179, 179)
        assert read_png_first_pixel(package.read(floor["textures"]["metallic"])) == (64, 64, 64)
        assert read_png_first_pixel(package.read(floor["textures"]["orm"])) == (255, 179, 64)


def test_material_palette_api_falls_back_to_mock_when_unconfigured(client: TestClient) -> None:
    job_id = create_job(client)
    client.post(
        f"/api/jobs/{job_id}/reference/upload",
        files={"file": ("reference.png", b"reference", "image/png")},
    )
    client.post(
        f"/api/jobs/{job_id}/masks/upload/wall_concrete",
        files={"file": ("mask.png", b"wall-mask", "image/png")},
    )
    assignment = {
        "unreal": {
            "master_material": "/Game/AI_Texturing/Materials/M_AI_PBR_Master.M_AI_PBR_Master",
            "texture_root": "/Game/AI_Texturing/Generated/Textures",
            "instance_root": "/Game/AI_Texturing/Generated/Instances",
        },
        "materials": [{"name": "wall_concrete", "display_name": "Wall Concrete", "metallic": 0.0}],
    }
    client.post(f"/api/jobs/{job_id}/assignment", json=assignment)

    response = client.post(
        f"/api/jobs/{job_id}/pbr/generate",
        json={"provider": "material_palette", "texture_size": 2, "fallback_to_mock": True},
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "mock_pbr"
