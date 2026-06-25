import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

# IMPORT CORRECT ASYNC ARCHITECTURE PATTERN
from mongodb import async_db
from services.user_tracking import track_user_usage

logger = logging.getLogger(__name__)

router = APIRouter()

# Use async_db for proper asynchronous collection references
meditation_collection = async_db["meditation"]


@router.get("/meditation")
async def get_meditation(
    background_tasks: BackgroundTasks,
    name: Optional[str] = None,
    email: Optional[str] = None
):
    """Return one meditation document from the collection."""
    try:
        # Await the asynchronous database read operation
        meditation = await meditation_collection.find_one({}, {"_id": 0})

        # Track user usage in background with the required 'service' argument
        if name or email:
            background_tasks.add_task(
                track_user_usage, 
                name, 
                email, 
                "meditation" # Explicitly passing the service name
            )

        return meditation
        
    except Exception as e:
        logger.error(f"Error fetching meditation content: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Meditation content is temporarily unavailable."
        )