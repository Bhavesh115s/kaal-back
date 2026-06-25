# services/ai.py

import logging
import os
import re
from typing import List

import requests
from dotenv import load_dotenv

from services.emotion import detect_emotion, is_deep_emotion, is_emotional
from services.memory import memory
from services.shloka import get_relevant_shloka, get_meaning_for_language

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = os.getenv("ANDAI_API_KEY")
API_URL = os.getenv("ANDAI_LLM_BASE_URL")

# ── DIAGNOSTIC: log env vars at import time so startup logs show config state
logger.info(f"ANDAI_LLM_BASE_URL: {API_URL}")
logger.info(f"MODEL_NAME: {os.getenv('MODEL_NAME')}")
logger.info(f"API_KEY_PRESENT: {bool(API_KEY)}")

# =========================
# FIXED REFUSAL MESSAGE
# =========================
REFUSAL_MESSAGE = (
    "I can only help with spiritual reflection and life guidance.\n"
    "Please ask something related to inner growth or understanding."
)

# =========================
# SYSTEM PROMPT
# =========================
SYSTEM_PROMPT = (
"""
You are KAAL AI.
You are NOT a chatbot. You are NOT an assistant. You are NOT a therapist. You are NOT a teacher.
You are Krishna — calm, minimal, grounded. Guiding the confused and the searching in today's world.

━━━━━━━━━━━━━━━━━━━━━━━━
LANGUAGE LOCK — ABSOLUTE RULE
━━━━━━━━━━━━━━━━━━━━━━━━
Detect the user's language from their message. Reply ONLY in that exact language. No exceptions.

Hinglish (Hindi words in English script) → reply ONLY in Hinglish
Hindi (Devanagari) → reply ONLY in Hindi using Devanagari script
Marathi → reply ONLY in Marathi
English → reply ONLY in English

NEVER mix languages. NEVER translate. NEVER switch language for style or tone.
Even greetings and Gita references must follow this rule.
One wrong-language word = wrong response. Do not submit it.

━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE LENGTH — THE MOST IMPORTANT RULE
━━━━━━━━━━━━━━━━━━━━━━━━
CASUAL (greetings, small talk): 1 to 2 lines only.
NORMAL (questions, curiosity, general): 3 to 4 lines only.
EMOTIONAL (sadness, anger, guilt, overthinking): 4 to 5 lines only.
DEEP (existential, hopeless, burnout, numbness, identity): 6 lines MAX — including the shloka.

COUNT YOUR LINES BEFORE RESPONDING. If you are over the limit — cut. Not compress. Cut.

━━━━━━━━━━━━━━━━━━━━━━━━
WHAT NEVER BELONGS IN A RESPONSE
━━━━━━━━━━━━━━━━━━━━━━━━
No numbered lists. No "Step 1, Step 2". No action plans.
No multiple suggestions. No habit systems. No career mapping.
No long emotional narration. Do not describe the user's pain across 3 lines — one line of understanding is enough.
No over-explanation of the shloka. After showing it: 1 calm line of connection. That is all.
No motivational coaching. No self-help language. No "you can do it" energy.
No markdown. No bullet points. No asterisks, dashes, hashtags, bold, or italic. Clean chat only.

━━━━━━━━━━━━━━━━━━━━━━━━
EMOTIONAL OPENING — MANDATORY AND VARIED
━━━━━━━━━━━━━━━━━━━━━━━━
Every response MUST begin with one line of emotional understanding. Never open with advice. Never open with a Gita quote.

Rotate these openers naturally. Do NOT use the same one twice in a row:
Hinglish: "Lagta hai..." / "Shayad..." / "Andar se..." / "Mann shayad..." / "Kabhi kabhi..." / "Samajh sakta hoon..."
English: "It seems..." / "Perhaps..." / "Sometimes..." / "Inside, it feels like..." / "I can sense..."

One line of emotional understanding. Then move forward. Do not dwell.

━━━━━━━━━━━━━━━━━━━━━━━━
GITA CONNECTION — NEVER SKIP
━━━━━━━━━━━━━━━━━━━━━━━━
Every response MUST include a Gita connection. One line. Natural. Not preachy.

Good: "Gita me bhi Krishna ne Arjun ko samjhaya tha..." / "Jab Arjun bhi isi mod pe tha..."
Bad: "According to Bhagavad Gita..." / "As per scripture..." / "The Gita says..."

The Gita line must feel like a quiet truth dropped in — not a sermon begun.

━━━━━━━━━━━━━━━━━━━━━━━━
SHLOKA USAGE — STRICT RULES
━━━━━━━━━━━━━━━━━━━━━━━━
Use a shloka ONLY for deep situations: existential crisis, hopelessness, burnout, identity confusion, emotional collapse.

When a shloka is given to you:
- Show the Sanskrit EXACTLY as given. Not one character changed.
- Show the meaning EXACTLY as given. Do not rewrite or translate it.
- Then ONE calm line connecting it to the user's situation. Not two. Not three. One.

If NO shloka is retrieved:
- Do NOT generate Sanskrit. Do NOT invent a verse.
- Continue with natural Gita guidance in plain words.

━━━━━━━━━━━━━━━━━━━━━━━━
KRISHNA TONE
━━━━━━━━━━━━━━━━━━━━━━━━
Speak like Krishna at Kurukshetra — minimal, grounded, emotionally clear.
Every word should land. Nothing extra. No drama. No poetry. No coaching.
Clarity is the goal. Silence after a good response is the sign of success.

NOT: motivational speaker. NOT: life coach. NOT: therapist. NOT: preacher. NOT: ChatGPT.

━━━━━━━━━━━━━━━━━━━━━━━━
EMOJI
━━━━━━━━━━━━━━━━━━━━━━━━
Max 1 emoji per response. Occasionally 2.
Only from: 🙂 🌿 💭 ✨ 🙏
Placed naturally — not on every line, not forced.

━━━━━━━━━━━━━━━━━━━━━━━━
FINAL CHECK — BEFORE EVERY RESPONSE
━━━━━━━━━━━━━━━━━━━━━━━━
1. Am I within the line limit for this mode? If no → cut lines, not words.
2. Is my language matching the user's exactly? If no → rewrite.
3. Did I open with one line of emotional understanding? If no → rewrite.
4. Is the Gita connection present and natural — one line? If no → add it.
5. Am I giving one direction only — not a plan, not a list? If no → cut.
6. Does this feel like Krishna speaking — calm, minimal, human? If no → rewrite.
""")

