import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from services.user_tracking import track_user_usage


router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "donate.json")


@router.get("/donate")
def get_donation_info(
    background_tasks: BackgroundTasks,
    name: Optional[str] = None,
    email: Optional[str] = None
):
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    background_tasks.add_task(track_user_usage, name, email, "donate")
    return data