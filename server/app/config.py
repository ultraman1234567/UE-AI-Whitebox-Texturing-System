from dataclasses import dataclass
import os
from pathlib import Path
from threading import Lock

_DOTENV_LOCK = Lock()
_DOTENV_LOADED = False


@dataclass(frozen=True)
class Settings:
    app_name: str
    version: str
    job_storage_dir: Path
    max_upload_mb: int
    enable_external_providers: bool
    default_reference_provider: str
    default_mask_provider: str
    provider_config_path: Path | None

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def get_settings() -> Settings:
    _load_dotenv_once()
    return Settings(
        app_name=os.getenv("APP_NAME", "UE AI Texturing Mock Server"),
        version=os.getenv("APP_VERSION", "0.1.0"),
        job_storage_dir=Path(os.getenv("SERVER_DATA_DIR") or os.getenv("JOB_STORAGE_DIR", "server_data/jobs")),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "50")),
        enable_external_providers=os.getenv("ENABLE_EXTERNAL_PROVIDERS", "false").lower() == "true",
        default_reference_provider=os.getenv("DEFAULT_REFERENCE_PROVIDER", "mock"),
        default_mask_provider=os.getenv("DEFAULT_MASK_PROVIDER", "mock"),
        provider_config_path=_optional_path(
            os.getenv("PROVIDER_CONFIG_PATH")
            or os.getenv("SERVER_CONFIG_PATH")
            or os.getenv("REFERENCE_PROVIDER_CONFIG_PATH")
        ),
    )


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value)


def _load_dotenv_once() -> None:
    global _DOTENV_LOADED
    with _DOTENV_LOCK:
        if _DOTENV_LOADED:
            return
        for path in _dotenv_candidates():
            if path.is_file():
                _load_dotenv_file(path)
        _DOTENV_LOADED = True


def _dotenv_candidates() -> list[Path]:
    cwd = Path.cwd()
    return [cwd / ".env", cwd / "server" / ".env"]


def _load_dotenv_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
