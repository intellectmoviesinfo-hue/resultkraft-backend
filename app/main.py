import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import get_settings
from app.routers import extraction, results, reports, analytics, ai_commands, health
from app.middleware.rate_limiter import RateLimitMiddleware

logger = logging.getLogger("resultkraft")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.environment} mode")
    yield
    print("Shutting down ResultKraft API")


app = FastAPI(
    title="ResultKraft API",
    description="Exam result analysis in 60 seconds. Not 6 hours.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if get_settings().environment != "production" else None,
    redoc_url=None,
)


# Global error handler — never leak stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )


# Body size limit middleware (reject before reading full body)
MAX_BODY_SIZE = 52_428_800  # 50MB

@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse(status_code=413, content={"detail": "Request body too large. Maximum 50MB."})
    return await call_next(request)


# Rate limiting
app.add_middleware(RateLimitMiddleware)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Routers
app.include_router(health.router, tags=["Health"])
app.include_router(extraction.router, prefix="/api/v1", tags=["Extraction"])
app.include_router(results.router, prefix="/api/v1", tags=["Results"])
app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
app.include_router(ai_commands.router, prefix="/api/v1", tags=["AI Commands"])
