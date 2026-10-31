from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/healthz", tags=["Health"])
async def health_check():
    """Liveness and readiness health probe."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }
