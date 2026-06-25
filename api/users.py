import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from mongodb import async_db

# Variable named EXACTLY 'router' to resolve the ImportError in main.py
router = APIRouter(prefix="/api/users", tags=["Users"])
logger = logging.getLogger(__name__)

@router.get("/profile")
async def get_user_profile(email: str):
    """
    Profile retrieval endpoint for frontend synchronization.
    Queries MongoDB using the provided email, executes diagnostics, and returns configuration arrays.
    """
    logger.info(f"[PROFILE API] Email received: '{email}'")
    
    try:
        users_collection = async_db["users"]
        user = await users_collection.find_one({"email": email.strip()})
        
        if not user:
            logger.warning(f"[PROFILE API] User not found for email: '{email}'")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile document not found inside collection repository."
            )
            
        logger.info(f"[PROFILE API] User found for email: '{email}'")
        
        premium = user.get("premium", False)
        plan = user.get("plan", "free")
        premium_expires_at = user.get("premium_expires_at")
        name = user.get("name")
        
        # Format naive/aware datetime parameters cleanly into ISO string format strings
        if premium_expires_at and isinstance(premium_expires_at, datetime):
            premium_expires_at = premium_expires_at.isoformat() + "Z"
            
        # Complete mandatory production telemetry logging sequence
        logger.info(
            f"[PROFILE API] Diagnostics Summary -> "
            f"premium value: {premium} | "
            f"plan value: '{plan}' | "
            f"premium_expires_at value: {premium_expires_at}"
        )
        
        return {
            "email": user.get("email"),
            "premium": premium,
            "plan": plan,
            "premium_expires_at": premium_expires_at,
            "name": name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[PROFILE API] Critical exception handling configuration loop profiles for {email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal database mapping configuration exception: {str(e)}"
        )