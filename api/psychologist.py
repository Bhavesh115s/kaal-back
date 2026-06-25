"""Psychologists API: list of psychologists (static JSON)."""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from services.user_tracking import track_user_usage

router = APIRouter()

# Data file (name matches existing file: psychologyist.json)
_PSYCHOLOGISTS_JSON = Path(__file__).resolve().parent.parent / "data" / "psychologyist.json"


@router.get("/")
def get_psychologists(
    background_tasks: BackgroundTasks,
    name: Optional[str] = None,
    email: Optional[str] = None
):
    """Return psychologist directory from data/psychologyist.json."""
    try:
        with open(_PSYCHOLOGISTS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        background_tasks.add_task(track_user_usage, name, email, "psychologist")
        return data
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Psychologist list is temporarily unavailable."
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=503,
            detail="Psychologist list could not be loaded."
        )
