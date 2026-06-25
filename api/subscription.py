# import os
# import logging
# from datetime import datetime
# import razorpay
# from fastapi import APIRouter, HTTPException, status
# from pydantic import BaseModel, EmailStr
# from mongodb import async_db

# router = APIRouter(prefix="/api/subscription", tags=["Subscription"])
# logger = logging.getLogger(__name__)

# # Initialize Razorpay Client
# RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
# RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# # Defaulting directly to your active live subscription plan instance
# RAZORPAY_PLAN_ID = os.getenv("RAZORPAY_PLAN_ID", "plan_SwJ506iQAnbuUi")

# try:
#     razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
#     logger.info("Razorpay client initialized successfully within subscription module.")
# except Exception:
#     logger.exception("Failed to initialize Razorpay client within subscription module")


# class CreateSubscriptionRequest(BaseModel):
#     email: EmailStr


# @router.post("/create")
# async def create_recurring_subscription(payload: CreateSubscriptionRequest):
#     """
#     Phase 1: Initializes a recurring subscription entity inside Razorpay
#     and logs the intent tracking parameters inside the existing users collection.
#     """
#     try:
#         # Define parameters for a standard open-ended monthly plan sequence
#         subscription_payload = {
#             "plan_id": RAZORPAY_PLAN_ID,
#             "total_count": 60,  # 5 years of monthly billing cycles
#             "quantity": 1,
#             "customer_notify": 1,
#             "notes": {"email": payload.email}
#         }

#         # Issue call to Razorpay Core billing API
#         subscription = razorpay_client.subscription.create(data=subscription_payload)
#         subscription_id = subscription.get("id")
#         subscription_status = "created"

#         # Mutate target profile in existing users collection asynchronously
#         users_collection = async_db["users"]
#         result = await users_collection.update_one(
#             {"email": payload.email},
#             {
#                 "$set": {
#                     "subscription_id": subscription_id,
#                     "subscription_status": subscription_status,
#                     "updated_at": datetime.utcnow()
#                 }
#             }
#         )

#         if result.matched_count == 0:
#             logger.warning(f"Subscription initialized but user profile row missing in DB for email: {payload.email}")

#         logger.info(f"Subscription token created: {subscription_id} for user: {payload.email}")
        
#         # Return exact requested validation object schema
#         return {
#             "subscription_id": subscription_id,
#             "status": subscription_status
#         }

#     except Exception as e:
#         logger.exception(f"Razorpay subscription generation failed for {payload.email}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"Failed to initialize subscription context: {str(e)}"
#         # )