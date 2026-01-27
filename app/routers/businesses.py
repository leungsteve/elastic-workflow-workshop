"""Business API router for Review Fraud Workshop."""

from typing import Optional

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_es_client, get_app_settings
from app.config import Settings
from app.models.business import Business, BusinessStats, BusinessSearchResult
from app.services.incident_service import create_incident_if_attack_detected

router = APIRouter(prefix="/api/businesses", tags=["businesses"])


@router.get("", response_model=BusinessSearchResult)
async def list_businesses(
    q: Optional[str] = Query(None, description="Search query for business name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    city: Optional[str] = Query(None, description="Filter by city"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Results per page"),
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> BusinessSearchResult:
    """
    List businesses with optional filtering and pagination.

    - **q**: Search query to match against business names
    - **category**: Filter businesses by category
    - **city**: Filter businesses by city
    - **page**: Page number for pagination
    - **page_size**: Number of results per page
    """
    # Build query
    must_clauses = []

    if q:
        must_clauses.append({
            "match": {
                "name": {
                    "query": q,
                    "fuzziness": "AUTO"
                }
            }
        })

    if category:
        must_clauses.append({
            "match": {
                "categories": category
            }
        })

    if city:
        must_clauses.append({
            "term": {
                "city": city
            }
        })

    query = {"match_all": {}} if not must_clauses else {"bool": {"must": must_clauses}}

    # Calculate pagination
    from_offset = (page - 1) * page_size

    try:
        response = await es.search(
            index=settings.businesses_index,
            query=query,
            from_=from_offset,
            size=page_size,
            sort=[{"review_count": "desc"}],
            track_total_hits=True
        )

        businesses = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            source["business_id"] = source.get("business_id", hit["_id"])
            businesses.append(Business(**source))

        total = response["hits"]["total"]["value"]

        return BusinessSearchResult(
            businesses=businesses,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching businesses: {str(e)}")


@router.get("/{business_id}", response_model=Business)
async def get_business(
    business_id: str,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> Business:
    """
    Get a specific business by ID.

    - **business_id**: The unique identifier of the business
    """
    try:
        # Try to get by document ID first
        try:
            response = await es.get(index=settings.businesses_index, id=business_id)
            source = response["_source"]
            source["business_id"] = source.get("business_id", business_id)
            return Business(**source)
        except:
            pass

        # Fall back to searching by business_id field
        response = await es.search(
            index=settings.businesses_index,
            query={"term": {"business_id": business_id}},
            size=1
        )

        if not response["hits"]["hits"]:
            raise HTTPException(status_code=404, detail=f"Business {business_id} not found")

        source = response["hits"]["hits"][0]["_source"]
        source["business_id"] = source.get("business_id", business_id)
        return Business(**source)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching business: {str(e)}")


@router.get("/{business_id}/stats", response_model=BusinessStats)
async def get_business_stats(
    business_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours to analyze"),
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> BusinessStats:
    """
    Get statistics for a business, including review fraud detection metrics.

    - **business_id**: The unique identifier of the business
    - **hours**: Number of hours to analyze for recent activity (default: 24)
    """
    try:
        # Get the business first
        business = await get_business(business_id, es, settings)

        # Get overall review stats
        overall_stats = await es.search(
            index=settings.reviews_index,
            query={"term": {"business_id": business_id}},
            aggs={
                "avg_rating": {"avg": {"field": "stars"}},
                "total_reviews": {"value_count": {"field": "review_id"}}
            },
            size=0
        )

        # Get recent review stats
        recent_stats = await es.search(
            index=settings.reviews_index,
            query={
                "bool": {
                    "must": [
                        {"term": {"business_id": business_id}},
                        {"range": {"date": {"gte": f"now-{hours}h"}}}
                    ]
                }
            },
            aggs={
                "avg_rating": {"avg": {"field": "stars"}},
                "review_count": {"value_count": {"field": "review_id"}},
                "suspicious_count": {
                    "filter": {"term": {"is_simulated": True}}
                }
            },
            size=0
        )

        overall_aggs = overall_stats.get("aggregations", {})
        recent_aggs = recent_stats.get("aggregations", {})

        total_reviews = int(overall_aggs.get("total_reviews", {}).get("value", 0))
        average_rating = overall_aggs.get("avg_rating", {}).get("value", 0) or 0
        recent_review_count = int(recent_aggs.get("review_count", {}).get("value", 0))
        recent_average_rating = recent_aggs.get("avg_rating", {}).get("value", 0) or 0
        suspicious_count = int(recent_aggs.get("suspicious_count", {}).get("doc_count", 0))

        # Calculate metrics
        rating_trend = recent_average_rating - average_rating if recent_review_count > 0 else 0
        review_velocity = recent_review_count / hours if hours > 0 else 0

        # Determine if under attack (simple heuristic)
        is_under_attack = (
            recent_review_count >= 5 and
            (rating_trend < -1.0 or review_velocity > 2.0 or suspicious_count > 3)
        )

        stats = BusinessStats(
            business_id=business_id,
            name=business.name,
            total_reviews=total_reviews,
            average_rating=round(average_rating, 2),
            recent_review_count=recent_review_count,
            recent_average_rating=round(recent_average_rating, 2),
            rating_trend=round(rating_trend, 2),
            review_velocity=round(review_velocity, 2),
            suspicious_review_count=suspicious_count,
            is_under_attack=is_under_attack
        )

        # Auto-create incident if attack detected
        if is_under_attack:
            try:
                await create_incident_if_attack_detected(es, settings, stats)
            except Exception:
                # Don't fail the stats request if incident creation fails
                pass

        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching business stats: {str(e)}")