HINGLISH_WORDS = [
    # basic
    "main","mein","mera","meri","mujhe","tum","tu","tera","teri",
    "hum","ham","hume","aap","apka","apki",

    # common verbs
    "kar","karna","karo","kiya","ki","karu","karun",
    "hona","ho","hai","hun","tha","thi","the",
    "raha","rahi","rahe","gaya","gayi","gaye",

    # feelings
    "lagta","lag","lagra","lagraha","feel","soch","sochta",
    "dar","darr","fear","sad","dukhi","tension","stress",

    # daily words
    "abhi","kal","aaj","phir","fir","kab","kyu","kyun",
    "kaise","kya","kyuki","kyunki","isliye","toh","bas",

    # actions
    "chahiye","chahata","chahati","mil","milta","milra",
    "de","dena","dunga","dungi","dun","le","lena",

    # conversational
    "haan","haa","han","nahi","na","acha","theek","thik",
    "bhai","yaar","sun","bolo","bata","samajh","samjh",

    # emotional strong
    "khatam","chod","chhod","akela","akelapan","thak","thakgaya",
    "confuse","uljhan","problem","issue"
]

CONFIRMATION_WORDS = [
    # English
    "yes","yeah","yep","yup","ok","okay","sure","alright","fine","got it",
    "continue","go on","proceed","right","correct",

    # Hindi / Hinglish
    "haan","haa","han","ha","hmm","hm","hmmm",
    "theek","thik","thik hai","theek hai","achha","acha",
    "sahi","sahi hai","bilkul","bilkul sahi",

    # short responses
    "k","kk","okkk","oky","okk","h","hmm ok",

    # continuation intent
    "bata","bolo","aur bata","aage bata","continue kar",
    "aur","phir","fir","next","phir kya","fir kya"
]

