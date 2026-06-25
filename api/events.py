"""Events API: list events from MongoDB (e.g. upcoming workshops)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from mongodb import db
from services.user_tracking import track_user_usage


router = APIRouter()

events_collection = db["events"]


@router.get("/events")
def get_events(
    background_tasks: BackgroundTasks,
    name: Optional[str] = None,
    email: Optional[str] = None
):
    """Return all events from the events collection. Excludes _id."""
    try:
        events = list(events_collection.find({}, {"_id": 0}))
        background_tasks.add_task(track_user_usage, name, email, "events")
        return {
            "count": len(events),
            "events": events
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Events are temporarily unavailable."
        )

