"""FastAPI application entry point for Review Bomb Workshop."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.dependencies import init_es_client, close_es_client, get_es_client
from app.routers import (
    businesses_router,
    reviews_router,
    incidents_router,
    notifications_router,
    streaming_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown events."""
    # Startup
    print("Starting Review Bomb Workshop...")
    try:
        await init_es_client()
        print("Elasticsearch client initialized")
    except Exception as e:
        print(f"Warning: Could not connect to Elasticsearch: {e}")

    yield

    # Shutdown
    print("Shutting down Review Bomb Workshop...")
    await close_es_client()
    print("Elasticsearch client closed")


# Create FastAPI application
app = FastAPI(
    title="Review Bomb Workshop",
    description="A workshop application for detecting and analyzing review bomb attacks using Elasticsearch",
    version="1.0.0",
    lifespan=lifespan,
)

# Get paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Ensure directories exist
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include routers
app.include_router(businesses_router)
app.include_router(reviews_router)
app.include_router(incidents_router)
app.include_router(notifications_router)
app.include_router(streaming_router)


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns the status of the application and its dependencies.
    """
    settings = get_settings()
    es_status = "disconnected"

    try:
        async for es in get_es_client():
            info = await es.info()
            es_status = "connected"
            break
    except Exception as e:
        es_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "elasticsearch": es_status,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Serve the main UI dashboard.
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "dashboard",
        }
    )


@app.get("/businesses", response_class=HTMLResponse)
async def businesses_page(request: Request):
    """
    Serve the businesses page.
    """
    return templates.TemplateResponse(
        "businesses.html",
        {
            "request": request,
            "active_page": "businesses",
        }
    )


@app.get("/incidents", response_class=HTMLResponse)
async def incidents_page(request: Request):
    """
    Serve the incidents page.
    """
    return templates.TemplateResponse(
        "incidents.html",
        {
            "request": request,
            "active_page": "incidents",
        }
    )


@app.get("/attack", response_class=HTMLResponse)
async def attack_page(request: Request):
    """
    Serve the attack simulation page.
    """
    return templates.TemplateResponse(
        "attack.html",
        {
            "request": request,
            "active_page": "attack",
        }
    )


@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    """
    Serve the notifications page.
    """
    return templates.TemplateResponse(
        "notifications.html",
        {
            "request": request,
            "active_page": "notifications",
        }
    )


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
