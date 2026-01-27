"""Notifications API router for Review Campaign Detection Workshop."""

from datetime import datetime
from typing import Optional
import uuid

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_es_client, get_app_settings
from app.config import Settings
from app.models.notification import (
    Notification,
    NotificationCreate,
    NotificationList,
    NotificationType,
    NotificationPriority
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
async def list_notifications(
    unread_only: bool = Query(False, description="Only show unread notifications"),
    type: Optional[NotificationType] = Query(None, description="Filter by notification type"),
    priority: Optional[NotificationPriority] = Query(None, description="Filter by priority"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> NotificationList:
    """
    List notifications with optional filtering.

    - **unread_only**: Only return unread notifications
    - **type**: Filter by notification type
    - **priority**: Filter by priority level
    """
    must_clauses = []

    if unread_only:
        must_clauses.append({"term": {"is_read": False}})

    if type:
        must_clauses.append({"term": {"type": type.value}})

    if priority:
        must_clauses.append({"term": {"priority": priority.value}})

    query = {"match_all": {}} if not must_clauses else {"bool": {"must": must_clauses}}

    from_offset = (page - 1) * page_size

    try:
        # Get notifications
        response = await es.search(
            index=settings.notifications_index,
            query=query,
            from_=from_offset,
            size=page_size,
            sort=[{"created_at": "desc"}],
            track_total_hits=True
        )

        notifications = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            source["notification_id"] = source.get("notification_id", hit["_id"])
            notifications.append(Notification(**source))

        total = response["hits"]["total"]["value"]

        # Get unread count
        unread_response = await es.count(
            index=settings.notifications_index,
            query={"term": {"is_read": False}}
        )
        unread_count = unread_response["count"]

        return NotificationList(
            notifications=notifications,
            total=total,
            unread_count=unread_count,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        # If index doesn't exist, return empty results
        if "index_not_found_exception" in str(e):
            return NotificationList(
                notifications=[],
                total=0,
                unread_count=0,
                page=page,
                page_size=page_size
            )
        raise HTTPException(status_code=500, detail=f"Error fetching notifications: {str(e)}")


@router.get("/{notification_id}", response_model=Notification)
async def get_notification(
    notification_id: str,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> Notification:
    """
    Get a specific notification by ID.
    """
    try:
        try:
            response = await es.get(index=settings.notifications_index, id=notification_id)
            source = response["_source"]
            source["notification_id"] = source.get("notification_id", notification_id)
            return Notification(**source)
        except:
            pass

        response = await es.search(
            index=settings.notifications_index,
            query={"term": {"notification_id": notification_id}},
            size=1
        )

        if not response["hits"]["hits"]:
            raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found")

        source = response["hits"]["hits"][0]["_source"]
        source["notification_id"] = source.get("notification_id", notification_id)
        return Notification(**source)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notification: {str(e)}")


@router.post("", response_model=Notification)
async def create_notification(
    notification_data: NotificationCreate,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> Notification:
    """
    Create a new notification.
    """
    try:
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"

        notification = Notification(
            notification_id=notification_id,
            type=notification_data.type,
            priority=notification_data.priority,
            title=notification_data.title,
            message=notification_data.message,
            business_id=notification_data.business_id,
            incident_id=notification_data.incident_id,
            data=notification_data.data,
            is_read=False,
            created_at=datetime.utcnow()
        )

        await es.index(
            index=settings.notifications_index,
            id=notification_id,
            document=notification.model_dump(mode="json")
        )

        return notification
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating notification: {str(e)}")


@router.post("/{notification_id}/read", response_model=Notification)
async def mark_notification_read(
    notification_id: str,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> Notification:
    """
    Mark a notification as read.
    """
    try:
        # Get existing notification
        notification = await get_notification(notification_id, es, settings)

        # Update read status
        notification.is_read = True
        notification.read_at = datetime.utcnow()

        # Update in ES
        await es.update(
            index=settings.notifications_index,
            id=notification_id,
            doc={"is_read": True, "read_at": notification.read_at.isoformat()}
        )

        return notification
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking notification as read: {str(e)}")


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """
    Mark all notifications as read.
    """
    try:
        await es.update_by_query(
            index=settings.notifications_index,
            query={"term": {"is_read": False}},
            script={
                "source": "ctx._source.is_read = true; ctx._source.read_at = params.now",
                "params": {"now": datetime.utcnow().isoformat()}
            }
        )

        return {"success": True, "message": "All notifications marked as read"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking notifications as read: {str(e)}")


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """
    Delete a notification by ID.
    """
    try:
        await es.delete(index=settings.notifications_index, id=notification_id)
        return {"success": True, "message": f"Notification {notification_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting notification: {str(e)}")
