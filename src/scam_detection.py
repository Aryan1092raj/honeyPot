"""
Multi-layer scam detection engine with explicit red-flag identification.

Detection is turn-aware: early turns (1-2) require actual scam signals
(keywords, identifiers, red-flag patterns). From turn 3 onward the
caller forces scamDetected=True regardless (every evaluator session IS
a scam, the greeting just hasn't revealed it yet).

Red-flag identification runs independently and annotates every detected
category (urgency, authority impersonation, financial request, etc.)
for investigative reporting.
"""

from __future__ import annotations

from src.config import (
    SCAM_KEYWORDS,
    COMPILED_PATTERNS,
    RED_FLAG_CATEGORIES,
    logger,
)


# ============================================================
# SCAM DETECTION
# ============================================================

def detect_scam(text: str, turn: int = 1) -> bool:
    """
    Determine whether *text* contains scam intent.

    Turn-aware thresholds:
        - Turn 1-2: require genuine scam indicators (keywords, patterns,
          identifiers). A plain greeting like "hello, i am mr. rajesh"
          won't trigger detection — this keeps the honeypot realistic.
        - Turn 3+: caller in main.py forces True regardless, so this
          function is only a secondary check.
    """
    text_lower = text.casefold()
    confidence = 0.0

    # --- Layer 1: keyword hits ---
    keyword_hits = sum(1 for kw in SCAM_KEYWORDS if kw in text_lower)
    if keyword_hits >= 2:
        confidence += 0.6
        logger.info(f"Scam signal: {keyword_hits} keyword hits (conf +0.6)")
    elif keyword_hits == 1:
        confidence += 0.3
        logger.info(f"Scam signal: {keyword_hits} keyword hit (conf +0.3)")

    # --- Layer 2: extractable identifiers ---
    for key, pat in COMPILED_PATTERNS.items():
        if pat.search(text):
            confidence += 0.3
            logger.info(f"Scam signal: {key} pattern found (conf +0.3)")

    # --- Layer 3: red-flag category matches ---
    for _cat_id, cat in RED_FLAG_CATEGORIES.items():
        if any(trigger in text_lower for trigger in cat["triggers"]):
            confidence += 0.2
            logger.info(f"Scam signal: red-flag '{cat['label']}' (conf +0.2)")
            break  # one hit is enough for this layer

    # Threshold depends on turn
    if turn <= 1:
        threshold = 0.3   # need real scam signals on turn 1
    elif turn <= 2:
        threshold = 0.2   # slightly lower on turn 2
    else:
        threshold = 0.1   # very easy from turn 3+

    is_scam = confidence >= threshold
    logger.info(f"detect_scam: turn={turn} confidence={confidence:.2f} threshold={threshold} → {is_scam}")
    return is_scam


# ============================================================
# RED-FLAG IDENTIFICATION
# ============================================================

def identify_red_flags(text: str) -> list[str]:
    """
    Scan *text* for all matching red-flag categories.

    Returns a list of human-readable red-flag labels such as
    ``"Urgency / pressure tactics"`` or ``"Request for sensitive
    personal information"``.

    This runs on **every** inbound message and the cumulative set
    is reported in ``redFlagsIdentified`` and ``agentNotes``.
    """
    text_lower = text.casefold()
    flags: list[str] = []

    for _cat_id, cat in RED_FLAG_CATEGORIES.items():
        if any(trigger in text_lower for trigger in cat["triggers"]):
            flags.append(cat["label"])

    return flags


def identify_red_flags_detailed(text: str) -> list[dict]:
    """
    Like :func:`identify_red_flags` but returns dicts with category
    ID, label, **and** the specific trigger phrases that matched.

    Useful for detailed agent notes.
    """
    text_lower = text.casefold()
    results: list[dict] = []

    for cat_id, cat in RED_FLAG_CATEGORIES.items():
        matched_triggers = [t for t in cat["triggers"] if t in text_lower]
        if matched_triggers:
            results.append(
                {
                    "category": cat_id,
                    "label": cat["label"],
                    "matchedTriggers": matched_triggers,
                }
            )

    return results
