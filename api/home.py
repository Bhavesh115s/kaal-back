"""Home page content API: serves static JSON for the landing section."""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from services.user_tracking import track_user_usage


router = APIRouter()

# Path to data file relative to this module (avoids CWD dependency)
_HOME_JSON = Path(__file__).resolve().parent.parent / "data" / "home.json"


@router.get("/")
def get_home_content(
    background_tasks: BackgroundTasks,
    name: Optional[str] = None,
    email: Optional[str] = None
):
    """Return home page content from data/home.json."""
    try:
        with open(_HOME_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        background_tasks.add_task(track_user_usage, name, email, "home")
        return data
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Home content is temporarily unavailable."
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=503,
            detail="Home content could not be loaded."
        )
