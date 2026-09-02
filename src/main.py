"""F3 RVA API Application Entrypoint & Serverless Lambda Handler."""

from __future__ import annotations

import logging
import sys
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import get_settings
from src.config.version import get_version
from src.routers import admin, aliases, auth, members, reports, schedule, workouts

settings = get_settings()
APP_VERSION = get_version()

# Configure global structured logging based on DEBUG environment flag
log_level = logging.DEBUG if settings.debug else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logging.getLogger("f3rva").setLevel(log_level)
logging.getLogger("f3rva.services").setLevel(log_level)
logger = logging.getLogger("f3rva-api")

app = FastAPI(
    title=settings.app_name or "F3 RVA API",
    version=APP_VERSION,
    description="Modern Python REST API for F3 RVA backblasts, member analytics, and schedule.",
    docs_url="/docs",
    redoc_url=None,  # Disabled ReDoc in favor of interactive Swagger UI
    openapi_url="/openapi.json",
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "https://f3rva.org",
        "https://www.f3rva.org",
        "https://dev.f3rva.org",
        "https://www.dev.f3rva.org",
        "https://api.f3rva.org",
        "https://api.dev.f3rva.org",
        "*",  # Open for public read APIs
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount Domain Routers
app.include_router(schedule.router, prefix="/schedule", tags=["Schedule"])
app.include_router(auth.router, prefix="/v2/auth", tags=["Auth"])
app.include_router(workouts.router, prefix="/v2/workouts", tags=["Workouts"])
app.include_router(members.router, prefix="/v2/members", tags=["Members"])
app.include_router(reports.router, prefix="/v2/reports", tags=["Reports"])
app.include_router(aliases.router, prefix="/v2/aliases", tags=["Aliases"])
app.include_router(admin.router, prefix="/v2/admin", tags=["Admin"])


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Format HTTP exceptions into structured JSON matching legacy contract."""
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"errorCode": exc.status_code, "errorMessage": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global fallback error handler ensuring structured JSON error responses with zero credential leakage."""
    logger.error("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"errorCode": 5000, "errorMessage": "An internal server error occurred."},
    )


@app.get(
    "/favicon.ico",
    include_in_schema=False,
    summary="Favicon endpoint to silence browser 404s",
)
def favicon() -> Response:
    """Return 204 No Content to silence browser favicon 404 noise in server logs."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/health",
    tags=["System"],
    summary="Application health check",
    description="Returns the current operational status, API version, and runtime environment.",
)
def health_check() -> dict[str, Any]:
    """Health check for load balancers, deployment pipelines, and liveness monitors."""
    return {
        "status": "healthy",
        "service": "f3rva-api",
        "version": APP_VERSION,
        "environment": settings.environment,
    }


@app.get(
    "/health/db",
    tags=["System"],
    summary="Database connectivity check",
    description="Executes a lightweight query against the configured database to verify connectivity.",
)
def health_check_db(
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Verify live database connectivity and report active engine dialect from SQLAlchemy metadata."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            dialect = db.bind.dialect.name if db.bind else "unknown"
            return {
                "status": "healthy",
                "database": "connected",
                "dialect": dialect,
                "version": APP_VERSION,
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"errorCode": 5031, "errorMessage": "Database returned unexpected response."},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Database connection failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "errorCode": 5030,
                "errorMessage": "Database connection failed. Unable to establish connection to the remote database host.",
            },
        ) from None


# AWS Lambda ASGI Adapter entrypoint
handler = Mangum(app, lifespan="off")
