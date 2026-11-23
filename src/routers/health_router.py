from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.load_resources import resources


router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def liveness():
    """Check that the API can respond without running model inference."""
    return {"status": "alive"}


@router.get("/ready", responses={503: {"description": "OCR service unavailable"}})
async def readiness(request: Request):
    """Check startup completion and availability of the loaded OCR service."""
    ready = (
        getattr(request.app.state, "ready", False)
        and resources.get("ocr_service") is not None
    )
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready"},
        headers={"Cache-Control": "no-store"},
    )