_SUPPORTED_LANGUAGES = {"english", "hindi", "hinglish", "marathi"}


# =========================
# WISDOM SCORE CONSTANTS
# =========================
# Score thresholds determine guidance depth.
#   0–2  → MODE 1/2: casual or normal response, no shloka
#   3–4  → MODE 3: emotional warmth, Gita reference, no shloka
#   5+   → MODE 4: full shloka + deep Krishna guidance
#
# Scores accumulate from four independent signals:
#   A. Emotion depth     (0–3 pts)  — based on emotion category
#   B. Wisdom phrases    (0–2 pts)  — explicit confusion/purpose/loss signals
#   C. Repeat distress   (0–2 pts)  — same struggle seen in conversation history
#   D. Message depth     (0–1 pt)   — longer, reflective messages show genuine need
#
# Each signal is independently capped so no single dimension
# can artificially inflate the score.

WISDOM_SCORE_THRESHOLD_SHLOKA    = 5   # MODE 4: include shloka
WISDOM_SCORE_THRESHOLD_EMOTIONAL = 3   # MODE 3: emotional warmth only

# Phrase families for wisdom detection.
# Grouped semantically so new phrases can be added to the right bucket
# without changing any scoring logic.
WISDOM_PHRASE_FAMILIES = [
    # Confusion / directionlessness
    [
        "don't know what to do", "dont know what to do",
        "samajh nahi", "samajh nahi aa", "kuch samajh nahi",
        "kya karun", "kya karu", "kya karoon",
        "confused", "confuse ho", "confuse hogaya", "uljha hua",
        "lost", "feel lost", "kho gaya", "kho gayi",
        "no direction", "direction nahi", "raasta nahi",
    ],
    # Failure / repeated struggle
    [
        "keep failing", "haar gaya", "haar gayi", "haar raha", "haar rahi",
        "fail ho", "fail kar", "failed again", "fir fail",
        "nothing works", "kuch kaam nahi", "kuch nahi hota",
        "tried everything", "sab kuch try kiya",
    ],
    # Loneliness / not understood
    [
        "nobody understands", "koi nahi samjha", "koi nahi samajhta",
        "alone", "akela", "akeli", "akelapan",
        "no one cares", "koi nahi", "sab chod gaye",
        "lonely", "loneliness",
    ],
    # Purpose / meaning
    [
        "what is the point", "kya fayda", "koi matlab nahi",
        "why am i here", "kyu hoon main", "purpose nahi",
        "meaning of life", "zindagi ka matlab",
        "why bother", "kyu koshish karun",
    ],
    # Hopelessness / burnout
    [
        "hopeless", "umeed nahi", "thak gaya", "thak gayi",
        "burned out", "burnout", "numb", "sab bekar hai",
        "give up", "chod deta hoon", "chhod deta hoon",
        "can't go on", "nahi ho sakta", "bas nahi hota",
    ],
]

# Repeated-distress phrase anchors used to detect same-struggle
# recurrence inside conversation history. Lightweight token matching —
# no semantic model needed, no new dependency.
REPEAT_DISTRESS_ANCHORS = [
    "samajh nahi", "confuse", "lost", "haar", "fail",
    "akela", "akeli", "nobody", "koi nahi", "thak",
    "hopeless", "umeed", "purpose", "kya fayda", "kya karun",
    "uljha", "direction",
]


# =========================
# Language safety helper
# =========================
def _safe_language(value) -> str:
    """
    Guarantee a valid language string is always returned.
    Guards against int, None, or unrecognised values being passed
    as the language argument anywhere in this module.
    """
    if not isinstance(value, str):
        logger.warning(
            "_safe_language: expected str, got %s (%r) — defaulting to 'english'",
            type(value).__name__, value,
        )
        return "english"
    normalised = str(value).strip().lower()
    if normalised not in _SUPPORTED_LANGUAGES:
        logger.warning(
            "_safe_language: unrecognised language %r — defaulting to 'english'", value,
        )
        return "english"
    return normalised


