"""Notification models for Review Fraud Workshop."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    """Type of notification."""

    ATTACK_DETECTED = "attack_detected"
    ATTACK_ESCALATED = "attack_escalated"
    ATTACK_RESOLVED = "attack_resolved"
    THRESHOLD_BREACH = "threshold_breach"
    SYSTEM_ALERT = "system_alert"
    INFO = "info"


class NotificationPriority(str, Enum):
    """Priority level of notification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Notification(BaseModel):
    """Notification model for alerting on review fraud activity."""

    notification_id: str = Field(..., description="Unique notification identifier")
    type: NotificationType = Field(..., description="Type of notification")
    priority: NotificationPriority = Field(default=NotificationPriority.MEDIUM)

    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")

    # Related entities
    business_id: Optional[str] = Field(default=None, description="Related business ID")
    incident_id: Optional[str] = Field(default=None, description="Related incident ID")

    # Status
    is_read: bool = Field(default=False, description="Whether notification has been read")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = Field(default=None)

    # Additional data
    data: Optional[dict] = Field(default=None, description="Additional notification data")

    class Config:
        json_schema_extra = {
            "example": {
                "notification_id": "notif_001",
                "type": "attack_detected",
                "priority": "high",
                "title": "Review Fraud Attack Detected",
                "message": "Joe's Coffee Shop is experiencing a coordinated negative review attack",
                "business_id": "abc123",
                "incident_id": "inc_001",
                "is_read": False,
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


class NotificationCreate(BaseModel):
    """Model for creating a new notification."""

    type: NotificationType = Field(..., description="Type of notification")
    priority: NotificationPriority = Field(default=NotificationPriority.MEDIUM)
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    business_id: Optional[str] = Field(default=None)
    incident_id: Optional[str] = Field(default=None)
    data: Optional[dict] = Field(default=None)

    class Config:
        json_schema_extra = {
            "example": {
                "type": "attack_detected",
                "priority": "high",
                "title": "New Attack Detected",
                "message": "Suspicious activity detected on business abc123",
                "business_id": "abc123"
            }
        }


class NotificationList(BaseModel):
    """List of notifications with metadata."""

    notifications: list[Notification]
    total: int
    unread_count: int
    page: int = 1
    page_size: int = 20
