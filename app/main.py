from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.routers import extraction, results, reports, analytics, ai_commands, health
from app.middleware.rate_limiter import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.environment} mode")
    yield
    # Shutdown
    print("Shutting down ResultKraft API")


app = FastAPI(
    title="ResultKraft API",
    description="Exam result analysis in 60 seconds. Not 6 hours.",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting (must be added before CORS)
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
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, tags=["Health"])
app.include_router(extraction.router, prefix="/api/v1", tags=["Extraction"])
app.include_router(results.router, prefix="/api/v1", tags=["Results"])
app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
app.include_router(ai_commands.router, prefix="/api/v1", tags=["AI Commands"])
