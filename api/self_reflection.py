import json
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from services.user_tracking import track_user_usage


router = APIRouter()


@router.get("/")
def get_questions(
    background_tasks: BackgroundTasks,
    name: Optional[str] = None,
    email: Optional[str] = None
):
    with open("data/self_reflection.json", "r") as f:
        data = json.load(f)
    background_tasks.add_task(track_user_usage, name, email, "self_reflection")
    return data