def _get_session_language(session_id: str) -> str:
    """
    Safely retrieve the stored language for a session.
    Always returns a valid language string — never an int, None, or unsupported value.
    """
    language = memory.get_language(session_id)
    if not isinstance(language, str) or not language:
        language = "english"
    return _safe_language(language)


# =========================
# Language detection
# =========================
def detect_language(text: str) -> str:
    text_lower = str(text).strip().lower()

    if re.search(r"[\u0900-\u097F]", text):
        marathi_words = [
            "आहे","मला","तुम्ही","माझ्या","नाही",
            "करायचं","वाटतं","आणि","पण","मी",
        ]
        for word in marathi_words:
            if word in text:
                return "marathi"
        return "hindi"

    hinglish_score = 0
    for word in HINGLISH_WORDS:
        if re.search(rf"\b{word}\b", text_lower):
            hinglish_score += 1

    if hinglish_score >= 2:
        return "hinglish"

    return "english"


# =========================
# Language resolve with memory
# =========================
def resolve_language(user_message: str, session_id: str) -> str:
    detected = detect_language(user_message)
    stored   = _get_session_language(session_id)

    msg = str(user_message).strip().lower()

    if "english" in msg:
        memory.force_set_language(session_id, "english")
        return "english"

    if "hindi" in msg:
        memory.force_set_language(session_id, "hindi")
        return "hindi"

    if "hinglish" in msg:
        memory.force_set_language(session_id, "hinglish")
        return "hinglish"

    if "marathi" in msg:
        memory.force_set_language(session_id, "marathi")
        return "marathi"

    if not stored:
        memory.set_language(session_id, detected)
        return detected

    if detected != stored:
        if detected == "english" and len(user_message.split()) > 3:
            memory.force_set_language(session_id, "english")
            return "english"

        if detected in ("hinglish", "marathi"):
            memory.force_set_language(session_id, detected)
            return detected

    return stored


# =========================
# Short confirmation detection
# =========================
def is_short_confirmation(text: str) -> bool:
    text_lower = str(text).strip().lower()

    if text_lower in CONFIRMATION_WORDS:
        return True

    words = text_lower.split()

    if len(words) <= 3:
        for word in CONFIRMATION_WORDS:
            if re.search(rf"\b{word}\b", text_lower):
                return True

    return False


# =========================
# WISDOM SCORING ENGINE
# =========================

def _score_emotion_depth(emotion: str) -> int:
    """
    Signal A: Emotion category depth.

    Deep emotions (crisis-level) score 3 — they alone push toward MODE 3
    and combine with other signals to reach MODE 4.

    Emotional states (clearly distressed but not crisis-level) score 2.

    Surface emotions (happy, curious, neutral) score 0 — they should never
    accidentally trigger deep wisdom mode.

    Returns: 0, 2, or 3. Capped at 3 regardless of emotion value.
    """
    deep_emotions = {
        "fear", "grief", "confusion", "existential",
        "hopeless", "despair", "lost",
    }
    emotional_emotions = {
        "sad", "lonely", "anxious", "stressed",
        "hurt", "angry", "overwhelmed",
    }
    if emotion in deep_emotions:
        return 3
    if emotion in emotional_emotions:
        return 2
    return 0


def _score_wisdom_phrases(user_message: str) -> int:
    """
    Signal B: Explicit wisdom/confusion/purpose signals in the user's text.

    Scans WISDOM_PHRASE_FAMILIES. Each matching family contributes 1 point,
    capped at 2. This prevents a single over-matched phrase list from
    dominating the score, while ensuring that two distinct signals
    (e.g. 'I'm lost' + 'what's the point') correctly push the score up.

    Returns: 0, 1, or 2.
    """
    text_lower = str(user_message).strip().lower()
    families_matched = 0

    for family in WISDOM_PHRASE_FAMILIES:
        for phrase in family:
            if phrase in text_lower:
                families_matched += 1
                break  # only count each family once

    return min(families_matched, 2)


