"""
MongoDB client and db instance. Created once at import; shared across requests.
Used by api.events and api.meditation. Fails fast if MONGO_URI is missing or ping fails.
Also provides Motor async client for user tracking.
"""

import logging
import os

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("MONGO_URI not found in .env")

# Synchronous client for existing code
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())

try:
    client.admin.command("ping")
    logger.info("MongoDB connected successfully")
except Exception as e:
    logger.exception("MongoDB connection failed: %s", e)
    raise

# DB name from URI (e.g. KarlAI)
db = client.get_database()

# Async Motor client for async operations (e.g., user tracking)
async_client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
async_db = async_client.get_database()

