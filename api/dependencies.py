import logging
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from mongodb import async_db

# This will be imported from your Phase 3 security core
from core.security import verify_supabase_token

logger = logging.getLogger(__name__)

async def get_current_user_email(payload: dict = Depends(verify_supabase_token)) -> str:
    """
    Extracts user identity directly from verified token metadata claims,
    completely eliminating reliance on arbitrary client headers.
    """
    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Authentication claims metadata missing email reference."
        )
    return email


async def verify_premium_user(email: str = Depends(get_current_user_email)) -> dict:
    """
    Validates user premium properties and real-time subscription lifecycle boundaries.
    """
    try:
        users_collection = async_db["users"]
        user = await users_collection.find_one({"email": email})

        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Access denied: User record not initialized."
            )

        is_premium_flagged = user.get("premium", False)
        expiration_date = user.get("premium_expires_at")
        
        # Safe timezone-neutral evaluation pattern
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if not is_premium_flagged or not expiration_date or expiration_date <= now:
            logger.warning(f"Subscription validation rejected for: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Premium subscription required or feature authorization period has expired."
            )
            
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing security check for user {email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Internal authorization framework fault."
        )