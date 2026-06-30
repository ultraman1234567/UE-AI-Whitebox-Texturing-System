from fastapi.testclient import TestClient


def create_job(client: TestClient) -> str:
    response = client.post(
        "/api/jobs",
        json={
            "job_name": "corridor_test_001",
            "description": "local milestone 1 test",
            "ue_project_name": "MockUEProject",
        },
    )
    assert response.status_code == 201
    return response.json()["job_id"]
