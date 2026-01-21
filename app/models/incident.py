"""Incident models for Review Bomb Workshop."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    """Status of a review bomb incident."""

    DETECTED = "detected"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class IncidentSeverity(str, Enum):
    """Severity level of an incident."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentMetrics(BaseModel):
    """Metrics associated with a review bomb incident."""

    review_count: int = Field(default=0, description="Number of suspicious reviews")
    unique_attackers: int = Field(default=0, description="Number of unique attacker profiles")
    average_rating: float = Field(default=0.0, description="Average rating of attack reviews")
    rating_drop: float = Field(default=0.0, description="Overall rating drop caused")
    attack_duration_minutes: int = Field(default=0, description="Duration of attack")
    reviews_per_minute: float = Field(default=0.0, description="Attack velocity")


class Incident(BaseModel):
    """Review bomb incident model."""

    incident_id: str = Field(..., description="Unique incident identifier")
    business_id: str = Field(..., description="Affected business ID")
    business_name: str = Field(..., description="Affected business name")

    status: IncidentStatus = Field(default=IncidentStatus.DETECTED)
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM)

    # Timing
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None, description="Estimated attack start time")
    resolved_at: Optional[datetime] = Field(default=None)

    # Details
    description: str = Field(default="", description="Incident description")
    metrics: IncidentMetrics = Field(default_factory=IncidentMetrics)

    # Related entities
    attacker_ids: List[str] = Field(default_factory=list, description="Known attacker IDs")
    review_ids: List[str] = Field(default_factory=list, description="Suspicious review IDs")

    # Response
    resolution: Optional[str] = Field(default=None, description="Resolution type (confirmed_attack, false_positive)")
    response_actions: List[str] = Field(default_factory=list, description="Actions taken")
    notes: str = Field(default="", description="Additional notes")

    class Config:
        json_schema_extra = {
            "example": {
                "incident_id": "inc_001",
                "business_id": "abc123",
                "business_name": "Joe's Coffee Shop",
                "status": "detected",
                "severity": "high",
                "detected_at": "2024-01-15T10:30:00Z",
                "description": "Coordinated review bomb attack detected",
                "metrics": {
                    "review_count": 45,
                    "unique_attackers": 12,
                    "average_rating": 1.2,
                    "rating_drop": 2.1,
                    "reviews_per_minute": 3.5
                }
            }
        }


class IncidentCreate(BaseModel):
    """Model for creating a new incident."""

    business_id: str = Field(..., description="Affected business ID")
    business_name: str = Field(..., description="Affected business name")
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM)
    description: str = Field(default="", description="Initial description")

    class Config:
        json_schema_extra = {
            "example": {
                "business_id": "abc123",
                "business_name": "Joe's Coffee Shop",
                "severity": "high",
                "description": "Sudden spike in negative reviews detected"
            }
        }


class IncidentUpdate(BaseModel):
    """Model for updating an incident."""

    status: Optional[IncidentStatus] = None
    severity: Optional[IncidentSeverity] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    response_actions: Optional[List[str]] = None


class IncidentSearchResult(BaseModel):
    """Search result for incidents."""

    incidents: List[Incident]
    total: int
    page: int = 1
    page_size: int = 10
