"""Provider that reports user-supplied material masks already saved in a job."""

from pathlib import Path

from .base import MaskGenerationRequest, MaskGenerationResult


class UserMaskProvider:
    name = "user_upload"

    def generate(self, request: MaskGenerationRequest, job_dir: Path) -> MaskGenerationResult:
        mask_dir = job_dir / "masks"
        masks = sorted(path.stem for path in mask_dir.glob("*.png")) if mask_dir.is_dir() else []
        return MaskGenerationResult(provider=self.name, status="done", masks=masks)
