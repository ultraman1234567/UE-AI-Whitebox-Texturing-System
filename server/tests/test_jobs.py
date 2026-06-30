import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_create_job_creates_local_storage(client: TestClient, jobs_root: Path) -> None:
    response = client.post(
        "/api/jobs",
        json={
            "job_name": "corridor_test_001",
            "description": "industrial corridor whitebox texturing",
            "ue_project_name": "MyUEProject",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "created"
    assert body["job_id"].startswith("job_")

    job_dir = jobs_root / body["job_id"]
    assert job_dir.is_dir()
    assert (job_dir / "masks").is_dir()
    assert (job_dir / "logs").is_dir()

    metadata = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert metadata["job_name"] == "corridor_test_001"
    assert metadata["status"] == "created"


def test_get_job_status(client: TestClient) -> None:
    job_id = client.post(
        "/api/jobs",
        json={"job_name": "status_test", "description": "", "ue_project_name": ""},
    ).json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_id"] == job_id
    assert response.json()["stage"] == "created"