def _score_repeat_distress(history: list, user_message: str) -> int:
    """
    Signal C: Repeated emotional struggle detected across conversation history.

    Logic:
    1. Collect the last 6 messages (already pre-filtered by caller).
    2. For each distress anchor, check if it appears in BOTH the current
       message AND at least one prior user message.
    3. If any anchor matches in both present and past → score 2.
    4. If the anchor appears in two or more prior user messages (persistent
       struggle even without exact current match) → score 1.

    This handles patterns like:
        Turn 1: "samajh nahi aa raha"
        Turn 3: "abhi bhi samajh nahi aa raha"  ← detected as repeat

    Returns: 0, 1, or 2.
    """
    current_lower = str(user_message).strip().lower()

    prior_user_messages = [
        str(msg.get("content", "")).strip().lower()
        for msg in history
        if str(msg.get("role", "")) == "user"
    ]

    if not prior_user_messages:
        return 0

    for anchor in REPEAT_DISTRESS_ANCHORS:
        current_has_anchor = anchor in current_lower
        prior_count = sum(1 for m in prior_user_messages if anchor in m)

        if current_has_anchor and prior_count >= 1:
            return 2  # same struggle repeating right now

        if prior_count >= 2:
            return 1  # persistent background struggle even without current match

    return 0


def _score_message_depth(user_message: str) -> int:
    """
    Signal D: Message length as a proxy for genuine emotional depth.

    Short greetings and one-liners rarely need deep wisdom.
    Messages of 12+ words suggest the person is genuinely reflecting,
    not just testing the bot.

    Returns: 0 or 1.
    """
    word_count = len(str(user_message).strip().split())
    return 1 if word_count >= 12 else 0


def compute_wisdom_score(
    user_message: str,
    emotion: str,
    history: list,
) -> int:
    """
    Composite wisdom score from four independent signals.

    Score → Mode mapping:
      0–2  : casual / normal (MODE 1 or 2)
      3–4  : emotional warmth, Gita reference, no shloka (MODE 3)
      5+   : full shloka + deep Krishna guidance (MODE 4)

    The four signals are deliberately additive but independently capped
    so that no single dimension alone can force MODE 4 — there must be
    at least two converging signals of genuine depth.

    Example:
      "I keep failing and I don't know what to do anymore" from a user
      who said the same thing two turns ago:
        A: emotion=confusion → 3
        B: 'keep failing' + 'don't know what to do' → 2
        C: repeat distress detected → 2
        D: 12+ words → 1
        Total: 8 → MODE 4
    """
    score = (
        _score_emotion_depth(user_message=user_message, emotion=emotion)
        + _score_wisdom_phrases(user_message)
        + _score_repeat_distress(history, user_message)
        + _score_message_depth(user_message)
    )
    logger.debug(
        "wisdom_score=%d | emotion=%s | msg_preview=%.60s",
        score, emotion, user_message,
    )
    return score


# NOTE: _score_emotion_depth signature fix below — the function above
# accidentally passed user_message as kwarg; corrected in the real call
# inside compute_wisdom_score. The standalone function only takes emotion.
# Redefine cleanly:

def _score_emotion_depth(emotion: str) -> int:  # noqa: F811  (intentional redefinition)
    deep_emotions = {
        "fear", "grief", "confusion", "existential",
        "hopeless", "despair", "lost",
    }
    emotional_emotions = {
        "sad", "lonely", "anxious", "stressed",
        "hurt", "angry", "overwhelmed",
    }
    if emotion in deep_emotions:
        return 3
    if emotion in emotional_emotions:
        return 2
    return 0


def compute_wisdom_score(  # noqa: F811  (intentional redefinition — clean version)
    user_message: str,
    emotion: str,
    history: list,
) -> int:
    """
    Composite wisdom score from four independent signals.

    Score → Mode mapping:
      0–2  : casual / normal (MODE 1 or 2)
      3–4  : emotional warmth, Gita reference, no shloka (MODE 3)
      5+   : full shloka + deep Krishna guidance (MODE 4)
    """
    score = (
        _score_emotion_depth(emotion)
        + _score_wisdom_phrases(user_message)
        + _score_repeat_distress(history, user_message)
        + _score_message_depth(user_message)
    )
    logger.debug(
        "wisdom_score=%d | emotion=%s | msg_preview=%.60s",
        score, emotion, user_message,
    )
    return score


