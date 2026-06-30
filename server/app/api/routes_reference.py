from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import storage
from ..providers.reference.base import ReferenceGenerationRequest as ProviderReferenceGenerationRequest
from ..providers.reference.base import ReferenceGenerationResult
from ..providers.reference.base import ReferenceProviderError
from ..providers.reference.registry import get_reference_provider
from ..schemas import FileUploadResponse, ReferenceGenerateRequest, ReferenceGenerateResponse

router = APIRouter(prefix="/api/jobs/{job_id}/reference", tags=["reference"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_reference(job_id: str, file: UploadFile = File(...)) -> FileUploadResponse:
    try:
        result = await storage.save_reference_upload(job_id, file)
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return FileUploadResponse(**result)


@router.post("/generate", response_model=ReferenceGenerateResponse)
def generate_reference(job_id: str, request: ReferenceGenerateRequest) -> ReferenceGenerateResponse:
    try:
        job_dir = storage.require_job_dir(job_id)
        provider_request = ProviderReferenceGenerationRequest(**_model_dump(request))
        result = _generate_with_fallback(request, provider_request, job_dir)
        if not result.output_path:
            raise ReferenceProviderError(502, "reference provider did not return output_path")
        storage.mark_reference_generated(job_id, result.output_path, result.provider)
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ReferenceProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return ReferenceGenerateResponse(
        job_id=job_id,
        status=result.status,
        provider=result.provider,
        path=result.output_path,
        message=result.message,
        metadata=result.metadata,
    )


def _generate_with_fallback(
    request: ReferenceGenerateRequest,
    provider_request: ProviderReferenceGenerationRequest,
    job_dir,
) -> ReferenceGenerationResult:
    provider_name = (request.provider or provider_request.provider or "mock").strip().lower()
    try:
        provider = get_reference_provider(provider_name)
        return provider.generate(provider_request, job_dir)
    except ReferenceProviderError as exc:
        return _fallback_reference_or_raise(request, provider_name, job_dir, exc.message, exc.status_code)
    except Exception as exc:
        return _fallback_reference_or_raise(request, provider_name, job_dir, f"{type(exc).__name__}: {exc}", 502)


def _fallback_reference_or_raise(
    request: ReferenceGenerateRequest,
    provider_name: str,
    job_dir,
    reason: str,
    status_code: int,
) -> ReferenceGenerationResult:
    if not request.fallback_to_mock or provider_name == "mock":
        raise ReferenceProviderError(status_code, reason)
    fallback_request = ProviderReferenceGenerationRequest(**{**_model_dump(request), "provider": "mock"})
    result = get_reference_provider("mock").generate(fallback_request, job_dir)
    return ReferenceGenerationResult(
        provider=result.provider,
        status=result.status,
        output_path=result.output_path,
        message=f"{result.message}; fallback from {provider_name}: {reason}",
        metadata={**result.metadata, "fallback_from": provider_name, "fallback_reason": reason},
    )


def _model_dump(model: object) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return model.dict()  # type: ignore[attr-defined]
