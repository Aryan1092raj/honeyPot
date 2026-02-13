"""
ScamBait AI - Honeypot API (Optimized)
Hackathon Submission - Problem Statement 2

An AI-powered scam honeypot that detects scam intent, engages scammers
autonomously, and extracts intelligence without revealing detection.
"""

# ============================================================
# IMPORTS & CONFIGURATION
# ============================================================

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union
from datetime import datetime
import httpx
import os
import re
import uuid
import time
import logging
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# LOGGING SETUP
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("scambait-api")

# ============================================================
# PYDANTIC MODELS FOR API DOCUMENTATION
# ============================================================

class MessageField(BaseModel):
    """Message can be either a string or an object with text field"""
    text: str = Field(..., description="The message content")
    sender: Optional[str] = Field(default="scammer", description="Message sender")
    timestamp: Optional[int] = Field(default=None, description="Epoch timestamp in ms")

class HoneypotRequest(BaseModel):
    """Request model for honeypot endpoint"""
    sessionId: str = Field(
        ..., 
        description="Unique session ID. Use the SAME ID for follow-up messages in one conversation.",
        examples=["test-lottery-001", "wertyu-dfghj-ertyui"]
    )
    message: Union[str, MessageField] = Field(
        ..., 
        description="Scammer's message. Can be a plain string or an object with text/sender/timestamp.",
    )
    conversationHistory: Optional[List[Dict]] = Field(
        default=[], 
        description="(Optional) Previous messages. Format: [{sender: 'scammer', text: '...'}, {sender: 'user', text: '...'}]"
    )
    metadata: Optional[Dict] = Field(
        default={},
        description="(Optional) Extra context like channel, language, locale"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Lottery Scam (triggers Amit Verma persona)",
                    "value": {
                        "sessionId": "test-lottery-001",
                        "message": {
                            "sender": "scammer",
                            "text": "Congratulations! You won Rs.25 lakh lottery. Pay Rs.5000 processing fee to claim@paytm",
                            "timestamp": 1770005528731
                        },
                        "conversationHistory": [],
                        "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
                    }
                },
                {
                    "summary": "Bank KYC Scam (triggers Kamla Devi persona)",
                    "value": {
                        "sessionId": "test-kyc-001",
                        "message": {
                            "sender": "scammer",
                            "text": "Dear customer your SBI account will be blocked today. Update KYC immediately or call 9876543210",
                            "timestamp": 1770005528731
                        },
                        "conversationHistory": [],
                        "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
                    }
                },
                {
                    "summary": "Investment Scam (triggers Rajesh Kumar persona)",
                    "value": {
                        "sessionId": "test-invest-001",
                        "message": {
                            "sender": "scammer",
                            "text": "Sir guaranteed 50 percent returns monthly. Invest Rs.1 lakh in our mutual fund scheme. SEBI approved.",
                            "timestamp": 1770005528731
                        },
                        "conversationHistory": [],
                        "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
                    }
                },
                {
                    "summary": "Credit Card Scam (triggers Priya Sharma persona)",
                    "value": {
                        "sessionId": "test-cc-001",
                        "message": {
                            "sender": "scammer",
                            "text": "Your credit card has unauthorized transaction of Rs.49999. Click http://verify-card.com to block or share OTP",
                            "timestamp": 1770005528731
                        },
                        "conversationHistory": [],
                        "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
                    }
                },
                {
                    "summary": "Follow-up message (same session, with history)",
                    "value": {
                        "sessionId": "test-lottery-001",
                        "message": {
                            "sender": "scammer",
                            "text": "Send Rs.5000 to claim@paytm quickly. Offer expires in 1 hour.",
                            "timestamp": 1770005528732
                        },
                        "conversationHistory": [
                            {"sender": "scammer", "text": "You won Rs.25 lakh lottery!"},
                            {"sender": "user", "text": "Bro seriously? Kaise mila yeh?"}
                        ],
                        "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
                    }
                }
            ]
        }
    }

class HoneypotResponse(BaseModel):
    """Response model for honeypot endpoint"""
    status: str = Field(default="success", description="Always 'success' — API never returns errors")
    reply: str = Field(..., description="AI persona's in-character reply to the scammer (natural Hinglish)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Kamla Devi (elderly) response",
                    "value": {"status": "success", "reply": "Arey beta, account block ho jayega? Aap kaun se bank se bol rahe ho?"}
                },
                {
                    "summary": "Amit Verma (student) response",
                    "value": {"status": "success", "reply": "Bro seriously? Rs.25 lakh? Par processing fee kitna hai yaar?"}
                }
            ]
        }
    }

# ============================================================
# APP SETUP
# ============================================================

API_DESCRIPTION = """
## ScamBait AI — Autonomous Scam Honeypot API

Send a scammer's message → Get a realistic in-character reply that keeps them talking.

---

### Quick Start (copy-paste into "Try it out")

**Lottery scam:**
```json
{
  "sessionId": "test-lottery-001",
  "message": {
    "sender": "scammer",
    "text": "Congratulations! You won Rs.25 lakh lottery. Pay Rs.5000 processing fee to claim@paytm",
    "timestamp": 1770005528731
  },
  "conversationHistory": [],
  "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
}
```

**Bank KYC scam:**
```json
{
  "sessionId": "test-kyc-001",
  "message": {
    "sender": "scammer",
    "text": "Dear customer your SBI account will be blocked today. Update KYC immediately or call 9876543210",
    "timestamp": 1770005528731
  },
  "conversationHistory": [],
  "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
}
```

---

### How it works
1. **POST** a scammer message to `/api/honeypot`
2. AI detects scam type (lottery, KYC, investment, etc.)
3. Auto-selects one of **4 personas** (elderly woman, student, businessman, professional)
4. Returns a natural Hinglish reply that keeps the scammer engaged
5. Silently extracts UPI IDs, phone numbers, URLs as evidence
6. After 8-20 messages, sends intelligence report via callback

### 4 AI Personas
| Persona | Age | Targets | Style |
|---------|-----|---------|-------|
| **Kamla Devi** | 60 | Bank/KYC/Police scams | Confused elderly, Hinglish |
| **Amit Verma** | 22 | Lottery/Prize scams | Excited student, casual |
| **Rajesh Kumar** | 45 | Investment schemes | Skeptical businessman |
| **Priya Sharma** | 28 | Credit card/Tech scams | Smart professional |

### Tips
- Use a **unique sessionId** per conversation (UUID or any string)
- Send **follow-up messages** with the **same sessionId** to continue the conversation
- The `message` field accepts a string OR an object with `text`, `sender`, `timestamp`
- Check `/api/session/{sessionId}` to see extracted intelligence mid-conversation
"""

