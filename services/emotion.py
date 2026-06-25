"""Emotion detection from user message text. Used to tune AI tone (see services.ai)."""

import re


# ---------------------------------------------------------------------------
# Keyword maps
# ---------------------------------------------------------------------------

_GENERAL_PATTERNS = [
    r"\bhi\b", r"\bhello\b", r"\bhey\b", r"\bbye\b", r"\bgoodbye\b",
    r"how\s+are\s+you", r"who\s+are\s+you", r"what\s+can\s+you\s+do",
    r"\bthanks\b", r"\bthank\s+you\s*", r"\bok\b", r"\bshukriya\b",
    r"\bnamaste\b", r"\bnamaskar\b", r"\bsup\b", r"\bwassup\b",
    r"\bkya\s+haal\b", r"\bkaise\s+ho\b", r"\btheek\s+ho\b",
]

_EMOTION_KEYWORDS: dict[str, list[str]] = {
    # ── sadness ────────────────────────────────────────────────────────────
    "sadness": [
        "sad", "depressed", "unhappy", "cry", "crying", "lonely", "broken",
        "pain", "hurt", "heartbreak", "heartbroken", "grieve", "grief",
        "hopeless", "helpless", "tears", "miss", "missing", "numb",
        # hindi / hinglish
        "dukh", "dukhi", "rona", "akela", "akelapan", "udaas", "toota",
        "toot", "dard", "bura", "bura lag",
        # marathi
        "दुःख", "एकटा", "एकटी", "रडणे",
    ],

    # ── anger ──────────────────────────────────────────────────────────────
    "anger": [
        "angry", "mad", "hate", "irritated", "furious", "frustrated",
        "rage", "annoyed", "outraged", "bitter", "resentful",
        # hindi / hinglish
        "gussa", "nafrat", "chidhchidha", "jalana", "krodh",
        # marathi
        "राग", "चिडचिड",
    ],

    # ── fear ───────────────────────────────────────────────────────────────
    "fear": [
        "scared", "fear", "anxious", "worried", "nervous", "panic",
        "terrified", "dread", "phobia", "insecure", "unsafe", "threat",
        "what if", "overthinking",
        # hindi / hinglish
        "dar", "darr", "ghabrana", "chinta", "fikar", "soch soch",
        "sochta rehta", "ghabraya",
        # marathi
        "भीती", "काळजी", "घाबरणे",
    ],

    # ── confusion ──────────────────────────────────────────────────────────
    "confusion": [
        "lost", "confused", "unsure", "doubt", "what to do", "no direction",
        "no purpose", "don't know", "dont know", "can't decide", "cant decide",
        "which way", "crossroads", "stuck", "unclear", "dilemma",
        # hindi / hinglish
        "samajh nahi", "pata nahi", "kya karu", "kya karun", "uljhan",
        "ulajh", "rasta nahi", "direction nahi",
        # marathi
        "काय करावं", "समजत नाही", "गोंधळ",
    ],

    # ── guilt ──────────────────────────────────────────────────────────────
    "guilt": [
        "sorry", "guilty", "regret", "shame", "mistake", "wrong", "apologize",
        "let down", "betrayed", "blunder", "fault", "my fault", "failed",
        # hindi / hinglish
        "galti", "maafi", "sharminda", "pachtawa", "kasoor",
        # marathi
        "चूक", "पश्चाताप", "माफी",
    ],

    # ── joy ────────────────────────────────────────────────────────────────
    "joy": [
        "happy", "joy", "blessed", "grateful", "excited", "peaceful",
        "content", "thrilled", "wonderful", "amazing", "love", "loved",
        "celebrate", "achieved", "success", "proud",
        # hindi / hinglish
        "khush", "khushi", "mast", "mazaa", "maja", "shukar", "shukra",
        "pyaar", "anand",
        # marathi
        "आनंद", "खूश", "छान",
    ],

    # ── existential / deep ─────────────────────────────────────────────────
    "existential": [
        "purpose", "meaning", "why am i", "why do i exist", "life purpose",
        "death", "dying", "afterlife", "soul", "karma", "moksha", "truth",
        "god", "universe", "consciousness", "who am i", "identity",
        "why live", "is life worth", "real self",
        # hindi / hinglish
        "jiwan ka matlab", "maut", "atma", "parmAtma", "sach kya hai",
        "main kaun hoon", "zindagi ka maqsad",
        # marathi
        "जगण्याचा अर्थ", "आत्मा", "मृत्यू",
    ],

    # ── loneliness (separate from sadness for richer mode mapping) ─────────
    "loneliness": [
        "no one understands", "nobody cares", "all alone", "no friends",
        "isolated", "abandoned", "ignored", "invisible", "no support",
        # hindi / hinglish
        "koi nahi", "koi samajhta nahi", "akela hoon", "akelapan",
        # marathi
        "कोणी नाही", "एकटेपण",
    ],

    # ── hopelessness ───────────────────────────────────────────────────────
    "hopeless": [
        "no hope", "give up", "giving up", "pointless", "useless", "worthless",
        "nothing matters", "end it", "can't go on", "cant go on", "no way out",
        # hindi / hinglish
        "koi umeed nahi", "sab khatam", "thak gaya", "thak gayi", "haar gaya",
        "haar gayi", "bas ab nahi",
        # marathi
        "आशा नाही", "थकलो", "थकले",
    ],
}

# Emotions that should trigger the deep 3-part response mode in ai.py
DEEP_EMOTIONS = {"existential", "hopeless", "fear", "confusion", "loneliness"}

# Emotions that should trigger the emotional (mode 3) response
EMOTIONAL_EMOTIONS = {"sadness", "anger", "guilt"}

# Emotions that stay light (mode 1/2)
LIGHT_EMOTIONS = {"joy", "general", "neutral"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_emotion(text: str) -> str:
    """
    Classify a message into one of:
        general | sadness | anger | fear | confusion | guilt | joy |
        existential | loneliness | hopeless | neutral

    Returns
    -------
    str
        Emotion label used by services.ai to select response mode and tone.
    """
    cleaned = text.lower().strip()

    # 1. Greeting / casual — checked first so short messages don't leak
    #    into emotional categories.
    for pattern in _GENERAL_PATTERNS:
        if re.search(pattern, cleaned):
            return "general"

    # 2. Emotion keyword scan — multi-word phrases checked before single words
    #    so "no hope" beats "hope" in a different category.
    scores: dict[str, int] = {emotion: 0 for emotion in _EMOTION_KEYWORDS}

    for emotion, keywords in _EMOTION_KEYWORDS.items():
        for kw in keywords:
            # Use word-boundary search for single-word keywords;
            # plain substring search is fine for multi-word phrases.
            if " " in kw:
                if kw in cleaned:
                    scores[emotion] += 2          # phrase match = stronger signal
            else:
                if re.search(rf"\b{re.escape(kw)}\b", cleaned):
                    scores[emotion] += 1

    best_emotion = max(scores, key=lambda e: scores[e])

    if scores[best_emotion] > 0:
        return best_emotion

    return "neutral"


def is_deep_emotion(emotion: str) -> bool:
    """Return True if the emotion warrants a deep 3-part shloka response."""
    return emotion in DEEP_EMOTIONS


def is_emotional(emotion: str) -> bool:
    """Return True if the emotion warrants an emotional (mode 3) response."""
    return emotion in EMOTIONAL_EMOTIONS


def is_casual(emotion: str) -> bool:
    """Return True if the emotion warrants a light casual (mode 1/2) response."""
    return emotion in LIGHT_EMOTIONS