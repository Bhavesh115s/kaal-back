"""
Async user tracking service using Motor (non-blocking MongoDB operations).
Tracks unique users, their services used, and usage patterns.
"""

import logging
from datetime import datetime
from typing import Optional

from mongodb import async_db

logger = logging.getLogger(__name__)


async def track_user_usage(
    name: Optional[str],
    email: Optional[str],
    service: str
) -> None:
    """
    Track or update user usage in MongoDB.

    Args:
        name: User's name (optional, can be None)
        email: User's email (optional, can be None)
        service: Name of service used (e.g., 'chat', 'meditation', 'psychologist')

    Returns:
        None. If any error occurs, logs it and continues silently.

    Logic:
        - If email is None → return immediately (cannot track without email)
        - Find user by email
        - If user exists:
            - Increment usage_count by 1
            - Add service to services_used array (avoid duplicates)
            - Update last_active timestamp
        - If user does not exist:
            - Create new user document with name, email, services_used, usage_count, first_visit, last_active
    """

    if not email:
        return

    try:
        users_collection = async_db["users"]
        now = datetime.utcnow()

        existing_user = await users_collection.find_one(
            {"email": email}
        )

        if existing_user:

            update_data = {
                "usage_count": existing_user.get(
                    "usage_count",
                    0
                ) + 1,
                "last_active": now,
            }

            services = existing_user.get(
                "services_used",
                []
            )

            if service not in services:
                services.append(service)
                update_data["services_used"] = services

            await users_collection.update_one(
                {"email": email},
                {"$set": update_data}
            )

            logger.debug(
                f"Updated user tracking for email: {email}, service: {service}"
            )

        else:

            new_user = {
                "email": email,
                "name": name,
                "services_used": [service],
                "usage_count": 1,
                "first_visit": now,
                "last_active": now,
            }

            await users_collection.insert_one(
                new_user
            )

            logger.debug(
                f"Created new user tracking for email: {email}, service: {service}"
            )

    except Exception as e:

        logger.exception(
            f"Error tracking user usage for email {email}, service {service}: {e}"
        )