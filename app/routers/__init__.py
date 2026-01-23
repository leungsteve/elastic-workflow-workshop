"""API routers for Review Fraud Workshop."""

from app.routers.admin import router as admin_router
from app.routers.businesses import router as businesses_router
from app.routers.incidents import router as incidents_router
from app.routers.notifications import router as notifications_router
from app.routers.reviews import router as reviews_router
from app.routers.streaming import router as streaming_router

__all__ = [
    "admin_router",
    "businesses_router",
    "reviews_router",
    "incidents_router",
    "notifications_router",
    "streaming_router",
]
