# import os
# import json
# import logging
# from datetime import datetime
# from fastapi import APIRouter, Request, HTTPException, status
# import razorpay
# from mongodb import async_db

# router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])
# logger = logging.getLogger(__name__)

# RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

# try:
#     razorpay_client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))
# except Exception:
#     logger.exception("Failed to initialize Razorpay engine in webhook core context")


# @router.post("/razorpay")
# async def handle_razorpay_webhook(request: Request):
#     """
#     Phase 3: Processes incoming server-to-server actions natively across the subscription lifecycle.
#     Implements mathematical idempotency via Razorpay cycle epoch boundaries.
#     """
#     raw_body = await request.body()
#     signature = request.headers.get("X-Razorpay-Signature")

#     if not signature or not RAZORPAY_WEBHOOK_SECRET:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing signature headers or secret configuration.")

#     try:
#         razorpay_client.utility.verify_webhook_signature(
#             raw_body.decode("utf-8"),
#             signature,
#             RAZORPAY_WEBHOOK_SECRET
#         )
#     except Exception:
#         logger.warning("Incoming webhook blocked: Failed signature match criteria.")
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature configuration.")

#     payload = json.loads(raw_body.decode("utf-8"))
#     event_type = payload.get("event")
#     users_collection = async_db["users"]
    
#     logger.info(f"Processing structural webhook payload event: {event_type}")

#     event_payload = payload.get("payload", {})
#     subscription_entity = event_payload.get("subscription", {}).get("entity", {})
#     payment_entity = event_payload.get("payment", {}).get("entity", {})
    
#     email = subscription_entity.get("notes", {}).get("email") or payment_entity.get("notes", {}).get("email") or payment_entity.get("email")
#     subscription_id = subscription_entity.get("id") or payment_entity.get("subscription_id")

#     if not email:
#         logger.warning(f"Webhook event parsed successfully but dropped: Identity data missing across scopes for event {event_type}")
#         return {"success": True}

#     now = datetime.utcnow()

#     # Safely parse current_end Unix timestamp from Razorpay entity if it exists
#     current_end_epoch = subscription_entity.get("current_end")
#     if current_end_epoch:
#         # Convert Unix epoch to datetime object
#         premium_expires_at = datetime.utcfromtimestamp(float(current_end_epoch))
#     else:
#         # Fallback security window if entity mapping fails
#         premium_expires_at = now + timedelta(days=30)

#     try:
#         if event_type == "subscription.activated":
#             await users_collection.update_one(
#                 {"email": email},
#                 {
#                     "$set": {
#                         "premium": True,
#                         "plan": "monthly",
#                         "subscription_id": subscription_id,
#                         "subscription_status": "active",
#                         "premium_since": now,
#                         "premium_expires_at": premium_expires_at
#                     }
#                 }
#             )
#             logger.info(f"Asynchronously activated billing profile for user {email} via webhook channels.")

#         elif event_type == "subscription.charged":
#             # Idempotent Extension: Using exact date limits extracted from the payload
#             await users_collection.update_one(
#                 {"email": email},
#                 {
#                     "$set": {
#                         "premium": True,
#                         "subscription_status": "active",
#                         "premium_expires_at": premium_expires_at,
#                         "last_billing_charge_event": now,
#                         "last_payment_id": payment_entity.get("id")
#                     }
#                 }
#             )
#             logger.info(f"Synchronized premium expiration timeline for user profile {email} to exact date: {premium_expires_at}")

#         elif event_type == "subscription.cancelled":
#             await users_collection.update_one(
#                 {"email": email},
#                 {
#                     "$set": {
#                         "subscription_status": "cancelled",
#                         "updated_at": now
#                     }
#                 }
#             )
#             logger.info(f"Flagged subscription status configuration as cancelled for user {email}. Access persists until expiry.")

#         elif event_type == "payment.failed":
#             await users_collection.update_one(
#                 {"email": email},
#                 {
#                     "$set": {
#                         "subscription_status": "payment_failed",
#                         "updated_at": now
#                     }
#                 }
#             )
#             logger.warning(f"Flagged structural auto-pay payment trace exception for user {email}.")

#         return {"success": True}

#     except Exception as processing_err:
#         logger.exception(f"Internal processing failure while handling webhook event context variables: {event_type}")
#         raise HTTPException(status_code=500, detail="Database sync tracking failed.")