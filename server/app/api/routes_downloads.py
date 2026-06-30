from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .. import storage

router = APIRouter(prefix="/api/jobs/{job_id}", tags=["downloads"])


@router.get("/download")
def download_job(job_id: str) -> StreamingResponse:
    try:
        filename, content = storage.build_result_zip(job_id)
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(content), media_type="application/zip", headers=headers)