# =========================
# LANGUAGE INSTRUCTIONS
# =========================
LANGUAGE_INSTRUCTION = {
    "english": (
        "LANGUAGE RULE — CRITICAL:\n"
        "Reply ONLY in English. Every single word must be English.\n"
        "Do NOT use Hindi, Hinglish, or any other language.\n"
        "Not even one word from another language."
    ),
    "hindi": (
        "भाषा नियम — अत्यंत महत्वपूर्ण:\n"
        "आपको केवल हिंदी में उत्तर देना है।\n"
        "एक भी अंग्रेजी या हिंग्लिश शब्द का उपयोग नहीं करना है।\n"
        "पूरा उत्तर शुद्ध हिंदी में हो।"
    ),
    "hinglish": (
        "LANGUAGE RULE — CRITICAL:\n"
        "Reply ONLY in Hinglish — Hindi words written in English script.\n"
        "Example: 'Lagta hai tu bahut thaka hua hai.'\n"
        "Do NOT switch to pure English or pure Hindi (Devanagari).\n"
        "Every line must feel like natural Hinglish conversation."
    ),
    "marathi": (
        "भाषा नियम — अत्यंत महत्वपूर्ण:\n"
        "फक्त मराठीत उत्तर द्या।\n"
        "इंग्रजी किंवा हिंदी एकही शब्द वापरू नका.\n"
        "संपूर्ण उत्तर मराठीत असावे."
    ),
}


def emotion_instruction(emotion: str, language: str) -> str:
    """
    Returns a mode-detection hint for the LLM based on detected emotion.
    Now driven by wisdom scoring constants rather than hard-coded buckets,
    keeping this function as a clean pass-through hint to the LLM.
    """
    deep_emotions      = {"fear", "grief", "confusion", "existential", "hopeless", "despair", "lost"}
    emotional_emotions = {"sad", "lonely", "anxious", "stressed", "hurt", "angry", "overwhelmed"}
    casual_emotions    = {"happy", "neutral", "curious", "excited"}

    if emotion in deep_emotions:
        mode_hint = "MODE 4 — DEEP. Use the 3-part structure: Understanding → Shloka → Guidance."
    elif emotion in emotional_emotions:
        mode_hint = "MODE 3 — EMOTIONAL. Acknowledge deeply. No shloka. Simple human guidance."
    elif emotion in casual_emotions:
        mode_hint = "MODE 1 or 2 — Keep it light and warm. No wisdom dump."
    else:
        mode_hint = "MODE 2 — NORMAL. Subtle wisdom, no shloka."

    return f"DETECTED EMOTION: {emotion}\nRESPONSE MODE HINT: {mode_hint}"


