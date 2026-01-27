"""Incidents API router for Negative Review Campaign Detection Workshop."""

from datetime import datetime
from typing import Optional
import uuid

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_es_client, get_app_settings
from app.config import Settings
from app.models.incident import (
    Incident,
    IncidentCreate,
    IncidentUpdate,
    IncidentStatus,
    IncidentSeverity,
    IncidentSearchResult,
    IncidentMetrics
)
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=IncidentSearchResult)
async def list_incidents(
    status: Optional[IncidentStatus] = Query(None, description="Filter by status"),
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by severity"),
    business_id: Optional[str] = Query(None, description="Filter by business ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Results per page"),
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> IncidentSearchResult:
    """
    List incidents with optional filtering.

    - **status**: Filter by incident status
    - **severity**: Filter by incident severity
    - **business_id**: Filter by affected business
    """
    must_clauses = []

    if status:
        must_clauses.append({"term": {"status": status.value}})

    if severity:
        must_clauses.append({"term": {"severity": severity.value}})

    if business_id:
        must_clauses.append({"term": {"business_id": business_id}})

    query = {"match_all": {}} if not must_clauses else {"bool": {"must": must_clauses}}

    from_offset = (page - 1) * page_size

    try:
        response = await es.search(
            index=settings.incidents_index,
            query=query,
            from_=from_offset,
            size=page_size,
            sort=[{"detected_at": "desc"}],
            track_total_hits=True
        )

        incidents = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            source["incident_id"] = source.get("incident_id", hit["_id"])
            incidents.append(Incident(**source))

        total = response["hits"]["total"]["value"]

        return IncidentSearchResult(
            incidents=incidents,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        # If index doesn't exist, return empty results
        if "index_not_found_exception" in str(e):
            return IncidentSearchResult(
                incidents=[],
                total=0,
                page=page,
                page_size=page_size
            )
        raise HTTPException(status_code=500, detail=f"Error fetching incidents: {str(e)}")


@router.get("/{incident_id}", response_model=Incident)
async def get_incident(
    incident_id: str,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> Incident:
    """
    Get a specific incident by ID.
    """
    try:
        try:
            response = await es.get(index=settings.incidents_index, id=incident_id)
            source = response["_source"]
            source["incident_id"] = source.get("incident_id", incident_id)
            return Incident(**source)
        except:
            pass

        response = await es.search(
            index=settings.incidents_index,
            query={"term": {"incident_id": incident_id}},
            size=1
        )

        if not response["hits"]["hits"]:
            raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

        source = response["hits"]["hits"][0]["_source"]
        source["incident_id"] = source.get("incident_id", incident_id)
        return Incident(**source)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching incident: {str(e)}")


@router.post("", response_model=Incident)
async def create_incident(
    incident_data: IncidentCreate,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> Incident:
    """
    Create a new incident.
    """
    try:
        incident_id = f"inc_{uuid.uuid4().hex[:12]}"

        incident = Incident(
            incident_id=incident_id,
            business_id=incident_data.business_id,
            business_name=incident_data.business_name,
            severity=incident_data.severity,
            description=incident_data.description,
            status=IncidentStatus.DETECTED,
            detected_at=datetime.utcnow(),
            metrics=IncidentMetrics()
        )

        await es.index(
            index=settings.incidents_index,
            id=incident_id,
            document=incident.model_dump(mode="json")
        )

        return incident
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating incident: {str(e)}")


@router.patch("/{incident_id}", response_model=Incident)
async def update_incident(
    incident_id: str,
    update_data: IncidentUpdate,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> Incident:
    """
    Update an existing incident.
    """
    try:
        # Get existing incident
        incident = await get_incident(incident_id, es, settings)

        # Apply updates
        update_dict = update_data.model_dump(exclude_none=True)
        for key, value in update_dict.items():
            setattr(incident, key, value)

        # If resolving, set resolved_at
        if update_data.status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.utcnow()

        # Update in ES
        await es.update(
            index=settings.incidents_index,
            id=incident_id,
            doc=incident.model_dump(mode="json")
        )

        return incident
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating incident: {str(e)}")


@router.post("/{incident_id}/resolve", response_model=Incident)
async def resolve_incident(
    incident_id: str,
    resolution_data: dict,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> Incident:
    """
    Resolve an incident with a specific resolution.

    - **incident_id**: The incident to resolve
    - **resolution**: The resolution type (confirmed_attack, false_positive)
    """
    try:
        # Get existing incident
        incident = await get_incident(incident_id, es, settings)

        # Update status to resolved
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.utcnow()
        incident.resolution = resolution_data.get("resolution", "resolved")

        # Update in ES
        await es.update(
            index=settings.incidents_index,
            id=incident_id,
            doc={
                "status": incident.status.value,
                "resolved_at": incident.resolved_at.isoformat(),
                "resolution": incident.resolution
            }
        )

        return incident
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resolving incident: {str(e)}")


@router.delete("/{incident_id}")
async def delete_incident(
    incident_id: str,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """
    Delete an incident by ID.
    """
    try:
        await es.delete(index=settings.incidents_index, id=incident_id)
        return {"success": True, "message": f"Incident {incident_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting incident: {str(e)}")


@router.post("/detect")
async def detect_attacks(
    business_id: Optional[str] = Query(None, description="Specific business to check"),
    hours: int = Query(24, ge=1, le=168, description="Hours to analyze"),
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """
    Manually trigger attack detection and incident creation.

    This endpoint checks for negative review campaigns and automatically creates
    incidents for any detected attacks. It can check a specific business
    or scan all businesses with recent activity.

    - **business_id**: Optional specific business to check
    - **hours**: Number of hours to analyze for recent activity (default: 24)
    """
    from app.models.business import BusinessStats

    incident_service = IncidentService(es, settings)
    detected_attacks = []
    created_incidents = []

    try:
        if business_id:
            # Check specific business
            businesses_to_check = [business_id]
        else:
            # Find businesses with recent review activity
            response = await es.search(
                index=settings.reviews_index,
                query={
                    "range": {
                        "date": {"gte": f"now-{hours}h"}
                    }
                },
                aggs={
                    "businesses": {
                        "terms": {
                            "field": "business_id",
                            "size": 100
                        }
                    }
                },
                size=0
            )

            businesses_to_check = [
                bucket["key"]
                for bucket in response.get("aggregations", {}).get("businesses", {}).get("buckets", [])
            ]

        # Check each business for attacks
        for bid in businesses_to_check:
            try:
                # Get business info
                business_response = await es.search(
                    index=settings.businesses_index,
                    query={"term": {"business_id": bid}},
                    size=1
                )

                if not business_response["hits"]["hits"]:
                    continue

                business_name = business_response["hits"]["hits"][0]["_source"].get("name", "Unknown")

                # Get review stats
                overall_stats = await es.search(
                    index=settings.reviews_index,
                    query={"term": {"business_id": bid}},
                    aggs={
                        "avg_rating": {"avg": {"field": "stars"}},
                        "total_reviews": {"value_count": {"field": "review_id"}}
                    },
                    size=0
                )

                recent_stats = await es.search(
                    index=settings.reviews_index,
                    query={
                        "bool": {
                            "must": [
                                {"term": {"business_id": bid}},
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

                rating_trend = recent_average_rating - average_rating if recent_review_count > 0 else 0
                review_velocity = recent_review_count / hours if hours > 0 else 0

                # Check attack criteria
                is_under_attack = (
                    recent_review_count >= 5 and
                    (rating_trend < -1.0 or review_velocity > 2.0 or suspicious_count > 3)
                )

                if is_under_attack:
                    stats = BusinessStats(
                        business_id=bid,
                        name=business_name,
                        total_reviews=total_reviews,
                        average_rating=round(average_rating, 2),
                        recent_review_count=recent_review_count,
                        recent_average_rating=round(recent_average_rating, 2),
                        rating_trend=round(rating_trend, 2),
                        review_velocity=round(review_velocity, 2),
                        suspicious_review_count=suspicious_count,
                        is_under_attack=True
                    )

                    detected_attacks.append({
                        "business_id": bid,
                        "business_name": business_name,
                        "review_count": recent_review_count,
                        "rating_trend": round(rating_trend, 2),
                        "review_velocity": round(review_velocity, 2),
                        "suspicious_count": suspicious_count
                    })

                    # Create incident (returns None if incident already exists)
                    incident = await incident_service.create_incident_from_attack(stats)
                    if incident:
                        # Execute automated response actions for new incident
                        response_result = await incident_service.execute_response_actions(
                            bid, incident.incident_id
                        )
                        created_incidents.append({
                            "incident_id": incident.incident_id,
                            "business_id": incident.business_id,
                            "business_name": incident.business_name,
                            "severity": incident.severity.value,
                            "response_actions": response_result
                        })
                    else:
                        # Incident already exists - still execute response actions
                        # to catch any new reviews that need to be held
                        existing_incident = await incident_service.check_existing_open_incident(bid)
                        if existing_incident:
                            response_result = await incident_service.execute_response_actions(
                                bid, existing_incident.incident_id
                            )
                            # Add to detected attacks with response info
                            detected_attacks[-1]["response_actions"] = response_result
                            detected_attacks[-1]["existing_incident_id"] = existing_incident.incident_id

            except Exception as e:
                # Continue checking other businesses
                continue

        return {
            "success": True,
            "businesses_checked": len(businesses_to_check),
            "attacks_detected": len(detected_attacks),
            "incidents_created": len(created_incidents),
            "detected_attacks": detected_attacks,
            "created_incidents": created_incidents
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during detection: {str(e)}")
