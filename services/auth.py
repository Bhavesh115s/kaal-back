# auth.py

import os
from typing import Optional, Dict, List

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from dotenv import load_dotenv

load_dotenv()

# =========================
# API KEY CONFIG
# =========================

API_KEY_HEADER = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)

# Load API keys ONLY from env
API_KEYS = os.getenv("API_KEYS")

if not API_KEYS:
    raise RuntimeError("API_KEYS not set in environment")

VALID_API_KEYS = [key.strip() for key in API_KEYS.split(",")]

# =========================
# AUTH DEPENDENCY
# =========================

async def get_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    if api_key is None:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="API key is required in the X-API-Key header"
        )

    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )

    return api_key

# =========================
# OPTIONAL PERMISSIONS
# =========================

def check_permissions(api_key: str, required_permissions: List[str]) -> Dict[str, bool]:
    """
    Stub for RBAC — extend later if needed
    """
    permissions = {
        "chat:read": True,
        "chat:write": True,
        "tools:invoke": True,
    }

    return {perm: permissions.get(perm, False) for perm in required_permissions}

