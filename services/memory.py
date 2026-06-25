# services/memory.py

from __future__ import annotations

from collections import defaultdict, deque
from typing import Optional

MAX_MEMORY = 6


class ConversationMemory:
    def __init__(self):
        self.store = defaultdict(lambda: deque(maxlen=MAX_MEMORY))
        self.pending_intent: dict[str, str] = {}
        self.language_preference: dict[str, str] = {}

    # -------------------------
    # Conversation memory
    # -------------------------
    def add(self, session_id: str, role: str, content: str) -> None:
        """
        Add message with duplicate + noise protection
        """
        if not content or not isinstance(content, str) or len(content.strip()) < 2:
            return

        content = str(content).strip()
        history = self.store[session_id]

        # 🔥 prevent duplicate consecutive messages
        if history and history[-1]["content"] == content:
            return

        # 🔥 prevent repeat spam (last 2 messages)
        for msg in list(history)[-2:]:
            if msg["role"] == role and msg["content"] == content:
                return

        history.append({
            "role": role,
            "content": content
        })

    def get_messages(self, session_id: str):
        """
        Return clean conversation (no duplicates)
        """
        history = list(self.store.get(session_id, []))

        cleaned = []
        seen = set()

        for msg in history:
            content = str(msg["content"]).strip()

            if not content:
                continue

            if content in seen:
                continue

            cleaned.append({
                "role": msg["role"],
                "content": content
            })
            seen.add(content)

        return cleaned

    def get_context(self, session_id: str) -> str:
        """
        Convert history into readable context
        """
        history = self.get_messages(session_id)

        context = ""
        for msg in history:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            context += f"{prefix}: {msg['content']}\n"

        return context.strip()

    # -------------------------
    # Intent handling
    # -------------------------
    def set_intent(self, session_id: str, intent: str) -> None:
        self.pending_intent[session_id] = intent

    def get_intent(self, session_id: str) -> Optional[str]:
        return self.pending_intent.get(session_id)

    def clear_intent(self, session_id: str) -> None:
        self.pending_intent.pop(session_id, None)

    # -------------------------
    # Language preference (SMART LOCK 🔥)
    # -------------------------
    def set_language(self, session_id: str, language: str) -> None:
        """
        Smart language setting:
        - First time → set normally
        - Allow Hinglish ↔ English soft switching
        - Keep Hindi stable unless forced
        """
        if session_id not in self.language_preference:
            self.language_preference[session_id] = language
            return

        current = self.language_preference[session_id]

        # 🔥 allow Hinglish ↔ English flexibility
        if current in ["hinglish", "english"] and language in ["hinglish", "english"]:
            self.language_preference[session_id] = language

        # 🔥 Hindi stays stable unless explicit force
        elif current == "hindi" and language != "hindi":
            return

        else:
            self.language_preference[session_id] = language

    def force_set_language(self, session_id: str, language: str) -> None:
        """
        Force change language when user clearly switches
        """
        self.language_preference[session_id] = language

    def get_language(self, session_id: str) -> str:
        lang = self.language_preference.get(session_id)
        if not isinstance(lang, str) or not lang:
            return "english"
        return lang

    def clear_language(self, session_id: str) -> None:
        self.language_preference.pop(session_id, None)


# Singleton
memory = ConversationMemory()