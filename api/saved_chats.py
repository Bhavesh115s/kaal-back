from fastapi import APIRouter, HTTPException
from mongodb import db
from datetime import datetime

router = APIRouter()

saved_collection = db["saved_chats"]


# ================= SAVE CHAT =================

@router.post("/save-chat")
async def save_chat(data: dict):

    try:

        saved_collection.update_one(

            {
                "user_id": data.get("user_id"),
                "session_id": data.get("session_id")
            },

            {
                "$set": {
                    "title": data.get("title", "Saved Chat"),
                    "updated_at": datetime.utcnow()
                },

                "$push": {
                    "messages": {
                        "$each": data.get("messages", [])
                    }
                },

                "$setOnInsert": {
                    "created_at": datetime.utcnow()
                }
            },

            upsert=True
        )

        return {
            "success": True,
            "message": "Chat saved successfully"
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ================= GET SAVED CHATS =================

@router.get("/saved-chats/{user_id}")
async def get_saved_chats(user_id: str):

    try:

        chats = list(
            saved_collection.find(
                {"user_id": user_id},
                {"_id": 0}
            ).sort("updated_at", -1)
        )

        return {
            "success": True,
            "chats": chats
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ================= DELETE CHAT =================

@router.delete("/delete-chat/{session_id}")
async def delete_chat(session_id: str):

    try:

        saved_collection.delete_one({
            "session_id": session_id
        })

        return {
            "success": True,
            "message": "Chat deleted"
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )