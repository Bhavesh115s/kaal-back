import logging
from services.auth import get_api_key
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Router Imports
from api.saved_chats import router as saved_chats_router
from api.chat import router as chat_router
from api.donate import router as donate_router
from api.events import router as events_router
from api.home import router as home_router
from api.meditation import router as meditation_router
from api.psychologist import router as psychologist_router
from api.self_reflection import router as reflection_router
from api.payment import router as payment_router
from api.users import router as users_router  # Added Users Profile Router

logger = logging.getLogger(__name__)

app = FastAPI(title="KALL AI", dependencies=[Depends(get_api_key)])

# ================== CORS CONFIG (DEV SAFE) ==================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://kaalai.dev.andaihub.com",
        "https://kaalai.in/"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================== GLOBAL EXCEPTION HANDLER ==================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ================== ROUTERS ==================
# Routes with explicit /api prefix
app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(donate_router, prefix="/api", tags=["Donate"])
app.include_router(home_router, prefix="/api/home", tags=["Home"])
app.include_router(psychologist_router, prefix="/api/psychologists", tags=["Psychologist"])
app.include_router(reflection_router, prefix="/api/self-reflection", tags=["Self Reflection"])
app.include_router(saved_chats_router, prefix="/api", tags=["Saved Chats"])

# Routes handling root-level definitions natively
app.include_router(events_router, tags=["Events"])
app.include_router(meditation_router, tags=["Meditation"])
app.include_router(payment_router, tags=["Payment"])
app.include_router(users_router)  # Registered Users Profile Router



# ================== HEALTH CHECK ==================
@app.get("/")
def health():
    return {"status": "KALL-AI Backend Active"}