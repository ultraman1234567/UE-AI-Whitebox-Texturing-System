from fastapi import APIRouter, HTTPException

from .. import storage
from ..schemas import AssignmentRequest, AssignmentResponse, JobCreateRequest, JobCreateResponse, JobStatusResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse, status_code=201)
def create_job(request: JobCreateRequest) -> JobCreateResponse:
    try:
        metadata = storage.create_job(_model_dump(request))
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return JobCreateResponse(job_id=metadata["job_id"], status=metadata["status"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    try:
        metadata = storage.load_job(job_id)
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return JobStatusResponse(**metadata)


@router.post("/{job_id}/assignment", response_model=AssignmentResponse)
def save_assignment(job_id: str, request: AssignmentRequest) -> AssignmentResponse:
    try:
        result = storage.save_assignment(job_id, _model_dump(request))
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return AssignmentResponse(**result)


def _model_dump(model: object) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return model.dict()  # type: ignore[attr-defined]
