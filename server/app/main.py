from fastapi import FastAPI

from .api.routes_downloads import router as downloads_router
from .api.routes_health import router as health_router
from .api.routes_jobs import router as jobs_router
from .api.routes_masks import router as masks_router
from .api.routes_pbr import router as pbr_router
from .api.routes_reference import router as reference_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="UE AI Texturing Mock Server",
        version="0.1.0",
        description="Local mock-first server skeleton for UE whitebox texturing.",
    )
    app.include_router(health_router)
    app.include_router(jobs_router)
    app.include_router(reference_router)
    app.include_router(masks_router)
    app.include_router(pbr_router)
    app.include_router(downloads_router)
    return app


app = create_app()
