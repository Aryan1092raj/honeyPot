"""
Regex-based intelligence extraction module.

Extracts and deduplicates the following from scammer messages:
    - UPI IDs      (e.g. scam@paytm)
    - Phone numbers (Indian +91 format, both original and cleaned)
    - Phishing URLs (http:// and www. patterns)
    - Bank accounts (10–18 digit numbers, excluding known phones)
    - Email addresses (full TLD validation)
    - Suspicious keywords from the SCAM_KEYWORDS list

All extraction is idempotent — calling multiple times on the same text
will not produce duplicates.
"""

from __future__ import annotations

import re

from src.config import COMPILED_PATTERNS, SCAM_KEYWORDS, logger


def extract_intelligence_from_history(conversation_history: list, session: dict) -> None:
    """
    Aggressively scan ALL conversation history turns for intelligence.
    Extracts from both scammer and user messages.
    """
    if not conversation_history:
        return
    for msg in conversation_history:
        if isinstance(msg, dict):
            text = msg.get("text", "") or msg.get("content", "")
            if text:
                extract_intelligence(text, session)


def extract_intelligence(text: str, session: dict) -> None:
    """
    Extract actionable intelligence from *text* and store in *session*.

    Extraction order matters:
    1. Emails first (to prevent UPI regex from eating email fragments)
    2. UPI IDs (skip anything already captured as email)
    3. Phone numbers (both cleaned and original format)
    4. URLs (trailing punctuation stripped)
    5. Bank accounts (deduplicated against phone digits)
    6. Suspicious keywords
    """
    intel = session["extracted_intelligence"]

    # 1. Emails ----------------------------------------------------------
    for match in COMPILED_PATTERNS["email"].findall(text):
        if match not in intel["emailAddresses"]:
            intel["emailAddresses"].append(match)
            logger.info(f"Extracted email: {match}")

    # 2. UPI IDs ---------------------------------------------------------
    for match in COMPILED_PATTERNS["upi"].findall(text):
        is_email = any(match in email for email in intel["emailAddresses"])
        if match not in intel["upiIds"] and not is_email:
            intel["upiIds"].append(match)
            logger.info(f"Extracted UPI ID: {match}")

    # 3. Phone numbers ---------------------------------------------------
    for match in COMPILED_PATTERNS["phone"].findall(text):
        original = match.strip()
        clean = re.sub(r"[\s-]", "", original)
        if clean not in intel["phoneNumbers"]:
            intel["phoneNumbers"].append(clean)
            logger.info(f"Extracted phone: {clean}")
        if original != clean and original not in intel["phoneNumbers"]:
            intel["phoneNumbers"].append(original)
            logger.info(f"Extracted phone (original format): {original}")

    # 4. URLs ------------------------------------------------------------
    for match in COMPILED_PATTERNS["url"].findall(text):
        clean_url = match.rstrip(".,;:!?)")
        if clean_url not in intel["phishingLinks"]:
            intel["phishingLinks"].append(clean_url)
            logger.info(f"Extracted URL: {clean_url}")

    # 5. Bank accounts ---------------------------------------------------
    phone_digits: set[str] = set()
    for pn in intel["phoneNumbers"]:
        digits = re.sub(r"[^0-9]", "", pn)
        phone_digits.add(digits)
        phone_digits.add(digits[-10:])

    for match in COMPILED_PATTERNS["bank_account"].findall(text):
        if match not in intel["bankAccounts"] and match not in phone_digits:
            intel["bankAccounts"].append(match)
            logger.info(f"Extracted bank account: {match}")

    # 6. Suspicious keywords ---------------------------------------------
    text_lower = text.casefold()
    for kw in SCAM_KEYWORDS:
        if kw in text_lower and kw not in intel["suspiciousKeywords"]:
            intel["suspiciousKeywords"].append(kw)
