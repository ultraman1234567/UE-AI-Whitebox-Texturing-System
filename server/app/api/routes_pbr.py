from fastapi import APIRouter, HTTPException

from .. import job_manager, storage
from ..providers.pbr.base import PBRProviderError
from ..schemas import PBRGenerateRequest, PBRGenerateResponse

router = APIRouter(prefix="/api/jobs/{job_id}/pbr", tags=["pbr"])


@router.post("/generate", response_model=PBRGenerateResponse)
def generate_pbr(job_id: str, request: PBRGenerateRequest) -> PBRGenerateResponse:
    try:
        result = job_manager.generate_pbr(
            job_id,
            provider_name=request.provider,
            texture_size=request.texture_size,
            fallback_to_mock=request.fallback_to_mock,
        )
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except PBRProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return PBRGenerateResponse(**result)
