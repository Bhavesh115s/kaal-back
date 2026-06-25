"""
Shloka retrieval: embed user input via Jina, query Pinecone index,
return best-match metadata (safe + stable version).
"""

import os
import logging
import json
import requests
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

logger = logging.getLogger(__name__)

JINA_API_KEY     = os.getenv("JINA_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME       = os.getenv("PINECONE_INDEX")

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
MIN_INPUT_LENGTH = 3
MIN_SCORE        = 0.3
TOP_K            = 4

# ---------------------------------------------------------------------------
# Pinecone client (module-level, one connection)
# ---------------------------------------------------------------------------
pc    = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_language(language) -> str:
    """
    Guarantee language is always a clean lowercase string.
    Falls back to 'english' for any non-string, empty, or unrecognised value.
    """
    SUPPORTED = {"english", "hindi", "hinglish", "marathi"}

    if not isinstance(language, str):
        logger.warning(
            "_safe_language: received non-string type %s (%r) — defaulting to 'english'",
            type(language).__name__, language,
        )
        return "english"

    normalised = str(language or "").strip().lower()
    if not normalised or normalised not in SUPPORTED:
        logger.warning(
            "_safe_language: unrecognised value %r — defaulting to 'english'", language,
        )
        return "english"

    return normalised


def _get_embedding(user_input: str) -> list[float] | None:
    """Call Jina embeddings API and return the embedding vector, or None."""
    try:
        res = requests.post(
            "https://api.jina.ai/v1/embeddings",
            json={
                "model":      "jina-embeddings-v3",
                "task":       "retrieval.query",
                "dimensions": 1024,
                "input":      [user_input],
            },
            headers={"Authorization": f"Bearer {JINA_API_KEY}"},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()

        if not data.get("data"):
            logger.warning("Jina returned empty data block for input: %.60s", user_input)
            print(f"[SHLOKA DEBUG] ❌ Embedding failed — empty response from Jina")
            return None

        vector = data["data"][0]["embedding"]
        print(f"[SHLOKA DEBUG] ✅ Embedding success — vector length: {len(vector)}")
        return vector

    except requests.exceptions.RequestException as exc:
        logger.exception("Jina API error: %s", exc)
        print(f"[SHLOKA DEBUG] ❌ Jina API exception: {exc}")
        return None


def _query_pinecone(vector: list[float]) -> tuple[dict | None, bool]:
    """
    Query Pinecone and return (best_match, is_confident).

    - Always returns the best available match even when score < MIN_SCORE
      so the caller can use it as a fallback.
    - Returns (None, False) only when Pinecone has zero matches.
    - Never discards a match silently when data exists.
    """
    try:
        result  = index.query(vector=vector, top_k=TOP_K, include_metadata=True)
        matches = result.get("matches", [])

        print(f"[SHLOKA DEBUG] 📦 Pinecone matches count: {len(matches)}")

        if not matches:
            logger.info("Pinecone returned no matches.")
            print(f"[SHLOKA DEBUG] ⚠️  Pinecone returned 0 matches")
            return None, False

        best  = matches[0]
        score = best.get("score", 0)

        print(f"[SHLOKA DEBUG] 🏆 Best match score: {score:.4f}  |  threshold: {MIN_SCORE}")

        if score < MIN_SCORE:
            logger.info(
                "Score %.4f below threshold %.4f — returning as fallback.",
                score, MIN_SCORE,
            )
            print(
                f"[SHLOKA DEBUG] ⚠️  Score below threshold — "
                f"returning best available match as fallback"
            )
            return best, False

        return best, True

    except Exception as exc:
        logger.exception("Pinecone query error: %s", exc)
        print(f"[SHLOKA DEBUG] ❌ Pinecone query exception: {exc}")
        return None, False


def _parse_emotion_map(raw) -> dict:
    """Safely coerce emotion_map metadata field to a plain dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _extract_metadata(metadata: dict, score: float) -> dict | None:
    """
    Pull all fields from a Pinecone metadata blob into a clean return dict.

    Hard minimum: sanskrit must be present.
    All meaning fields fall back gracefully so we never return empty strings
    when any translation variant exists.
    """
    sanskrit     = str(metadata.get("sanskrit")         or "").strip()
    meaning_en   = str(metadata.get("meaning_english")  or "").strip()
    meaning_hi   = str(metadata.get("meaning_hindi")    or "").strip()
    meaning_hl   = str(metadata.get("meaning_hinglish") or "").strip()
    meaning_mr   = str(metadata.get("meaning_marathi")  or "").strip()
    core_meaning = str(metadata.get("core_meaning")     or "").strip()
    use_cases    = metadata.get("use_cases",        [])
    chapter      = str(metadata.get("chapter")          or "").strip()
    verse        = str(metadata.get("verse")            or "").strip()
    emotion_map  = _parse_emotion_map(metadata.get("emotion_map", {}))

    if not sanskrit:
        logger.warning("Shloka metadata missing 'sanskrit' — skipped.")
        print(f"[SHLOKA DEBUG] ❌ Metadata missing sanskrit field — cannot use this match")
        return None

    effective_en = meaning_en or core_meaning or "Seek the truth within."

    print(
        f"[SHLOKA DEBUG] ✅ Metadata extracted — "
        f"chapter: '{chapter}', verse: '{verse}', score: {score:.4f}"
    )

    return {
        "sanskrit": sanskrit,
        "meaning": {
            "english":  effective_en,
            "hindi":    meaning_hi or effective_en,
            "hinglish": meaning_hl or effective_en,
            "marathi":  meaning_mr or effective_en,
        },
        "core_meaning": core_meaning or effective_en,
        "use_cases":    use_cases if isinstance(use_cases, list) else [],
        "emotion_map":  emotion_map,
        "chapter":      chapter,
        "verse":        verse,
        "score":        round(score, 4),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_relevant_shloka(user_input: str) -> dict | None:
    """
    Embed *user_input* with Jina, query Pinecone, return best-match metadata.

    Guarantees
    ----------
    - Never raises.
    - Never returns None when Pinecone has any match (fallback logic ensures this).
    - Returns None only when: input too short, embedding fails, or
      Pinecone returns zero matches.

    Return shape
    ------------
    {
        "sanskrit":     str,
        "meaning":      {"english": str, "hindi": str, "hinglish": str, "marathi": str},
        "core_meaning": str,
        "use_cases":    list[str],
        "emotion_map":  dict,
        "chapter":      str,
        "verse":        str,
        "score":        float,
    }
    """
    print(f"\n[SHLOKA DEBUG] ── New retrieval ───────────────────────────────────")
    print(f"[SHLOKA DEBUG] Input: {user_input[:80]!r}")

    if not user_input or len(str(user_input or "").strip()) < MIN_INPUT_LENGTH:
        print(f"[SHLOKA DEBUG] ⚠️  Input too short — skipping")
        return None

    vector = _get_embedding(str(user_input or "").strip())
    if vector is None:
        return None

    best, is_confident = _query_pinecone(vector)

    if best is None:
        print(f"[SHLOKA DEBUG] ⚠️  No Pinecone match at all — returning None")
        return None

    result = _extract_metadata(
        metadata=best.get("metadata", {}),
        score=best.get("score", 0),
    )

    if result:
        label = "confident" if is_confident else "fallback"
        print(f"[SHLOKA DEBUG] ✅ Returning {label} match — score: {result['score']}")
    else:
        print(f"[SHLOKA DEBUG] ❌ Metadata extraction failed — returning None")

    return result


def get_meaning_for_language(shloka: dict, language) -> str:
    """
    Return the most appropriate translation string for *language*.

    Falls back gracefully:
      requested language → english → core_meaning → placeholder

    The *language* parameter is defensively cast via _safe_language so a
    non-string value (e.g. int) never causes an AttributeError.
    """
    if not shloka:
        return ""

    # ✅ BUG FIX: guarantee language is always a valid string before any str ops
    lang_key = _safe_language(language)

    meaning_map: dict = shloka.get("meaning", {})

    translation = (
        meaning_map.get(lang_key, "")
        or meaning_map.get("english", "")
        or shloka.get("core_meaning", "")
        or "Seek the truth within."
    )
    return str(translation or "").strip()