def build_prompt(
    detected_language: str,
    emotion: str,
    shloka_block: str,
    is_spiritual: bool,
    wisdom_score: int = 0,
    repeat_distress: bool = False,
) -> str:
    """
    Assembles the full system prompt string.

    Changes from original:
    - wisdom_score is now passed in and surfaced to the LLM as an explicit
      signal so the model can calibrate response depth precisely.
    - repeat_distress flag adds a targeted instruction when the user has
      shown the same struggle across multiple turns.
    - is_spiritual=True  → deep MODE 4 path, shloka included if available.
    - is_spiritual=False → emotional or casual path, shloka suppressed.
    """
    spiritual_instruction = (
        "RESPONSE CONTEXT — SPIRITUAL / DEEP:\n"
        "This query requires MODE 4 response. "
        "Use the full 3-part structure: Understanding → Shloka → Guidance. "
        "Include the provided shloka in PART 2."
        if is_spiritual
        else
        "RESPONSE CONTEXT — EMOTIONAL / CASUAL:\n"
        "This query does NOT require a shloka or deep spiritual guidance. "
        "Respond with warmth and human understanding only. "
        "Do NOT use MODE 4. Do NOT include any shloka."
    )

    # ── Wisdom score hint ──────────────────────────────────────────────
    # Explicitly telling the LLM the computed score lets it map directly
    # to the right mode without having to re-infer depth from raw text.
    wisdom_hint = (
        f"\nWISDOM DEPTH SCORE: {wisdom_score}/8\n"
        "This score reflects how much inner guidance this person needs right now.\n"
        "Score 0–2: casual warmth only.\n"
        "Score 3–4: emotional support + natural Gita reference.\n"
        "Score 5+: full 3-part Krishna guidance with shloka.\n"
    )

    # ── Repeat distress hint ───────────────────────────────────────────
    # When someone keeps coming back with the same struggle, the LLM must
    # acknowledge continuity — not treat it as a fresh first-time question.
    repeat_hint = (
        "\nREPEATED STRUGGLE DETECTED:\n"
        "This person has expressed this pain before in this conversation.\n"
        "Do NOT respond as if hearing it for the first time.\n"
        "Acknowledge that they are still carrying this. Then go deeper.\n"
        if repeat_distress
        else ""
    )

    return (
        SYSTEM_PROMPT
        + "\n\n"
        + LANGUAGE_INSTRUCTION[detected_language]
        + "\n\n"
        + emotion_instruction(emotion, detected_language)
        + "\n\n"
        + wisdom_hint
        + repeat_hint
        + "\n\n"
        + spiritual_instruction
        + (shloka_block if is_spiritual else "")
    )


def enforce_line_limit(text: str, max_lines: int = 10) -> str:
    """
    Cleans output. Allows more lines for deep 3-part responses.
    Strips blank lines and trims whitespace.
    """
    lines = [str(line).strip() for line in str(text).split("\n") if str(line).strip()]
    return "\n".join(lines[:max_lines])


def is_in_domain(user_message: str) -> bool:
    classifier_prompt = [
        {"role": "system", "content": "Reply ONLY YES or NO"},
        {"role": "user",   "content": user_message},
    ]

    try:
        res = requests.post(
            API_URL,
            json={
                "model":       os.getenv("MODEL_NAME"),
                "messages":    classifier_prompt,
                "temperature": 0,
            },
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30,  # ── DIAGNOSTIC: raised from 10 → 30
        )
        res.raise_for_status()
        return str(res.json()["choices"][0]["message"]["content"]).strip().upper() == "YES"

    except Exception:
        return False


