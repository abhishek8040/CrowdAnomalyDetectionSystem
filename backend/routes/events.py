"""
Events API Router
Endpoints for querying, acknowledging, resolving, and managing anomaly events.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging
from database import (
    get_events,
    get_event_by_id,
    acknowledge_event,
    resolve_event,
    delete_event,
    clear_events,
    get_events_summary,
    save_event
)

logger = logging.getLogger(__name__)

router = APIRouter()


class AcknowledgeRequest(BaseModel):
    acknowledged_by: Optional[str] = "operator"


class ResolveRequest(BaseModel):
    notes: Optional[str] = ""


class CreateEventRequest(BaseModel):
    event_type: str
    details: Dict[str, Any] = {}
    frame_number: int = 0
    camera_id: str = "camera_0"
    severity: str = "medium"
    confidence: float = 1.0
    snapshot: Optional[str] = None


@router.get("/")
async def list_events(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high, critical)"),
    status: Optional[str] = Query(None, description="Filter by status (new, acknowledged, resolved)"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    start_date: Optional[str] = Query(None, description="Filter events after this ISO date"),
    end_date: Optional[str] = Query(None, description="Filter events before this ISO date"),
    search: Optional[str] = Query(None, description="Text search in type, details, or notes"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Retrieve filtered events list with pagination."""
    try:
        return get_events(
            event_type=event_type,
            severity=severity,
            status=status,
            camera_id=camera_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Error fetching events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve events")


@router.get("/stats")
async def events_summary():
    """Get aggregated summary counts for events."""
    try:
        return get_events_summary()
    except Exception as e:
        logger.error(f"Error fetching event summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve events summary")


@router.get("/{event_id}")
async def get_event(event_id: str):
    """Retrieve details of a single event."""
    event = get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/")
async def create_event(payload: CreateEventRequest):
    """Manually insert an event or record an external alert."""
    try:
        evt = save_event(
            event_type=payload.event_type,
            details=payload.details,
            frame_number=payload.frame_number,
            camera_id=payload.camera_id,
            severity=payload.severity,
            confidence=payload.confidence,
            snapshot=payload.snapshot
        )
        return {"success": True, "event": evt}
    except Exception as e:
        logger.error(f"Error creating event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save event")


@router.patch("/{event_id}/acknowledge")
async def acknowledge(event_id: str, payload: AcknowledgeRequest = AcknowledgeRequest()):
    """Acknowledge an active event."""
    success = acknowledge_event(event_id, acknowledged_by=payload.acknowledged_by or "operator")
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"success": True, "event_id": event_id, "status": "acknowledged"}


@router.patch("/{event_id}/resolve")
async def resolve(event_id: str, payload: ResolveRequest = ResolveRequest()):
    """Mark an event as resolved with notes."""
    success = resolve_event(event_id, notes=payload.notes or "")
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"success": True, "event_id": event_id, "status": "resolved"}


@router.delete("/{event_id}")
async def remove_event(event_id: str):
    """Delete an event."""
    success = delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"success": True, "event_id": event_id, "message": "Event deleted"}


@router.delete("/")
async def clear_all_events():
    """Clear all historical events."""
    count = clear_events()
    return {"success": True, "cleared_count": count}
