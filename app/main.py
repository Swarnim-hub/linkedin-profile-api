"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers.profile import router as profile_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    has_creds = bool(settings.LINKEDIN_LI_AT and settings.LINKEDIN_JSESSIONID)
    logger.info(f"LinkedIn session credentials configured: {has_creds}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title="LinkedIn Profile Scraper API",
    description=(
        "A reverse-engineered API that accepts a LinkedIn profile URL and returns "
        "comprehensive structured JSON directly from LinkedIn internal endpoints, "
        "without using browser automation (Puppeteer/Selenium)."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for public consumption
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(profile_router)


@app.get("/", tags=["Health"])
async def root():
    """Root info endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
        "endpoints": {
            "scrape_profile_post": "POST /api/profile",
            "scrape_profile_get": "GET /api/profile?url={url}",
            "health": "GET /health",
        },
        "credentials_configured": bool(settings.LINKEDIN_LI_AT),
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring and deployment platforms."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "credentials_configured": bool(settings.LINKEDIN_LI_AT),
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global fallback exception handler."""
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred.",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