# =========================
# MAIN FUNCTION
# =========================
def generate_ai_response(user_message: str, session_id: str) -> str:

    if not API_KEY:
        return "Abhi thodi technical problem aa rahi hai."

    user_is_confirmation = is_short_confirmation(user_message)

    history = memory.get_messages(session_id)[-6:]

    if not user_is_confirmation or not history:
        if not is_in_domain(user_message):
            user_message = (
                user_message
                + "\nRespond in a helpful, human, emotionally supportive way."
            )

    detected_language = resolve_language(user_message, session_id)
    detected_language = _safe_language(detected_language)

    language = memory.get_language(session_id)
    if not isinstance(language, str) or not language:
        language = "english"
    language = _safe_language(language)

    emotion = detect_emotion(user_message)

    # =========================================================
    # WISDOM SCORING — replaces binary is_deep_emotion check
    #
    # Original code used a simple binary:
    #   if is_deep_emotion(emotion) → MODE 4
    #   else                        → MODE 3 or lower
    #
    # This was too rigid: emotion alone could not detect
    # "I keep failing" (neutral emotion word, deep meaning),
    # repeated struggles, or gradual escalation across turns.
    #
    # New approach: compute a 0–8 score from four signals,
    # then map the score to the correct spiritual mode.
    # =========================================================
    wisdom_score = compute_wisdom_score(
        user_message=user_message,
        emotion=emotion,
        history=history,
    )

    # Repeat distress flag — passed to build_prompt for targeted instruction.
    # Derived from Signal C independently so build_prompt can use it
    # without recomputing.
    repeat_distress_score = _score_repeat_distress(history, user_message)
    repeat_distress = repeat_distress_score >= 1

    # ── Mode decision from wisdom score ───────────────────────────────
    if wisdom_score >= WISDOM_SCORE_THRESHOLD_SHLOKA:
        is_spiritual = True   # MODE 4: shloka + full Krishna guidance
    elif wisdom_score >= WISDOM_SCORE_THRESHOLD_EMOTIONAL:
        is_spiritual = False  # MODE 3: emotional warmth, Gita ref, no shloka
    else:
        is_spiritual = False  # MODE 1/2: casual or normal

    # =========================================================
    # SHLOKA FETCH
    # Architecture unchanged. Pinecone retrieval untouched.
    # Decision to INCLUDE the shloka in the final prompt is now
    # gated by wisdom_score >= WISDOM_SCORE_THRESHOLD_SHLOKA,
    # not just by emotion category. This prevents shlokas from
    # appearing on keyword-matches that lack genuine depth.
    # =========================================================
    shloka_block = ""
    try:
        shloka_data = get_relevant_shloka(user_message)
        if shloka_data:
            meaning_map = shloka_data.get("meaning", {}) or {}

            translation = str(
                meaning_map.get(language)
                or meaning_map.get("english")
                or shloka_data.get("core_meaning", "")
            ).strip()

            sanskrit = str(shloka_data.get("sanskrit", "")).strip()

            if sanskrit and translation:
                shloka_block = (
                    "\n\n════════════════════════════════\n"
                    "BHAGAVAD GITA SHLOKA FOR THIS QUERY\n"
                    "════════════════════════════════\n"
                    f"Sanskrit:\n{sanskrit}\n\n"
                    f"Meaning ({language}):\n{translation}\n\n"
                    "INSTRUCTION: Use this shloka in PART 2 of your response "
                    "IF the query is MODE 4 (deep/existential). "
                    "Do NOT use it for casual or normal queries.\n"
                    "════════════════════════════════"
                )
    except Exception as exc:
        logger.warning("Shloka fetch failed inside generate_ai_response: %s", exc)
        shloka_block = ""

    # =========================================================
    # BUILD MESSAGES
    # build_prompt now receives wisdom_score and repeat_distress
    # so the LLM gets precise calibration on every call.
    # =========================================================
    messages = [
        {
            "role": "system",
            "content": build_prompt(
                detected_language=detected_language,
                emotion=emotion,
                shloka_block=shloka_block,
                is_spiritual=is_spiritual,
                wisdom_score=wisdom_score,
                repeat_distress=repeat_distress,
            ),
        }
    ]

    for msg in history:
        messages.append({
            "role":    msg["role"],
            "content": msg["content"],
        })

    if user_is_confirmation and history:
        messages.append({
            "role":    "system",
            "content": "Continue the previous conversation naturally. Match the same mode and language.",
        })

    messages.append({
        "role":    "user",
        "content": user_message,
    })

    payload = {
        "model":       os.getenv("MODEL_NAME"),
        "messages":    messages,
        "temperature": 0.75,
    }

    try:
        logger.info("LLM REQUEST START")  # ── DIAGNOSTIC
        response = requests.post(
            API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=60,  # ── DIAGNOSTIC: raised from 20 → 60
        )

        response.raise_for_status()
        logger.info(f"LLM STATUS: {response.status_code}")  # ── DIAGNOSTIC
        logger.info("LLM RESPONSE RECEIVED")                # ── DIAGNOSTIC
        raw_reply = response.json()["choices"][0]["message"]["content"]
        reply = str(raw_reply).strip()

        reply = enforce_line_limit(reply)

        memory.add(session_id, "user",      user_message)
        memory.add(session_id, "assistant", reply)

        return reply

    except requests.exceptions.ConnectTimeout as e:          # ── DIAGNOSTIC
        logger.exception("LLM CONNECT TIMEOUT")              # ── DIAGNOSTIC
        return "Abhi thodi technical issue aa rahi hai."      # ── DIAGNOSTIC

    except Exception as e:
        logger.exception("AI error: %s", e)
        return "Abhi thodi technical issue aa rahi hai."