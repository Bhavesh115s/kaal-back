import os
import logging
from datetime import datetime, timedelta, timezone
import razorpay
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from razorpay.errors import SignatureVerificationError

from mongodb import async_db

# Setup router and logger
router = APIRouter(prefix="/api/payment", tags=["Payment"])
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize Razorpay Client
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    logger.error("CRITICAL: Razorpay credentials are missing from environment variables!")

try:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    logger.info("Razorpay client initialized successfully.")
except Exception as e:
    logger.exception("Failed to initialize Razorpay client")


class VerifyPaymentRequest(BaseModel):
    email: EmailStr
    payment_id: str
    order_id: str  # Restored from subscription_id
    signature: str
    plan: str


@router.post("/create-order")
async def create_order():
    """
    Restored one-time order creation endpoint.
    Generates a fixed-amount order tracking token for frontend checkout validation.
    """
    try:
        order_payload = {
            "amount": 4900,  # ₹49 in paise
            "currency": "INR",
            "payment_capture": 1  # Auto-capture payment instantly upon authorization
        }
        
        order = razorpay_client.order.create(data=order_payload)
        logger.info(f"Successfully generated one-time order entity: {order.get('id')}")
        return order
        
    except Exception as e:
        logger.exception("Failed to initialize Razorpay one-time order object context")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": str(e)}
        )


@router.post("/verify")
async def verify_payment(payload: VerifyPaymentRequest):
    """
    Restored one-time order verification pipeline.
    Validates cryptographic order signatures and provisions a strict 30-day time-bound window.
    """
    logger.info("Incoming one-time order payment signature verification sequence.")
    logger.info(f"Email: {payload.email}")
    logger.info(f"Order ID: {payload.order_id} | Payment ID: {payload.payment_id}")
    
    # 1. Verify standard Razorpay Order Signature
    try:
        params_dict = {
            'razorpay_order_id': payload.order_id,
            'razorpay_payment_id': payload.payment_id,
            'razorpay_signature': payload.signature
        }
        
        # Swapped back to one-time payment signature validation mechanics
        razorpay_client.utility.verify_payment_signature(params_dict)
        logger.info("Order payment signature verification passed.")

    except SignatureVerificationError as sve:
        logger.exception("Order signature checksum validation failed checkpoint error")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": f"Invalid cryptographic signature: {str(sve)}"}
        )
    except Exception as e:
        logger.exception("Unexpected payment signature verification handling error")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": str(e)}
        )

    # 2. Database Update Phase (Matching user_tracking.py pattern)
    try:
        users_collection = async_db["users"]
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Standardizing transaction parameters while ensuring strict 30-day temporal tracking bounds
        update_data = {
            "premium": True,
            "plan": payload.plan,
            "premium_since": now,
            "premium_expires_at": now + timedelta(days=30),
            "payment_id": payload.payment_id,
            "razorpay_order_id": payload.order_id
        }

        # Update existing user document natively by email tracking key
        result = await users_collection.update_one(
            {"email": payload.email},
            {"$set": update_data}
        )
        
        logger.info(
            f"Order Verification DB Update Metrics -> "
            f"Email: {payload.email} | "
            f"Order ID: {payload.order_id} | "
            f"Matched Count: {result.matched_count} | "
            f"Modified Count: {result.modified_count}"
        )

        if result.matched_count == 0:
            logger.warning(f"WARNING: User tracking document missing for email identity: {payload.email}")
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "message": "User file entry not initialized inside collection parameters."}
            )

        logger.info(f"Successfully activated standard premium access status parameters for user: {payload.email}.")

        return {
            "success": True,
            "premium": True
        }

    except Exception as e:
        logger.exception("Database configuration persistence step update failed")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": str(e)}
        )