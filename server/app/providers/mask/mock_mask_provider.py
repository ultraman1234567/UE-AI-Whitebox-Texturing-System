"""Mock mask provider for local, offline development."""

from pathlib import Path

from ...processing.mask_utils import mask_bbox_area, rectangle_mask, write_mask_png
from .base import CandidateMask, MaskGenerationRequest, MaskGenerationResult


class MockMaskProvider:
    name = "mock"

    def generate(self, request: MaskGenerationRequest, job_dir: Path) -> MaskGenerationResult:
        width = int(request.params.get("width", 128))
        height = int(request.params.get("height", 128))
        candidate_dir = job_dir / "candidate_masks"
        candidate_dir.mkdir(parents=True, exist_ok=True)

        specs = [
            ("mask_001", 0, 0, width // 2, height),
            ("mask_002", width // 2, 0, width - width // 2, height),
            ("mask_003", width // 4, height // 4, max(1, width // 2), max(1, height // 2)),
        ]

        candidates: list[CandidateMask] = []
        for index, (mask_id, x, y, rect_width, rect_height) in enumerate(specs):
            pixels = rectangle_mask(width, height, x, y, rect_width, rect_height)
            bbox, area = mask_bbox_area(width, height, pixels)
            relative_path = f"candidate_masks/{mask_id}.png"
            write_mask_png(job_dir / relative_path, width, height, pixels)
            candidates.append(
                CandidateMask(
                    mask_id=mask_id,
                    path=relative_path,
                    bbox=bbox,
                    area=area,
                    score=round(0.95 - index * 0.04, 3),
                )
            )

        masks = [request.material_name] if request.material_name else []
        return MaskGenerationResult(provider=self.name, status="done", masks=masks, candidates=candidates)
