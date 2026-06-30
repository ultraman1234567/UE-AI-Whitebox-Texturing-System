from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app.main import create_app


@pytest.fixture()
def jobs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "server_data" / "jobs"
    monkeypatch.setenv("JOB_STORAGE_DIR", str(root))
    return root


@pytest.fixture()
def client(jobs_root: Path) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client
