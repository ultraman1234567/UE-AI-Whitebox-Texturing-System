"""Provider that reuses a reference image uploaded by the user."""

from pathlib import Path

from .base import ReferenceGenerationRequest, ReferenceGenerationResult, ReferenceProviderError


class UserUploadReferenceProvider:
    name = "user_upload"

    def generate(self, request: ReferenceGenerationRequest, job_dir: Path) -> ReferenceGenerationResult:
        for filename in ("reference.png", "reference.jpg", "reference.jpeg"):
            if (job_dir / filename).is_file():
                return ReferenceGenerationResult(
                    provider=self.name,
                    status="done",
                    output_path=filename,
                    message="Using uploaded reference image",
                )
        raise ReferenceProviderError(409, "reference image has not been uploaded")
