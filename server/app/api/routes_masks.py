from dataclasses import asdict

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .. import storage
from ..providers.mask.base import MaskGenerationRequest as ProviderMaskGenerationRequest
from ..providers.mask.base import MaskProviderError
from ..providers.mask.registry import get_mask_provider
from ..schemas import FileUploadResponse, MaskAutoRequest, MaskAutoResponse, MaskConfirmRequest, MaskConfirmResponse

router = APIRouter(prefix="/api/jobs/{job_id}/masks", tags=["masks"])


@router.post("/upload/{material_name:path}", response_model=FileUploadResponse)
async def upload_mask(job_id: str, material_name: str, file: UploadFile = File(...)) -> FileUploadResponse:
    try:
        result = await storage.save_mask_upload(job_id, material_name, file)
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return FileUploadResponse(**result)


@router.post("/auto-sam", response_model=MaskAutoResponse)
def auto_sam(job_id: str, request: MaskAutoRequest) -> MaskAutoResponse:
    try:
        job_dir = storage.require_job_dir(job_id)
        provider_request = ProviderMaskGenerationRequest(**_model_dump(request))
        result = _generate_masks_with_fallback(request, provider_request, job_dir)
        candidates = storage.save_mask_candidates(
            job_id,
            result.provider,
            [asdict(candidate) for candidate in result.candidates],
        )
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except MaskProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return MaskAutoResponse(job_id=job_id, status=result.status, provider=result.provider, candidates=candidates)


def _generate_masks_with_fallback(
    request: MaskAutoRequest,
    provider_request: ProviderMaskGenerationRequest,
    job_dir,
):
    provider_name = (request.provider or provider_request.provider or "mock").strip().lower()
    try:
        provider = get_mask_provider(provider_name)
        return provider.generate(provider_request, job_dir)
    except MaskProviderError:
        if not request.fallback_to_mock or provider_name in {"mock", "mock_sam"}:
            raise
        fallback_request = ProviderMaskGenerationRequest(**{**_model_dump(request), "provider": "mock"})
        return get_mask_provider("mock").generate(fallback_request, job_dir)
    except Exception:
        if not request.fallback_to_mock or provider_name in {"mock", "mock_sam"}:
            raise
        fallback_request = ProviderMaskGenerationRequest(**{**_model_dump(request), "provider": "mock"})
        return get_mask_provider("mock").generate(fallback_request, job_dir)


@router.get("/candidates/{mask_id}/preview")
def preview_candidate(job_id: str, mask_id: str) -> FileResponse:
    try:
        path = storage.candidate_preview_path(job_id, mask_id)
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return FileResponse(path, media_type="image/png")


@router.post("/confirm", response_model=MaskConfirmResponse)
def confirm_masks(job_id: str, request: MaskConfirmRequest) -> MaskConfirmResponse:
    try:
        result = storage.confirm_mask_candidates(
            job_id,
            request.material_name,
            request.candidate_mask_ids,
            request.operation,
        )
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return MaskConfirmResponse(**result)


def _model_dump(model: object) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return model.dict()  # type: ignore[attr-defined]
