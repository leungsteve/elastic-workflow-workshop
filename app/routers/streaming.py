"""Streaming API router for Review Campaign Detection Workshop."""

import asyncio
from datetime import datetime
from typing import Optional

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies import get_es_client, get_app_settings
from app.config import Settings
from app.services.review_generator import ReviewGenerator

router = APIRouter(prefix="/api/streaming", tags=["streaming"])


class StreamingStatus(BaseModel):
    """Status of the review streaming service."""

    is_running: bool = False
    target_business_id: Optional[str] = None
    target_business_name: Optional[str] = None
    reviews_generated: int = 0
    started_at: Optional[datetime] = None
    interval_seconds: float = 1.0
    batch_size: int = 1


class StreamingStartRequest(BaseModel):
    """Request to start streaming reviews."""

    business_id: str = Field(..., description="Target business ID")
    interval_seconds: float = Field(default=1.0, ge=0.1, le=60.0, description="Seconds between review batches")
    batch_size: int = Field(default=1, ge=1, le=10, description="Reviews per batch")
    min_stars: float = Field(default=1.0, ge=1.0, le=5.0, description="Minimum star rating")
    max_stars: float = Field(default=2.0, ge=1.0, le=5.0, description="Maximum star rating")
    attack_type: str = Field(default="random", description="Attack pattern type")


# Global streaming state
_streaming_state = {
    "is_running": False,
    "task": None,
    "target_business_id": None,
    "target_business_name": None,
    "reviews_generated": 0,
    "started_at": None,
    "interval_seconds": 1.0,
    "batch_size": 1,
    "min_stars": 1.0,
    "max_stars": 2.0,
    "attack_type": "random"
}


async def _streaming_loop(
    es: AsyncElasticsearch,
    settings: Settings,
    business_id: str,
    interval: float,
    batch_size: int,
    min_stars: float,
    max_stars: float,
    attack_type: str
):
    """Background task for streaming reviews."""
    global _streaming_state

    generator = ReviewGenerator()

    while _streaming_state["is_running"]:
        try:
            # Generate batch of reviews
            reviews = await generator.generate_attack_reviews(
                business_id=business_id,
                count=batch_size,
                min_stars=min_stars,
                max_stars=max_stars,
                attack_type=attack_type
            )

            # Bulk index the reviews
            operations = []
            for review in reviews:
                operations.append({"index": {"_index": settings.reviews_index, "_id": review.review_id}})
                operations.append(review.model_dump(mode="json"))

            if operations:
                await es.bulk(operations=operations)
                _streaming_state["reviews_generated"] += len(reviews)

            # Wait for next interval
            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Streaming error: {e}")
            await asyncio.sleep(interval)


@router.get("/status", response_model=StreamingStatus)
async def get_streaming_status() -> StreamingStatus:
    """
    Get the current status of the review streaming service.
    """
    return StreamingStatus(
        is_running=_streaming_state["is_running"],
        target_business_id=_streaming_state["target_business_id"],
        target_business_name=_streaming_state["target_business_name"],
        reviews_generated=_streaming_state["reviews_generated"],
        started_at=_streaming_state["started_at"],
        interval_seconds=_streaming_state["interval_seconds"],
        batch_size=_streaming_state["batch_size"]
    )


@router.post("/start", response_model=StreamingStatus)
async def start_streaming(
    request: StreamingStartRequest,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> StreamingStatus:
    """
    Start streaming simulated attack reviews to a business.

    This creates a background task that continuously generates
    and indexes negative reviews to simulate a negative review campaign.

    - **business_id**: Target business for the attack
    - **interval_seconds**: Time between review batches
    - **batch_size**: Number of reviews per batch
    - **min_stars**: Minimum star rating for generated reviews
    - **max_stars**: Maximum star rating for generated reviews
    - **attack_type**: Type of attack pattern
    """
    global _streaming_state

    if _streaming_state["is_running"]:
        raise HTTPException(
            status_code=400,
            detail="Streaming is already running. Stop it first."
        )

    # Verify business exists
    try:
        response = await es.search(
            index=settings.businesses_index,
            query={"term": {"business_id": request.business_id}},
            size=1
        )

        if not response["hits"]["hits"]:
            raise HTTPException(status_code=404, detail=f"Business {request.business_id} not found")

        business_name = response["hits"]["hits"][0]["_source"].get("name", "Unknown")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying business: {str(e)}")

    # Update state
    _streaming_state["is_running"] = True
    _streaming_state["target_business_id"] = request.business_id
    _streaming_state["target_business_name"] = business_name
    _streaming_state["reviews_generated"] = 0
    _streaming_state["started_at"] = datetime.utcnow()
    _streaming_state["interval_seconds"] = request.interval_seconds
    _streaming_state["batch_size"] = request.batch_size
    _streaming_state["min_stars"] = request.min_stars
    _streaming_state["max_stars"] = request.max_stars
    _streaming_state["attack_type"] = request.attack_type

    # Start background task
    _streaming_state["task"] = asyncio.create_task(
        _streaming_loop(
            es=es,
            settings=settings,
            business_id=request.business_id,
            interval=request.interval_seconds,
            batch_size=request.batch_size,
            min_stars=request.min_stars,
            max_stars=request.max_stars,
            attack_type=request.attack_type
        )
    )

    return await get_streaming_status()


@router.post("/stop", response_model=StreamingStatus)
async def stop_streaming() -> StreamingStatus:
    """
    Stop the review streaming service.
    """
    global _streaming_state

    if not _streaming_state["is_running"]:
        raise HTTPException(status_code=400, detail="Streaming is not running")

    # Stop the background task
    _streaming_state["is_running"] = False

    if _streaming_state["task"]:
        _streaming_state["task"].cancel()
        try:
            await _streaming_state["task"]
        except asyncio.CancelledError:
            pass
        _streaming_state["task"] = None

    return await get_streaming_status()


@router.post("/reset")
async def reset_streaming_stats() -> dict:
    """
    Reset streaming statistics without stopping.
    """
    global _streaming_state

    _streaming_state["reviews_generated"] = 0

    return {"success": True, "message": "Streaming stats reset"}
