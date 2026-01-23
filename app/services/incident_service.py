"""Incident management service for Review Fraud Workshop.

This service handles auto-creation of incidents when review fraud attacks are detected,
with deduplication to avoid creating multiple incidents for the same ongoing attack.
"""

from datetime import datetime
from typing import Optional
import uuid

from elasticsearch import AsyncElasticsearch

from app.config import Settings
from app.models.incident import (
    Incident,
    IncidentStatus,
    IncidentSeverity,
    IncidentMetrics,
)
from app.models.business import BusinessStats


class IncidentService:
    """Service for managing review fraud incidents."""

    def __init__(self, es_client: AsyncElasticsearch, settings: Settings):
        self.es = es_client
        self.settings = settings

    async def check_existing_open_incident(self, business_id: str) -> Optional[Incident]:
        """
        Check if there's an existing open incident for the given business.

        Returns the incident if found, None otherwise.
        """
        try:
            # Search for open incidents (detected, investigating, or confirmed) for this business
            response = await self.es.search(
                index=self.settings.incidents_index,
                query={
                    "bool": {
                        "must": [
                            {"term": {"business_id": business_id}},
                            {
                                "terms": {
                                    "status": [
                                        IncidentStatus.DETECTED.value,
                                        IncidentStatus.INVESTIGATING.value,
                                        IncidentStatus.CONFIRMED.value,
                                        IncidentStatus.MITIGATED.value,
                                    ]
                                }
                            }
                        ]
                    }
                },
                size=1,
                sort=[{"detected_at": "desc"}]
            )

            if response["hits"]["hits"]:
                source = response["hits"]["hits"][0]["_source"]
                source["incident_id"] = source.get("incident_id", response["hits"]["hits"][0]["_id"])
                return Incident(**source)

            return None

        except Exception as e:
            # If index doesn't exist or other error, return None
            if "index_not_found_exception" in str(e):
                return None
            raise

    def determine_severity(self, stats: BusinessStats) -> IncidentSeverity:
        """
        Determine incident severity based on attack metrics.

        Severity levels:
        - CRITICAL: Very high velocity (>5/hr) or massive review count (>20)
        - HIGH: High velocity (>3/hr) or significant review count (>10) or severe rating drop (<-2)
        - MEDIUM: Moderate attack indicators
        - LOW: Minimal attack indicators
        """
        if stats.review_velocity > 5.0 or stats.recent_review_count > 20:
            return IncidentSeverity.CRITICAL
        elif (stats.review_velocity > 3.0 or
              stats.recent_review_count > 10 or
              stats.rating_trend < -2.0):
            return IncidentSeverity.HIGH
        elif stats.recent_review_count >= 5 or stats.suspicious_review_count > 3:
            return IncidentSeverity.MEDIUM
        else:
            return IncidentSeverity.LOW

    async def create_incident_from_attack(
        self,
        stats: BusinessStats,
        auto_created: bool = True
    ) -> Optional[Incident]:
        """
        Create an incident from detected attack statistics.

        Args:
            stats: BusinessStats object with attack detection results
            auto_created: Whether this was auto-created by the system

        Returns:
            The created Incident, or None if an incident already exists
        """
        # Check for existing open incident to avoid duplicates
        existing = await self.check_existing_open_incident(stats.business_id)
        if existing:
            # Update the existing incident with latest metrics if needed
            await self.update_incident_metrics(existing.incident_id, stats)
            return None

        # Determine severity based on attack metrics
        severity = self.determine_severity(stats)

        # Generate unique incident ID
        incident_id = f"inc_{uuid.uuid4().hex[:12]}"

        # Build description
        description = self._build_incident_description(stats, auto_created)

        # Create incident metrics
        metrics = IncidentMetrics(
            review_count=stats.recent_review_count,
            unique_attackers=stats.suspicious_review_count,  # Approximation
            average_rating=stats.recent_average_rating,
            rating_drop=abs(stats.rating_trend) if stats.rating_trend < 0 else 0,
            reviews_per_minute=round(stats.review_velocity / 60, 2),
        )

        # Create the incident object
        incident = Incident(
            incident_id=incident_id,
            business_id=stats.business_id,
            business_name=stats.name,
            status=IncidentStatus.DETECTED,
            severity=severity,
            detected_at=datetime.utcnow(),
            description=description,
            metrics=metrics,
            response_actions=["Auto-detected by monitoring system"] if auto_created else [],
        )

        # Index the incident in Elasticsearch
        try:
            await self.es.index(
                index=self.settings.incidents_index,
                id=incident_id,
                document=incident.model_dump(mode="json"),
                refresh=True  # Make it immediately searchable
            )
            return incident
        except Exception as e:
            # If index doesn't exist, try to create it with basic settings
            if "index_not_found_exception" in str(e):
                await self._ensure_incidents_index()
                await self.es.index(
                    index=self.settings.incidents_index,
                    id=incident_id,
                    document=incident.model_dump(mode="json"),
                    refresh=True
                )
                return incident
            raise

    async def update_incident_metrics(self, incident_id: str, stats: BusinessStats) -> None:
        """
        Update an existing incident with the latest attack metrics.
        """
        try:
            metrics = {
                "review_count": stats.recent_review_count,
                "average_rating": stats.recent_average_rating,
                "rating_drop": abs(stats.rating_trend) if stats.rating_trend < 0 else 0,
                "reviews_per_minute": round(stats.review_velocity / 60, 2),
            }

            await self.es.update(
                index=self.settings.incidents_index,
                id=incident_id,
                doc={
                    "metrics": metrics,
                    "last_updated": datetime.utcnow().isoformat(),
                }
            )
        except Exception:
            # Silently ignore update failures
            pass

    def _build_incident_description(self, stats: BusinessStats, auto_created: bool) -> str:
        """Build a human-readable incident description."""
        parts = []

        if auto_created:
            parts.append("Automatically detected review fraud attack.")
        else:
            parts.append("Review fraud attack detected.")

        parts.append(f"Business '{stats.name}' received {stats.recent_review_count} reviews recently.")

        if stats.rating_trend < 0:
            parts.append(f"Rating dropped by {abs(stats.rating_trend):.1f} points.")

        if stats.review_velocity > 0:
            parts.append(f"Review velocity: {stats.review_velocity:.1f} reviews/hour.")

        if stats.suspicious_review_count > 0:
            parts.append(f"Suspicious reviews detected: {stats.suspicious_review_count}.")

        return " ".join(parts)

    async def _ensure_incidents_index(self) -> None:
        """Ensure the incidents index exists."""
        try:
            exists = await self.es.indices.exists(index=self.settings.incidents_index)
            if not exists:
                await self.es.indices.create(
                    index=self.settings.incidents_index,
                    body={
                        "mappings": {
                            "properties": {
                                "incident_id": {"type": "keyword"},
                                "business_id": {"type": "keyword"},
                                "business_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                                "detected_at": {"type": "date"},
                                "resolved_at": {"type": "date"},
                                "status": {"type": "keyword"},
                                "severity": {"type": "keyword"},
                                "description": {"type": "text"},
                                "metrics": {"type": "object"},
                                "attacker_ids": {"type": "keyword"},
                                "review_ids": {"type": "keyword"},
                                "resolution": {"type": "keyword"},
                                "response_actions": {"type": "keyword"},
                                "notes": {"type": "text"},
                            }
                        }
                    }
                )
        except Exception:
            pass  # Index might already exist

    async def protect_business(self, business_id: str) -> bool:
        """
        Enable rating protection on a business.

        This prevents the malicious reviews from affecting the displayed rating.
        """
        try:
            await self.es.update(
                index=self.settings.businesses_index,
                id=business_id,
                doc={
                    "rating_protected": True,
                    "protection_reason": "review_fraud_detected",
                    "protected_since": datetime.utcnow().isoformat(),
                },
                refresh=True
            )
            return True
        except Exception as e:
            print(f"Error protecting business {business_id}: {e}")
            return False

    async def hold_suspicious_reviews(self, business_id: str, hours: int = 1) -> int:
        """
        Hold suspicious reviews for a business.

        This marks low-trust reviews as 'held' so they don't affect ratings
        and can be reviewed manually.

        Returns the number of reviews held.
        """
        try:
            # Find suspicious reviews (low trust score, recent, low rating)
            response = await self.es.update_by_query(
                index=self.settings.reviews_index,
                query={
                    "bool": {
                        "must": [
                            {"term": {"business_id": business_id}},
                            {"range": {"date": {"gte": f"now-{hours}h"}}},
                            {"range": {"stars": {"lte": 2}}},
                        ],
                        "should": [
                            {"term": {"is_simulated": True}},
                        ]
                    }
                },
                script={
                    "source": "ctx._source.status = 'held'; ctx._source.held_at = params.timestamp; ctx._source.hold_reason = 'review_fraud_detected'",
                    "params": {
                        "timestamp": datetime.utcnow().isoformat()
                    }
                },
                refresh=True
            )
            return response.get("updated", 0)
        except Exception as e:
            print(f"Error holding reviews for {business_id}: {e}")
            return 0

    async def execute_response_actions(self, business_id: str, incident_id: str) -> dict:
        """
        Execute all automated response actions for a detected attack.

        Returns a summary of actions taken.
        """
        actions_taken = []

        # 1. Protect the business rating
        if await self.protect_business(business_id):
            actions_taken.append("business_protected")

        # 2. Hold suspicious reviews
        held_count = await self.hold_suspicious_reviews(business_id)
        if held_count > 0:
            actions_taken.append(f"held_{held_count}_reviews")

        # 3. Update incident with response actions
        try:
            await self.es.update(
                index=self.settings.incidents_index,
                id=incident_id,
                doc={
                    "response_actions": actions_taken,
                    "response_executed_at": datetime.utcnow().isoformat(),
                }
            )
        except Exception:
            pass

        return {
            "business_protected": "business_protected" in actions_taken,
            "reviews_held": held_count,
            "actions": actions_taken
        }


async def create_incident_if_attack_detected(
    es: AsyncElasticsearch,
    settings: Settings,
    stats: BusinessStats
) -> Optional[Incident]:
    """
    Convenience function to create an incident if an attack is detected.

    This is meant to be called from the stats endpoint or other detection points.

    Args:
        es: Elasticsearch client
        settings: Application settings
        stats: Business statistics with attack detection results

    Returns:
        Created Incident if attack detected and incident created, None otherwise
    """
    if not stats.is_under_attack:
        return None

    service = IncidentService(es, settings)
    return await service.create_incident_from_attack(stats, auto_created=True)
