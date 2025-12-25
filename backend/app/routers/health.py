"""
Health check endpoint for desktop app readiness detection.
"""
from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    """Simple health check endpoint for Tauri to detect backend readiness."""
    return {"status": "ok", "service": "mycelium-backend"}