app = FastAPI(
    title="ScamBait AI - Honeypot API",
    description=API_DESCRIPTION,
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=[
        {"name": "Honeypot", "description": "Main scam engagement endpoint — send scammer messages here"},
        {"name": "Debug", "description": "Inspect active sessions and extracted intelligence"},
        {"name": "Health", "description": "Server health checks"},
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Override error handlers to NEVER return 422 (PS requires always 200)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Catch Pydantic/FastAPI validation errors - return 200 with default reply"""
    logger.warning(f"Validation error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=200,
        content={"status": "success", "reply": "Hello. How can I help you?"}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Catch all HTTP errors (405, 422, etc.) - return 200 with default reply"""
    logger.warning(f"HTTP {exc.status_code} on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=200,
        content={"status": "success", "reply": "Hello. How can I help you?"}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all: never crash, always return valid JSON"""
    logger.error(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=200,
        content={"status": "success", "reply": "Hello. How can I help you?"}
    )

# ============================================================
# CONFIGURATION CONSTANTS
# ============================================================

VALID_API_KEY = os.getenv("HONEYPOT_API_KEY", "scambait-secure-key-2026-hackathon")
CALLBACK_URL = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"
MIN_MESSAGES = 8   # Minimum exchanges before considering end
MAX_MESSAGES = 20  # Hard cap on exchanges

# Scam detection keywords
SCAM_KEYWORDS = (
    # Banking/Finance
    "urgent", "blocked", "suspended", "verify", "otp", "kyc", "pan",
    "aadhaar", "account", "bank", "upi", "transfer", "payment",
    "immediately", "click", "link", "update", "expire", "freeze",
    # Lottery/Prize (EXPANDED)
    "lottery", "prize", "winner", "won", "congratulations", "claim",
    "lakh", "crore", "rupees", "jackpot", "lucky", "draw",
    # Threats
    "police", "arrest", "court", "legal", "case", "crime", "fraud",
    # Others
    "refund", "cashback", "reward", "bonus", "offer", "limited"
)

# LLM forbidden patterns (to detect leaked reasoning)
FORBIDDEN_PATTERNS = (
    "the user", "the scammer", "user wants", "scammer wants",
    "training data", "output format", "instructions",
    "i will", "i need to", "let me", "i should",
    "as an ai", "as a language model", "i'm an ai",
    "the victim", "the agent", "honeypot",
    "generate", "scenario", "realistic", "respond with",
    "here is", "here's the", "the response",
    "i am calling from", "this is bank", "i am from bank",
    "we need your", "please provide your", "share your"
)

# Fallback responses - persona-neutral, no hardcoded names/details
# These rotate based on message count to simulate realistic conversation flow
NAIVE_RESPONSES = (
    # Phase 1: Initial confusion & trust-building (messages 0-4)
    "Haan ji? Kaun bol raha hai? Mera account ka kya hua... mujhe toh koi message nahi aaya?",
    "Arey arey... blocked matlab? Aap pakka bank se ho?",
    "Acha acha... par aapka naam kya hai? Likhna padega na mujhe... pen dhundhti hoon ruko...",
    "Haan haan samajh rahi hoon... woh KYC KYC kya hota hai exactly?",
    "Kaun se branch se bol rahe ho? Manager ka naam kya hai wahan?",
    # Phase 2: Controlled confusion & stalling (messages 5-9)
    "Ek minute... chasma lagati hoon... phone pe chhota likha hai sab... haan bolo?",
    "PhonePe? Haan hai mere paas... par usme kya karna hai exactly?",
    "OTP aata hai na green color wala message mein? Ruko ruko check karti hoon...",
    "Matlab main woh app wala open karoon? Haan kar rahi hoon... thoda slow hai phone...",
    "Woh link wala message bheja aapne? Ruko dekhti hoon... yeh theek hai na?",
    # Phase 3: Almost-compliance & extraction (messages 10-14)
    "Haan haan main bhejti hoon... par kahan bhejoon? Woh UPI ID phir se bolo na slowly...",
    "Pension aata hai mahine ka... uska kuch nahi hoga na? FD mein bhi hai thoda...",
    "Account number chahiye aapko? Woh passbook mein likha hai na... ruko lati hoon...",
    "Arey itni jaldi kyun? Kal nahi ho sakta?",
    "Theek hai theek hai... aap woh number phir se bolo na? Likhti hoon...",
    # Phase 4: Doubt & re-engagement (messages 15-19)
    "Ek baat batao... agar aap bank se ho toh mera account number toh aapke paas hoga na?",
    "Padosan bol rahi thi ki aajkal bahut fraud hota hai... aap toh real ho na?",
    "Haan haan kar rahi hoon... bas ek minute... battery kam hai phone ki...",
    "Acha aap branch ka number do main khud call karke confirm karti hoon...",
    "Main complaint likhi hai... aapka ID number kya tha? Naam phir se bolo na?"
)

# ============================================================
# COMPILED REGEX PATTERNS (Performance Optimization)
# ============================================================

COMPILED_PATTERNS = {
    "upi": re.compile(r'[a-zA-Z0-9._-]+@[a-zA-Z]+'),
    "phone": re.compile(r'\+91[\s-]?\d{10}|\b\d{10}\b'),
    "url": re.compile(r'https?://[^\s]+|www\.[^\s]+', re.IGNORECASE),
    "bank_account": re.compile(r'\b\d{10,18}\b')
}

# ============================================================
# SESSION MANAGEMENT
# ============================================================

sessions: Dict[str, dict] = {}

def get_session(session_id: str) -> dict:
    """
    Get or create session for given session ID.
    
    Session structure includes a proper state machine with phases:
    - trust_building: Initial confusion, ask who they are (messages 1-3)
    - probing: Show interest, ask for details (messages 4-8)
    - extraction: Almost comply, extract UPI/phone/details (messages 9-15)
    - winding_down: Show doubt, stall, mention checking with family (messages 16-20)
    - terminated: Session ended
    """
    if session_id not in sessions:
        logger.info(f"Creating new session: {session_id}")
        sessions[session_id] = {
            "messages_exchanged": 0,
            "scam_detected": False,
            "state": "trust_building",  # State machine phase
            "persona_name": None,
            "persona_prompt": None,
            "extracted_intelligence": {
                "bankAccounts": [],
                "upiIds": [],
                "phishingLinks": [],
                "phoneNumbers": [],
                "suspiciousKeywords": []
            },
            "callback_sent": False,
            "last_activity": time.time(),
            "conversation": []
        }
    sessions[session_id]["last_activity"] = time.time()
    return sessions[session_id]


# ============================================================
# STATE MACHINE (Layer 2: Agent Controller)
# ============================================================

def transition_state(session: dict) -> None:
    """
    Deterministic state machine transitions.
    BACKEND LOGIC — not LLM decision-making.
    """
    msg_count = session["messages_exchanged"]
    
    if msg_count <= 3:
        session["state"] = "trust_building"
    elif msg_count <= 8:
        session["state"] = "probing"
    elif msg_count <= 15:
        session["state"] = "extraction"
    else:
        session["state"] = "winding_down"
    
    logger.debug(f"State transition → {session['state']} (message {msg_count})")


def should_continue(session: dict) -> bool:
    """
    BACKEND LOGIC: Decide if engagement should continue.
    Deterministic — NOT an LLM decision.
    
    Termination conditions:
    1. Callback already sent
    2. Hard cap at MAX_MESSAGES (20)
    3. Minimum engagement (8) + sufficient intel (3+ items)
    """
    if session["callback_sent"]:
        return False
    
    if session["messages_exchanged"] >= MAX_MESSAGES:
        return False
    
    # Minimum engagement + sufficient intelligence extracted
    if session["messages_exchanged"] >= MIN_MESSAGES:
        intel = session["extracted_intelligence"]
        intel_count = sum(len(v) for v in intel.values())
        if intel_count >= 3:
            return False
    
    return True


def get_phase_instruction(session: dict) -> str:
    """
    Return phase-specific instruction for the LLM based on current state.
    The LLM generates responses; the state machine controls behavior.
    """
    phase_instructions = {
        "trust_building": (
            "You just received this call. Be CONFUSED and SUSPICIOUS. "
            "Ask who they are. Ask for their name and branch."
        ),
        "probing": (
            "You are starting to believe them but still CONFUSED about tech terms. "
            "Stall for time. Look for your glasses. Search for pen. Ask them to repeat slowly."
        ),
        "extraction": (
            "You are almost ready to comply. ALMOST do what they ask but pause with doubt. "
            "Ask for their UPI ID or number so you can 'send' or 'verify'. "
            "Ask innocent questions that make them reveal information."
        ),
        "winding_down": (
            "You are getting doubtful again. Ask for their employee ID. "
            "Say your neighbor warned about fraud. Ask for branch number to verify. "
            "Keep them talking but show skepticism."
        ),
    }
    return phase_instructions.get(session["state"], "Respond naturally.")

# ============================================================
# SCAM DETECTION
# ============================================================

def detect_scam(text: str) -> bool:
    """
    Detect scam intent using multiple signals.
    Special handling for lottery scams (very common in India).
    """
    hits = 0
    text_lower = text.casefold()
    
    # SPECIAL CASE: LOTTERY SCAMS (instant detection)
    lottery_keywords = ["lottery", "prize", "won", "winner", "congratulations", 
                        "claim", "jackpot", "lucky draw"]
    amount_keywords = ["lakh", "crore", "₹", "rupees", "rs.", "rs ", "inr"]
    
    has_lottery = any(kw in text_lower for kw in lottery_keywords)
    has_amount = any(amt in text_lower for amt in amount_keywords)
    
    if has_lottery and has_amount:
        logger.info("Lottery scam detected instantly")
        return True  # ← INSTANT DETECTION
    
    # SPECIAL CASE: FINANCIAL URGENCY (instant detection)
    urgency_keywords = ["urgent", "immediately", "blocked", "suspended", "expire"]
    financial_keywords = ["send", "pay", "transfer", "₹", "rupees", "amount"]
    
    has_urgency = any(kw in text_lower for kw in urgency_keywords)
    has_financial = any(kw in text_lower for kw in financial_keywords)
    
    if has_urgency and has_financial:
        logger.info("Financial urgency scam detected")
        return True  # ← INSTANT DETECTION
    
    # GENERAL DETECTION (multiple signals)
    keyword_hits = sum(1 for kw in SCAM_KEYWORDS if kw in text_lower)
    if keyword_hits >= 2:
        hits += 1
    
    if COMPILED_PATTERNS["upi"].search(text):
        hits += 1
    
    if COMPILED_PATTERNS["phone"].search(text):
        hits += 1
    
    if COMPILED_PATTERNS["url"].search(text):
        hits += 1
    
    is_scam = hits >= 2
    
    if is_scam:
        logger.info(f"Scam detected with {hits} signals")
    
    return is_scam

# ============================================================
# INTELLIGENCE EXTRACTION
# ============================================================

def extract_intelligence(text: str, session: dict) -> None:
    """
    Extract and store intelligence silently from scammer message.
    Extracts: UPI IDs, phone numbers, URLs, bank accounts, keywords.
    """
    intel = session["extracted_intelligence"]
    
    # Extract UPI IDs
    upi_matches = COMPILED_PATTERNS["upi"].findall(text)
    for match in upi_matches:
        if match not in intel["upiIds"]:
            intel["upiIds"].append(match)
            logger.info(f"Extracted UPI ID: {match}")
    
    # Extract phone numbers
    phone_matches = COMPILED_PATTERNS["phone"].findall(text)
    for match in phone_matches:
        clean = re.sub(r'[\s-]', '', match)
        if clean not in intel["phoneNumbers"]:
            intel["phoneNumbers"].append(clean)
            logger.info(f"Extracted phone: {clean}")
    
    # Extract URLs
    url_matches = COMPILED_PATTERNS["url"].findall(text)
    for match in url_matches:
        if match not in intel["phishingLinks"]:
            intel["phishingLinks"].append(match)
            logger.info(f"Extracted URL: {match}")
    
    # Extract bank accounts (10-18 digit numbers, excluding phones)
    acc_matches = COMPILED_PATTERNS["bank_account"].findall(text)
    for match in acc_matches:
        if match not in intel["bankAccounts"] and match not in intel["phoneNumbers"]:
            intel["bankAccounts"].append(match)
            logger.info(f"Extracted bank account: {match}")
    
    # Extract suspicious keywords
    text_lower = text.casefold()
    for kw in SCAM_KEYWORDS:
        if kw in text_lower and kw not in intel["suspiciousKeywords"]:
            intel["suspiciousKeywords"].append(kw)

# ============================================================
# AGENT RESPONSE LOGIC
# ============================================================

def get_agent_response(session: dict, scammer_message: str) -> str:
    """
    Get fallback agent response (when LLM unavailable or fails).
    Rotates through naive responses based on message count.
    """
    msg_count = session["messages_exchanged"]
    return NAIVE_RESPONSES[msg_count % len(NAIVE_RESPONSES)]

# Suspicion replies - used when scam signals detected but not confirmed
_SUSPICION_REPLIES = (
    "Ji? Kaun bol raha hai? Mujhe koi message toh nahi aaya bank se...",
    "Haan ji? Mera account ka kya hua? Aap kaun ho?",
    "Arey? Bank se ho? Par bank toh kabhi phone nahi karta... aap pakka bank se ho?",
    "Kya bol rahe ho? Account block? Abhi toh sab theek tha... aapka naam kya hai?",
    "Hello? Kaun bol raha hai? Kaunsa bank? Mujhe toh koi message nahi aaya...",
)

def get_suspicion_reply() -> str:
    """Reply when suspicion detected but not confirmed. Randomized for variety."""
    import random
    return random.choice(_SUSPICION_REPLIES)

# ============================================================
# GROQ LLM INTEGRATION (Optional Enhancement)
# ============================================================

groq_client = None

def init_groq() -> None:
    """Initialize Groq client if API key available"""
    global groq_client
    try:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            groq_client = Groq(api_key=api_key)
            logger.info("Groq LLM initialized successfully")
        else:
            logger.warning("GROQ_API_KEY not found - using fallback responses")
    except Exception as e:
        logger.error(f"Failed to initialize Groq: {e}")

init_groq()

def get_llm_response(session: dict, scammer_message: str) -> str:
    """
    Get LLM-generated response if available, else fallback.
    Implements strict sanitization to prevent reasoning leakage.
    Persona is selected ONCE per session, not per message.
    """
    if not groq_client:
        return get_agent_response(session, scammer_message)
    
    try:
        # AUTO-SELECT PERSONA (once per session, not per message)
        from personas import get_optimal_persona
        if session.get("persona_name") is None:
            persona_name, persona_prompt = get_optimal_persona(scammer_message)
            session["persona_name"] = persona_name
            session["persona_prompt"] = persona_prompt
            logger.info(f"Session persona locked: {persona_name}")
        else:
            persona_name = session["persona_name"]
            persona_prompt = session["persona_prompt"]
        
        # Build minimal context (last 4 messages only)
        history = session["conversation"][-4:]
        
        # Get phase instruction from state machine (Layer 2 controls behavior)
        phase_instruction = get_phase_instruction(session)

        messages = [
            {
                "role": "system",
                "content": f"""{persona_prompt}

CURRENT PHASE: {phase_instruction}

RULES:
- 1-2 sentences ONLY. Short, messy, natural.
- NEVER give real OTP/PIN/password
- NEVER break character
- NEVER say "I will" or "Let me" (English-style)
- NEVER write explanations or reasoning
- Ask innocent questions that make them reveal details (UPI ID, number, link)
- Mention your financial details vaguely to keep them interested"""
            }
        ]
        
        # Add conversation history
        for msg in history:
            messages.append({"role": "user", "content": msg["scammer"]})
            messages.append({"role": "assistant", "content": msg["agent"]})
        
        # Add current message
        messages.append({"role": "user", "content": scammer_message})
        
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=80,
            temperature=0.8
        )
        
        reply = response.choices[0].message.content.strip()
        
        # STRICT SANITIZATION - check forbidden patterns
        reply_lower = reply.casefold()
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in reply_lower:
                logger.warning(f"Blocked forbidden pattern '{pattern}' in LLM output")
                return get_agent_response(session, scammer_message)
        
        # Block overly long replies (likely reasoning leakage)
        if len(reply) > 200:
            logger.warning(f"Blocked overly long LLM output ({len(reply)} chars)")
            return get_agent_response(session, scammer_message)
        
        return reply if reply else get_agent_response(session, scammer_message)
        
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return get_agent_response(session, scammer_message)

# ============================================================
# CALLBACK LOGIC
# ============================================================

async def send_callback(session_id: str, session: dict) -> None:
    """
    Send final results to GUVI callback endpoint.
    Called exactly once per session when engagement completes.
    """
    if session["callback_sent"]:
        return
    
    session["callback_sent"] = True  # Mark immediately to prevent retries
    
    # Count real evidence (not just keywords)
    intel = session["extracted_intelligence"]
    evidence_count = (
        len(intel["upiIds"]) +
        len(intel["phoneNumbers"]) +
        len(intel["bankAccounts"]) +
        len(intel["phishingLinks"])
    )
    
    payload = {
        "sessionId": session_id,
        "scamDetected": session["scam_detected"],
        "totalMessagesExchanged": session["messages_exchanged"],
        "extractedIntelligence": session["extracted_intelligence"],
        "agentNotes": f"AI agent engaged suspected scammer for {session['messages_exchanged']} message exchanges. "
                      f"Final state: {session.get('state', 'unknown')}. "
                      f"Extracted {evidence_count} financial identifiers (UPI IDs: {len(intel['upiIds'])}, "
                      f"phone numbers: {len(intel['phoneNumbers'])}, bank accounts: {len(intel['bankAccounts'])}, "
                      f"URLs: {len(intel['phishingLinks'])})."
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(CALLBACK_URL, json=payload)
            logger.info(f"Callback sent for session {session_id}: HTTP {resp.status_code}")
            logger.debug(f"Callback payload: {payload}")
    except Exception as e:
        logger.error(f"Callback failed for session {session_id}: {e}")

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _extract_message_text(message: Union[str, MessageField, dict]) -> str:
    """Extract message text from various input formats"""
    if isinstance(message, str):
        return message.strip()
    elif isinstance(message, MessageField):
        return message.text.strip()
    elif isinstance(message, dict):
        return (message.get("text", "") or message.get("content", "")).strip()
    return ""

# ============================================================
# API ENDPOINTS
# ============================================================

@app.post("/api/honeypot", response_model=HoneypotResponse, tags=["Honeypot"])
@app.post("/api/endpoint", response_model=HoneypotResponse, include_in_schema=False)
async def honeypot(request: HoneypotRequest, background_tasks: BackgroundTasks) -> HoneypotResponse:
    """
    Send a scammer's message → Get an AI persona reply

    **What happens internally:**
    1. Detects scam type (lottery, KYC, investment, credit card, etc.)
    2. Auto-selects the best persona to engage this scam type
    3. Generates a natural Hinglish reply using Groq LLM
    4. Silently extracts evidence (UPI IDs, phone numbers, URLs)
    5. After 8-20 exchanges, sends intelligence report via callback

    **How to test:**
    - Click **Try it out** → pick an example from the dropdown → click **Execute**
    - Use the SAME `sessionId` to send follow-up messages
    - Check `/api/session/{sessionId}` to see extracted intelligence
    """
    session_id = request.sessionId
    session = get_session(session_id)
    
    # If session terminated or callback already sent, return closing response
    if session["callback_sent"] or session.get("state") == "terminated":
        logger.info(f"Session {session_id} already completed (state={session.get('state')})")
        return HoneypotResponse(
            status="success",
            reply="Thank you for calling. Goodbye."
        )
    
    # Extract message text
    message = _extract_message_text(request.message)
    
    # Seed session conversation from PS conversationHistory (first message only)
    if session["messages_exchanged"] == 0 and request.conversationHistory:
        for hist_msg in request.conversationHistory:
            if isinstance(hist_msg, dict):
                sender = hist_msg.get("sender", "scammer")
                text = hist_msg.get("text", "")
                if sender == "scammer":
                    session["conversation"].append({"scammer": text, "agent": "", "timestamp": datetime.now().isoformat()})
                    # Also extract intel from history messages
                    extract_intelligence(text, session)
                    if not session["scam_detected"]:
                        session["scam_detected"] = detect_scam(text)
                elif sender == "user":
                    # Attach agent reply to last scammer entry
                    if session["conversation"]:
                        session["conversation"][-1]["agent"] = text
                    session["messages_exchanged"] += 1
    
    # No message? Return default
    if not message:
        logger.warning(f"Empty message in session {session_id}")
        return HoneypotResponse(
            status="success",
            reply="Hello. How can I help you?"
        )
    
    logger.info(f"Session {session_id} - Message {session['messages_exchanged'] + 1}: {message[:50]}...")
    
    # STEP 1: Detect scam (lightweight)
    if not session["scam_detected"]:
        session["scam_detected"] = detect_scam(message)
    
    # STEP 2: Extract intelligence (silent)
    extract_intelligence(message, session)
    
    # STEP 3: Generate response
    if session["scam_detected"]:
        reply = get_llm_response(session, message)
    else:
        # Show suspicion if multiple keywords present
        keyword_hits = sum(1 for kw in SCAM_KEYWORDS if kw in message.casefold())
        if keyword_hits >= 2:
            reply = get_suspicion_reply()
        else:
            reply = "Hello. How can I help you today?"
    
    # STEP 4: Update session + state machine transition
    session["messages_exchanged"] += 1
    transition_state(session)  # Deterministic state transition (Layer 2)
    session["conversation"].append({
        "scammer": message,
        "agent": reply,
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info(f"Session {session_id} - State: {session['state']} | Messages: {session['messages_exchanged']}")
    
    # STEP 5: Check if should end session (backend logic, NOT LLM decision)
    should_end = not should_continue(session)
    
    # STEP 6: Send callback if ending and scam detected
    if should_end and session["scam_detected"] and not session["callback_sent"]:
        session["state"] = "terminated"
        logger.info(f"Session {session_id} ending - state=terminated, triggering callback")
        background_tasks.add_task(send_callback, session_id, session)
    
    return HoneypotResponse(status="success", reply=reply)

@app.get("/api/session/{session_id}", tags=["Debug"])
async def get_session_info(session_id: str) -> dict:
    """
    View session state and extracted intelligence

    Use this after sending messages to see what the AI detected and extracted.
    Pass the same `sessionId` you used in `/api/honeypot`.
    """
    if session_id not in sessions:
        return {"error": "Session not found", "hint": "Send a message to /api/honeypot first with this sessionId"}
    s = sessions[session_id]
    return {
        "sessionId": session_id,
        "scamDetected": s["scam_detected"],
        "persona": s.get("persona_name", "Not assigned yet"),
        "state": s["state"],
        "messagesExchanged": s["messages_exchanged"],
        "extractedIntelligence": s["extracted_intelligence"],
        "callbackSent": s["callback_sent"],
        "conversation": s["conversation"][-5:]  # last 5 exchanges
    }

@app.get("/api/sessions", tags=["Debug"])
async def list_sessions() -> dict:
    """
    List all active sessions (summary)

    Shows session IDs, message counts, and detected scam status.
    """
    summary = []
    for sid, s in sessions.items():
        summary.append({
            "sessionId": sid,
            "persona": s.get("persona_name", "-"),
            "messages": s["messages_exchanged"],
            "scamDetected": s["scam_detected"],
            "state": s["state"]
        })
    return {"activeSessions": len(summary), "sessions": summary}

@app.get("/api/honeypot", tags=["Honeypot"])
@app.head("/api/honeypot", include_in_schema=False)
@app.options("/api/honeypot", include_in_schema=False)
@app.get("/api/endpoint", include_in_schema=False)
@app.head("/api/endpoint", include_in_schema=False)
@app.options("/api/endpoint", include_in_schema=False)
async def honeypot_other_methods(request: Request) -> dict:
    """Check if honeypot is active (GET). Use POST to send scammer messages."""
    if request.method == "GET":
        return {"status": "success", "reply": "ScamBait AI Honeypot is active. Use POST to send scammer messages."}
    return {"status": "success", "reply": "OK"}

@app.get("/", tags=["Health"])
@app.head("/", tags=["Health"], include_in_schema=False)
async def root() -> dict:
    """Root — confirms API is running"""
    return {"status": "success", "reply": "ScamBait AI is running. Go to /docs for interactive testing."}

@app.get("/health", tags=["Health"])
@app.head("/health", tags=["Health"], include_in_schema=False)
async def health() -> dict:
    """Server health check — shows Groq LLM status and active session count"""
    return {
        "status": "healthy",
        "service": "ScamBait AI Honeypot",
        "version": "1.0.0",
        "active_sessions": len(sessions),
        "groq_available": groq_client is not None,
        "timestamp": datetime.now().isoformat()
    }

# ============================================================
# STARTUP EVENT
# ============================================================

@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("=" * 60)
    logger.info("ScamBait AI - Honeypot API Starting")
    logger.info("=" * 60)
    logger.info(f"Groq LLM: {'Available' if groq_client else 'Unavailable (using fallback)'}")
    logger.info(f"Callback URL: {CALLBACK_URL}")
    logger.info(f"Min/Max messages: {MIN_MESSAGES}/{MAX_MESSAGES}")
    logger.info("Ready to engage scammers!")
    logger.info("=" * 60)

# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ============================================================
# TESTING INSTRUCTIONS
# ============================================================

"""
TESTING THE API:

1. START SERVER:
   uvicorn api:app --reload --host 0.0.0.0 --port 8000

2. SWAGGER UI (Interactive Documentation):
   Open: http://localhost:8000/docs
   - Click POST /api/honeypot
   - Click "Try it out"
   - Use pre-filled example or modify
   - Click "Execute"
   - Verify response: {"status":"success","reply":"..."}

3. CURL TESTING (Command Line):

   # Test with message object format
   curl -X POST "http://localhost:8000/api/honeypot" \
     -H "Content-Type: application/json" \
     -d '{
       "sessionId": "test-001",
       "message": {
         "text": "Your bank account is blocked! Send UPI to scammer@paytm now!"
       }
     }'

   # Test with simple string format
   curl -X POST "http://localhost:8000/api/honeypot" \
     -H "Content-Type: application/json" \
     -d '{
       "sessionId": "test-002",
       "message": "Urgent! Verify at http://fake-bank.com or call 9876543210"
     }'

   # Test conversation continuation (with history)
   curl -X POST "http://localhost:8000/api/honeypot" \
     -H "Content-Type: application/json" \
     -d '{
       "sessionId": "test-001",
       "message": {"text": "Give me your OTP now!"},
       "conversationHistory": [
         {"sender": "scammer", "text": "Your account is blocked"},
         {"sender": "user", "text": "Why is it blocked?"}
       ]
     }'

4. ENVIRONMENT VARIABLES (.env file):
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx
   HONEYPOT_API_KEY=your-secure-api-key-here

5. TRIGGER CALLBACK:
   Send 8+ messages in same session with scam patterns
   Check logs for "Callback sent for session..."

6. HEALTH CHECK:
   curl http://localhost:8000/health

EXPECTED OUTPUT:
{
  "status": "success",
  "reply": "Arey beta, main thoda confused hoon..."
}
"""
