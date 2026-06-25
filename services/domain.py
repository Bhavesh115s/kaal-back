import re

def is_spiritual_domain(text: str) -> bool:
    text = text.lower().strip()

    # -------------------------
    # Direct allow (greetings)
    # -------------------------
    greetings = [
        "hi", "hello", "hey", "bye", "goodbye",
        "how are you", "what can you do", "thank you"
    ]

    for g in greetings:
        if g in text:
            return True

    # -------------------------
    # Strong spiritual keywords
    # -------------------------
    spiritual_keywords = [
        "life", "death", "soul", "karma", "moksha", "dharma",
        "god", "krishna", "gita", "shloka", "bhagavad",
        "purpose", "meaning", "truth", "attachment",
        "desire", "suffering"
    ]

    # -------------------------
    # Emotional signals (VERY IMPORTANT 🔥)
    # -------------------------
    emotional_keywords = [
        "sad", "depressed", "lonely", "broken",
        "fear", "anxious", "overthinking", "stress",
        "confused", "lost", "empty", "tired",
        "why do i", "i feel", "i don't understand"
    ]

    # -------------------------
    # Match logic
    # -------------------------
    for keyword in spiritual_keywords + emotional_keywords:
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            return True

    # -------------------------
    # Fallback: allow medium-length queries
    # (avoid over-blocking real users)
    # -------------------------
    if len(text.split()) >= 4:
        return True

    return False