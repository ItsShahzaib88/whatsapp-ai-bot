"""
Health Check Router
Returns system health status including DB connectivity.
Redis is optional and disabled by default.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database.mongodb import get_database

router = APIRouter()


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    System health check endpoint.
    Returns 200 if MongoDB is healthy, 503 otherwise.
    """
    health: dict = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {},
    }
    is_healthy = True

    # Check MongoDB
    try:
        db = get_database()
        await db.command("ping")
        health["services"]["mongodb"] = "up"
    except Exception as e:
        health["services"]["mongodb"] = f"down: {str(e)}"
        is_healthy = False

    if not is_healthy:
        health["status"] = "degraded"
        return JSONResponse(status_code=503, content=health)

    return JSONResponse(status_code=200, content=health)
