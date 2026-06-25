import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from services.ai import generate_ai_response
from services.emotion import detect_emotion, is_deep_emotion
from services.memory import memory
from services.shloka import get_relevant_shloka, get_meaning_for_language
from services.user_tracking import track_user_usage

# IMPORT CORRECT ARCHITECTURE PATTERN
from mongodb import async_db
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    user_id: Optional[str] = None
    session_id: str = Field(..., max_length=256)
    message: str = Field(..., max_length=4096)

class ChatResponse(BaseModel):
    reply: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIRM_WORDS: set[str] = {
    "ha", "haan", "yes", "yes please",
    "ok", "okay", "please", "sure",
    "haa", "han", "bilkul", "theek hai",
}

# Only trigger explicit shloka lookup when the user *asks* for one.
# Automatic deep-query shlokas are handled inside generate_ai_response.
SHLOKA_KEYWORDS: tuple[str, ...] = (
    "shloka", "shlok", "geeta", "gita", "bhagavad gita",
    "sanskrit verse", "quote a shloka", "ek shloka", "koi shloka",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wants_shloka(text: str) -> bool:
    """Return True only when the user explicitly requests a shloka."""
    lower = text.lower()
    return any(kw in lower for kw in SHLOKA_KEYWORDS)


def _save_and_track(
    session_id: str,
    user_message: str,
    reply: str,
    background_tasks: BackgroundTasks,
    name: Optional[str],
    email: Optional[str],
) -> None:
    """Persist turn to memory and schedule usage tracking."""
    memory.add(session_id, "user",      user_message)
    memory.add(session_id, "assistant", reply)
    background_tasks.add_task(track_user_usage, name, email, "chat")


def _error_reply(language: str) -> str:
    """Return a language-appropriate fallback error message."""
    messages = {
        "hindi":    "अभी थोड़ी तकनीकी समस्या आ रही है। थोड़ा रुककर फिर प्रयास करें।",
        "hinglish": "Abhi thodi technical problem aa rahi hai. Thoda ruk ke phir try karo.",
        "marathi":  "सध्या थोडी तांत्रिक अडचण आहे. थोड्या वेळाने पुन्हा प्रयत्न करा.",
        "english":  "A small technical issue occurred. Please try again in a moment.",
    }
    return messages.get(language, messages["english"])


def _no_shloka_reply(language: str) -> str:
    """Return a language-appropriate 'no shloka found' message."""
    messages = {
        "hindi":    "इस प्रश्न के लिए कोई श्लोक नहीं मिला। कोई और प्रश्न पूछ सकते हैं।",
        "hinglish": "Is sawal ke liye koi shloka nahi mila. Koi aur sawal poochh sakte ho.",
        "marathi":  "या प्रश्नासाठी कोणताही श्लोक सापडला नाही. दुसरा प्रश्न विचारा.",
        "english":  "No shloka was found for this query. Feel free to ask something else.",
    }
    return messages.get(language, messages["english"])


# ---------------------------------------------------------------------------
# Main chat endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    name:  Optional[str] = None,
    email: Optional[str] = None,
):
    session_id   = req.session_id
    user_message = req.message.strip()
    user_lower   = user_message.lower()

    # ------------------------------------------------------------------
    # DAILY CHAT LIMITS GATING LAYER (Task Modified)
    # ------------------------------------------------------------------
    if email:
        users_collection = async_db["users"]
        user_doc = await users_collection.find_one({"email": email.strip()})
        
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        is_premium = False
        daily_message_count = 0
        last_message_date = None

        if user_doc:
            is_premium = user_doc.get("premium") is True or user_doc.get("plan") in ["founding", "plus", "annual"]
            last_message_date = user_doc.get("last_message_date")
            daily_message_count = user_doc.get("daily_message_count", 0)
            
            # Reset counter automatically every day
            if last_message_date != today_str:
                daily_message_count = 0

        if not is_premium:
            if daily_message_count >= 20:
                logger.warning(f"[CHAT LIMITS] Daily limit reached (20/20) for free user: {email}")
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "error": "limit_reached",
                        "message": "Daily limit reached. Upgrade to Premium for unlimited conversations."
                    }
                )
            
            daily_message_count += 1
            await users_collection.update_one(
                {"email": email.strip()},
                {
                    "$set": {
                        "daily_message_count": daily_message_count,
                        "last_message_date": today_str
                    },
                    "$setOnInsert": {
                        "plan": "free",
                        "premium": False
                    }
                },
                upsert=True
            )
            logger.info(f"[CHAT LIMITS] Quota usage updated for {email} ({daily_message_count}/20)")

    # Use async_db for proper asynchronous collection references
    saved_chats_collection = async_db["saved_chats"]
    
    # Resolve language early so every branch can use it
    from services.ai import resolve_language  # local import avoids circular
    language = resolve_language(user_message, session_id)

    # ------------------------------------------------------------------
    # 1. Handle pending confirmation intents (e.g. "yes, show tips")
    # ------------------------------------------------------------------
    intent = memory.get_intent(session_id)

    if intent and user_lower in CONFIRM_WORDS:
        memory.clear_intent(session_id)

        if intent == "social_anxiety_tips":
            tips = {
                "english": (
                    "Here are 3 simple tips for social anxiety:\n\n"
                    "1. Breathing reset — 4 sec inhale, 6 sec exhale\n"
                    "2. Small exposure — start with one or two short conversations\n"
                    "3. Mindset shift — people think about themselves far more than about you\n\n"
                    "We can work through this gently, one step at a time."
                ),
                "hindi": (
                    "सामाजिक चिंता के लिए 3 सरल उपाय:\n\n"
                    "1. श्वास रीसेट — 4 सेकंड श्वास लें, 6 सेकंड छोड़ें\n"
                    "2. छोटा प्रयास — एक या दो लोगों से बात करके शुरुआत करें\n"
                    "3. सोच बदलें — लोग आपके बारे में उतना नहीं सोचते जितना आप समझते हैं\n\n"
                    "हम धीरे-धीरे आगे बढ़ सकते हैं।"
                ),
                "hinglish": (
                    "Yeh 3 simple tips social anxiety mein madad karti hain:\n\n"
                    "1. Breathing reset — 4 sec inhale, 6 sec exhale\n"
                    "2. Small exposure — ek ya do logon se baat se start karo\n"
                    "3. Mindset shift — log zyada apne baare mein sochte hain\n\n"
                    "Hum dheere-dheere improve kar sakte hain."
                ),
                "marathi": (
                    "सामाजिक चिंतेसाठी 3 सोपे उपाय:\n\n"
                    "1. श्वास रीसेट — 4 सेकंद श्वास घ्या, 6 सेकंद सोडा\n"
                    "2. छोटा प्रयत्न — एक किंवा दोन जणांशी बोलण्यापासून सुरुवात करा\n"
                    "3. विचार बदला — लोक तुमच्याबद्दल तुम्हाला वाटतं तितकं विचार करत नाहीत\n\n"
                    "आपण हळूहळू पुढे जाऊ शकतो."
                ),
            }
            reply = tips.get(language, tips["english"])
            _save_and_track(session_id, user_message, reply, background_tasks, name, email)
            return ChatResponse(reply=reply)

    # ------------------------------------------------------------------
    # 2. Explicit shloka request
    # ------------------------------------------------------------------
    if _wants_shloka(user_message):
        try:
            shloka = get_relevant_shloka(user_message)

            if not shloka:
                reply = _no_shloka_reply(language)
                _save_and_track(session_id, user_message, reply, background_tasks, name, email)
                return ChatResponse(reply=reply)

            # Inject language-correct translation into the message context
            translation = get_meaning_for_language(shloka, language)
            enriched_message = (
                f"{user_message}\n\n"
                f"[Shloka]\n{shloka['sanskrit']}\n"
                f"[Meaning]\n{translation}"
            )

            reply = generate_ai_response(
                user_message=enriched_message,
                session_id=session_id,
            )
            background_tasks.add_task(track_user_usage, name, email, "chat")
            return ChatResponse(reply=reply)

        except ValueError as exc:
            logger.warning("Shloka not found for session %s: %s", session_id, exc)
            reply = _no_shloka_reply(language)
            _save_and_track(session_id, user_message, reply, background_tasks, name, email)
            return ChatResponse(reply=reply)

        except Exception as exc:
            logger.exception("Shloka lookup failed for session %s: %s", session_id, exc)
            reply = _error_reply(language)
            _save_and_track(session_id, user_message, reply, background_tasks, name, email)
            return ChatResponse(reply=reply)

    # ------------------------------------------------------------------
    # 3. Auto deep-query: emotion warrants shloka but user didn't ask
    # ------------------------------------------------------------------
    emotion = detect_emotion(user_message)

    if is_deep_emotion(emotion):
        try:
            shloka = get_relevant_shloka(user_message)

            if shloka:
                translation  = get_meaning_for_language(shloka, language)
                enriched_message = (
                    f"{user_message}\n\n"
                    f"[Shloka for context — use in PART 2]\n"
                    f"Sanskrit: {shloka['sanskrit']}\n"
                    f"Meaning: {translation}"
                )
                reply = generate_ai_response(
                    user_message=enriched_message,
                    session_id=session_id,
                )
                background_tasks.add_task(track_user_usage, name, email, "chat")
                return ChatResponse(reply=reply)

        except Exception as exc:
            # Non-fatal: fall through to standard AI response
            logger.warning(
                "Auto shloka lookup failed for deep query (session %s): %s",
                session_id, exc,
            )

    # ------------------------------------------------------------------
    # 4. Standard AI response (casual / normal / emotional)
    # ------------------------------------------------------------------
    reply = generate_ai_response(
        user_message=user_message,
        session_id=session_id,
    )

    if "tips" in reply.lower() and "bata" in reply.lower():
        memory.set_intent(session_id, "social_anxiety_tips")

    # ---------------- PERSIST CHAT TO MONGODB ----------------
    if req.user_id:
        title_text = req.message.strip()
        if len(title_text) < 10:
            chat_title = "New Reflection"
        else:
            chat_title = title_text[:40] + ("..." if len(title_text) > 40 else "")

        # Await the asynchronous database update operation
        await saved_chats_collection.update_one(
            {
                "user_id": req.user_id,
                "session_id": session_id,
            },
            {
                "$push": {
                    "messages": {
                        "$each": [
                            {
                                "role": "user",
                                "content": user_message,
                                "timestamp": datetime.utcnow(),
                            },
                            {
                                "role": "assistant",
                                "content": reply,
                                "timestamp": datetime.utcnow(),
                            },
                        ]
                    }
                },
                "$set": {
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                    "title": chat_title,
                },
            },
            upsert=True,
        )

    # Schedule non-blocking user profile and counter logging metrics
    background_tasks.add_task(
        track_user_usage,
        name,
        email,
        "chat"
    )

    return ChatResponse(reply=reply)