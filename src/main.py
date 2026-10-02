"""F3 RVA API Application Entrypoint & Serverless Lambda Handler."""

from __future__ import annotations

import logging
import sys
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import Settings, get_settings
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

def get_allowed_origins(app_settings: Settings) -> list[str]:
    """Compile list of trusted CORS origins for browser preflight validation."""
    origins = [
        # Production
        "https://f3rva.org",
        "https://www.f3rva.org",
        "https://api.f3rva.org",
        "https://f3rva.com",
        "https://www.f3rva.com",
        "https://f3rva.net",
        "https://www.f3rva.net",
        # Development / Staging
        "https://dev.f3rva.org",
        "https://www.dev.f3rva.org",
        "https://api.dev.f3rva.org",
        # Local Development
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:4173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
        "http://127.0.0.1:8000",
    ]
    if app_settings.cors_allowed_origins:
        for extra in app_settings.cors_allowed_origins.split(","):
            extra_cleaned = extra.strip()
            if extra_cleaned and extra_cleaned not in origins:
                origins.append(extra_cleaned)
    return origins


# Configure Cross-Origin Resource Sharing (CORS)
allowed_origins = get_allowed_origins(settings)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Inject OWASP defensive security response headers on all outgoing HTTP responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


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
