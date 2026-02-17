"""
Configuration constants and logging setup for ScamBait AI.

Centralizes all tunable parameters, API keys, keyword lists,
and compiled regex patterns used across the application.
"""

import os
import re
import logging
from dotenv import load_dotenv

# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("scambait-api")

# ============================================================
# API KEYS & URLS
# ============================================================

VALID_API_KEY = os.getenv("HONEYPOT_API_KEY", "scambait-secure-key-2026-hackathon")
CALLBACK_URL = os.getenv(
    "HACKATHON_CALLBACK_URL",
    "https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ============================================================
# SESSION PARAMETERS
# ============================================================

MIN_MESSAGES = 5   # Minimum exchanges before sending callback
MAX_MESSAGES = 10  # Hard cap — evaluator sends at most 10 turns

# ============================================================
# SCAM DETECTION KEYWORDS
# ============================================================

SCAM_KEYWORDS: tuple[str, ...] = (
    # Banking / Finance
    "urgent", "blocked", "suspended", "verify", "otp", "kyc", "pan",
    "aadhaar", "account", "bank", "upi", "transfer", "payment",
    "immediately", "click", "link", "update", "expire", "freeze",
    "locked", "compromised", "share", "identity", "security",
    "prevent", "suspension", "digit", "minutes", "hours",
    # Lottery / Prize
    "lottery", "prize", "winner", "won", "congratulations", "claim",
    "lakh", "crore", "rupees", "jackpot", "lucky", "draw",
    # Threats
    "police", "arrest", "court", "legal", "case", "crime", "fraud",
    # Offers
    "refund", "cashback", "reward", "bonus", "offer", "limited",
)

# ============================================================
# RED-FLAG CATEGORIES
# ============================================================
# Each category maps to a list of trigger phrases and a human-readable label.
# Used by scam_detection.identify_red_flags().

RED_FLAG_CATEGORIES: dict[str, dict] = {
    "URGENCY_PRESSURE": {
        "label": "Urgency / pressure tactics",
        "triggers": [
            "urgent", "immediately", "act now", "expire", "last chance",
            "right now", "act fast", "hurry", "quick", "limited time",
            "within minutes", "within hours", "today only", "don't delay",
            "minutes", "hours", "seconds",
        ],
    },
    "AUTHORITY_IMPERSONATION": {
        "label": "Impersonation of authority / institution",
        "triggers": [
            "bank", "rbi", "sbi", "government", "police", "court",
            "reserve bank", "income tax", "sebi", "customs", "telecom",
            "officer", "manager", "department", "ministry", "aadhaar",
        ],
    },
    "FINANCIAL_REQUEST": {
        "label": "Request for money / financial transaction",
        "triggers": [
            "send money", "transfer", "pay", "upi", "payment",
            "processing fee", "registration fee", "advance amount",
            "deposit", "invest", "amount", "rupees", "rs.",
        ],
    },
    "PERSONAL_INFO_REQUEST": {
        "label": "Request for sensitive personal information",
        "triggers": [
            "otp", "password", "pin", "cvv", "card number",
            "aadhaar", "pan", "kyc", "verify identity", "share details",
            "bank details", "account number", "login", "credentials",
        ],
    },
    "TOO_GOOD_TO_BE_TRUE": {
        "label": "Too-good-to-be-true offer",
        "triggers": [
            "lottery", "won", "prize", "congratulations", "winner",
            "guaranteed returns", "double", "triple", "jackpot",
            "lakh", "crore", "free", "lucky draw", "cashback", "reward",
        ],
    },
    "THREATENING_LANGUAGE": {
        "label": "Threatening / fear-based language",
        "triggers": [
            "arrest", "court", "legal action", "case filed", "jail",
            "warrant", "crime", "fraud", "suspend", "block", "freeze",
            "locked", "compromised", "terminate", "penalty", "fine",
        ],
    },
    "SUSPICIOUS_LINKS": {
        "label": "Contains suspicious links or redirects",
        "triggers": [
            "http://", "https://", "www.", "click here", "click link",
            ".xyz", ".tk", ".ml", "bit.ly", "tinyurl",
        ],
    },
    "UPFRONT_PAYMENT": {
        "label": "Upfront payment required before benefit",
        "triggers": [
            "processing fee", "registration fee", "tax amount",
            "claim charge", "advance", "fee before", "pay to receive",
            "pay first", "token amount",
        ],
    },
    "SECRECY_REQUEST": {
        "label": "Request for secrecy",
        "triggers": [
            "don't tell", "keep secret", "confidential", "private",
            "between us", "do not share", "alone",
        ],
    },
}

# ============================================================
# LLM FORBIDDEN PATTERNS (reasoning leakage)
# ============================================================

FORBIDDEN_PATTERNS: tuple[str, ...] = (
    "the user", "the scammer", "user wants", "scammer wants",
    "training data", "output format", "instructions",
    "i will", "i need to", "let me", "i should",
    "as an ai", "as a language model", "i'm an ai",
    "the victim", "the agent", "honeypot",
    "generate", "scenario", "realistic", "respond with",
    "here is", "here's the", "the response",
    "i am calling from", "this is bank", "i am from bank",
    "we need your", "please provide your", "share your",
)

# ============================================================
# NAIVE / FALLBACK RESPONSES
# ============================================================
# Every fallback actively probes for intelligence.

NAIVE_RESPONSES: tuple[str, ...] = (
    # Phase 1: Initial confusion + ask for PHONE NUMBER
    "Haan ji? Kaun bol raha hai? Aapka phone number kya hai... main call back karungi verify karne ke liye?",
    "Arey arey... blocked matlab? Aap pakka bank se ho? Aapka direct number do na, main khud call karungi.",
    # Phase 2: Ask for UPI ID and ACCOUNT NUMBER
    "Acha acha... par kahan bhejoon paisa? Woh UPI ID phir se bolo na slowly... likhti hoon... @ ke baad kya aata hai?",
    "Account number chahiye aapko? Woh passbook mein likha hai... par pehle aapka account number bolo jismein bhejoon? IFSC code bhi dena.",
    # Phase 3: Ask for LINK and EMAIL
    "Woh link wala message phir se bhejo... phone pe chhota likha hai dikha nahi. Pura URL bolo na http se?",
    "Email pe bhej do details beta... mera beta padhega. Aapka email ID kya hai? Gmail hai ya office wala?",
    # Phase 4: Repeat intelligence probes (multi-ask)
    "Haan haan main bhejti hoon... par UPI ID kya tha aapka? Woh @ wala phir se bolo na? Aur phone number bhi do backup ke liye.",
    "Aap branch ka phone number do na... landline hoga na? Aur woh website ka link bhi bhejo, main beta se check karwaungi.",
    # Phase 5: Deeper probing (ask for everything missing)
    "Theek hai... aapka website kya hai? Link bhejo WhatsApp pe. Aur email bhi do, main documents forward karungi.",
    "Padosan fraud fraud bol rahi thi... aapka official email bhejo, phone number do, aur UPI ID bhi — mera beta sab verify karega.",
    # Phase 6: Extra aggressive probing rounds
    "Main confuse ho gayi... ek kaam karo — apna phone number, UPI ID, aur bank account number sab ek saath bol do. Main likh leti hoon.",
    "Arey sun nahi paya... woh link phir se bolo? Aur email pe bhi bhej do. Mera beta aayega toh check karega.",
)

# ============================================================
# COMPILED REGEX PATTERNS
# ============================================================

COMPILED_PATTERNS: dict[str, re.Pattern] = {
    "upi": re.compile(r"[a-zA-Z0-9._-]+@[a-zA-Z]+"),
    "phone": re.compile(r"\+91[\s-]?\d{10}|\b\d{10}\b"),
    "url": re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE),
    "bank_account": re.compile(r"\b\d{10,18}\b"),
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
}
