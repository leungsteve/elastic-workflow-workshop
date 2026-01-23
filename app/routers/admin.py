"""Admin API routes for workshop management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.dependencies import get_es_client, get_app_settings


router = APIRouter(prefix="/api/admin", tags=["admin"])


class ResetResponse(BaseModel):
    """Response from reset operation."""
    success: bool
    message: str
    details: dict


class ResetStats(BaseModel):
    """Statistics from reset operation."""
    attack_reviews_deleted: int = 0
    attacker_users_deleted: int = 0
    businesses_reset: int = 0
    incidents_deleted: int = 0
    notifications_deleted: int = 0


@router.post("/reset", response_model=ResetResponse)
async def reset_environment(
    reviews: bool = True,
    users: bool = True,
    protection: bool = True,
    incidents: bool = True,
    notifications: bool = True,
):
    """
    Reset the workshop environment by removing attack data.

    This endpoint removes:
    - Simulated/attack reviews
    - Attacker user accounts
    - Business protection flags
    - Incidents
    - Notifications

    Use this to reset the environment for a fresh attack simulation.
    """
    settings = get_app_settings()
    stats = ResetStats()

    try:
        async for es in get_es_client():
            # Delete attack reviews
            if reviews:
                query = {
                    "bool": {
                        "should": [
                            {"term": {"is_simulated": True}},
                            {"prefix": {"user_id": "attacker_"}},
                        ],
                        "minimum_should_match": 1
                    }
                }
                try:
                    response = await es.delete_by_query(
                        index=settings.reviews_index,
                        query=query,
                        refresh=True,
                        conflicts="proceed"
                    )
                    stats.attack_reviews_deleted = response.get("deleted", 0)
                except Exception as e:
                    print(f"Error deleting attack reviews: {e}")

            # Delete attacker users
            if users:
                query = {
                    "bool": {
                        "should": [
                            {"term": {"is_attacker": True}},
                            {"prefix": {"user_id": "attacker_"}},
                        ],
                        "minimum_should_match": 1
                    }
                }
                try:
                    response = await es.delete_by_query(
                        index=settings.users_index,
                        query=query,
                        refresh=True,
                        conflicts="proceed"
                    )
                    stats.attacker_users_deleted = response.get("deleted", 0)
                except Exception as e:
                    print(f"Error deleting attacker users: {e}")

            # Reset business protection
            if protection:
                query = {"term": {"rating_protected": True}}
                try:
                    response = await es.update_by_query(
                        index=settings.businesses_index,
                        query=query,
                        script={
                            "source": """
                                ctx._source.rating_protected = false;
                                ctx._source.remove('protection_reason');
                                ctx._source.remove('protected_since');
                            """,
                            "lang": "painless"
                        },
                        refresh=True,
                        conflicts="proceed"
                    )
                    stats.businesses_reset = response.get("updated", 0)
                except Exception as e:
                    print(f"Error resetting business protection: {e}")

            # Delete incidents
            if incidents:
                try:
                    if await es.indices.exists(index=settings.incidents_index):
                        response = await es.delete_by_query(
                            index=settings.incidents_index,
                            query={"match_all": {}},
                            refresh=True,
                            conflicts="proceed"
                        )
                        stats.incidents_deleted = response.get("deleted", 0)
                except Exception as e:
                    print(f"Error deleting incidents: {e}")

            # Delete notifications
            if notifications:
                try:
                    if await es.indices.exists(index=settings.notifications_index):
                        response = await es.delete_by_query(
                            index=settings.notifications_index,
                            query={"match_all": {}},
                            refresh=True,
                            conflicts="proceed"
                        )
                        stats.notifications_deleted = response.get("deleted", 0)
                except Exception as e:
                    print(f"Error deleting notifications: {e}")

            break

        total_changes = (
            stats.attack_reviews_deleted +
            stats.attacker_users_deleted +
            stats.businesses_reset +
            stats.incidents_deleted +
            stats.notifications_deleted
        )

        if total_changes == 0:
            return ResetResponse(
                success=True,
                message="Environment is already clean. No attack data found.",
                details=stats.model_dump()
            )

        return ResetResponse(
            success=True,
            message=f"Environment reset successfully. {total_changes} items cleaned up.",
            details=stats.model_dump()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


@router.get("/stats")
async def get_environment_stats():
    """
    Get current environment statistics.

    Returns counts of attack data that would be cleaned up by reset.
    """
    settings = get_app_settings()
    stats = {
        "attack_reviews": 0,
        "attacker_users": 0,
        "protected_businesses": 0,
        "active_incidents": 0,
        "notifications": 0,
        "total_reviews": 0,
        "total_users": 0,
        "total_businesses": 0,
    }

    try:
        async for es in get_es_client():
            # Count attack reviews
            query = {
                "bool": {
                    "should": [
                        {"term": {"is_simulated": True}},
                        {"prefix": {"user_id": "attacker_"}},
                    ],
                    "minimum_should_match": 1
                }
            }
            try:
                response = await es.count(index=settings.reviews_index, query=query)
                stats["attack_reviews"] = response.get("count", 0)

                response = await es.count(index=settings.reviews_index)
                stats["total_reviews"] = response.get("count", 0)
            except:
                pass

            # Count attacker users
            query = {
                "bool": {
                    "should": [
                        {"term": {"is_attacker": True}},
                        {"prefix": {"user_id": "attacker_"}},
                    ],
                    "minimum_should_match": 1
                }
            }
            try:
                response = await es.count(index=settings.users_index, query=query)
                stats["attacker_users"] = response.get("count", 0)

                response = await es.count(index=settings.users_index)
                stats["total_users"] = response.get("count", 0)
            except:
                pass

            # Count protected businesses
            try:
                response = await es.count(
                    index=settings.businesses_index,
                    query={"term": {"rating_protected": True}}
                )
                stats["protected_businesses"] = response.get("count", 0)

                response = await es.count(index=settings.businesses_index)
                stats["total_businesses"] = response.get("count", 0)
            except:
                pass

            # Count incidents
            try:
                if await es.indices.exists(index=settings.incidents_index):
                    response = await es.count(index=settings.incidents_index)
                    stats["active_incidents"] = response.get("count", 0)
            except:
                pass

            # Count notifications
            try:
                if await es.indices.exists(index=settings.notifications_index):
                    response = await es.count(index=settings.notifications_index)
                    stats["notifications"] = response.get("count", 0)
            except:
                pass

            break

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
