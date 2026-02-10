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
    sessionId: str = Field(..., description="Unique session identifier", example="wertyu-dfghj-ertyui")
    message: Union[str, MessageField] = Field(
        ..., 
        description="Message from suspected scammer (string or object)",
    )
    conversationHistory: Optional[List[Dict]] = Field(
        default=[], 
        description="Previous messages in conversation"
    )
    metadata: Optional[Dict] = Field(
        default={},
        description="Additional context (channel, language, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sessionId": "wertyu-dfghj-ertyui",
                "message": {
                    "sender": "scammer",
                    "text": "Your bank account will be blocked today. Verify immediately.",
                    "timestamp": 1770005528731
                },
                "conversationHistory": [],
                "metadata": {
                    "channel": "SMS",
                    "language": "English",
                    "locale": "IN"
                }
            }
        }

class HoneypotResponse(BaseModel):
    """Response model for honeypot endpoint"""
    status: str = Field(default="success", description="Status of the request")
    reply: str = Field(..., description="Agent's response to the scammer")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "reply": "Why is my account being suspended?"
            }
        }

# ============================================================
# APP SETUP
# ============================================================

app = FastAPI(
    title="ScamBait AI - Honeypot API",
    description="AI-powered scam honeypot for autonomous engagement and intelligence extraction",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None
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

# Fallback responses organized by conversation phase
# These rotate based on message count to simulate realistic conversation flow
NAIVE_RESPONSES = (
    # Phase 1: Initial confusion & trust-building (messages 0-4)
    "Haan ji? Kaun bol raha hai? Mera account ka kya hua... mujhe toh koi message nahi aaya?",
    "Arey arey... blocked matlab? Abhi toh ATM se pension nikala tha... aap pakka bank se ho?",
    "Acha acha... par aapka naam kya hai beta? Likhna padega na mujhe... pen dhundhti hoon ruko...",
    "Haan haan samajh rahi hoon... woh KYC KYC kya hota hai? Rohit bolta tha kuch aisa...",
    "Aap SBI se ho na? Mere Mansarovar branch se? Manager ka naam kya hai wahan?",
    # Phase 2: Controlled confusion & stalling (messages 5-9)
    "Ek minute beta... chasma lagati hoon... phone pe chhota likha hai sab... haan bolo?",
    "PhonePe? Haan hai mere paas... Rohit ne daala tha Diwali pe... par usme kya karna hai?",
    "OTP aata hai na green color wala message mein? Ruko ruko check karti hoon... bahut messages hain WhatsApp pe...",
    "Matlab main woh app wala open karoon? Haan kar rahi hoon... thoda slow hai phone... purana nahi hai par...",
    "Woh link wala message bheja aapne? Ruko dekhti hoon... yeh theek hai na? Rohit bolta hai link mat kholna...",
    # Phase 3: Almost-compliance & extraction (messages 10-14)
    "Haan haan main bhejti hoon... par kahan bhejoon? Woh UPI ID phir se bolo na slowly... likhti hoon...",
    "₹38,000 pension aata hai mahine ka beta... uska kuch nahi hoga na? Suresh ji ka paisa hai woh FD mein bhi...",
    "Account number chahiye aapko? Woh passbook mein likha hai na... ruko almari se lati hoon...",
    "Arey beta itni jaldi kyun? Kal nahi ho sakta? Rohit Sunday ko aayega toh woh kar dega...",
    "Theek hai theek hai... aap woh number phir se bolo na? 9 se shuru tha na? Likhti hoon...",
    # Phase 4: Doubt & re-engagement (messages 15-19)
    "Ek baat batao beta... agar aap bank se ho toh mera account number toh aapke paas hoga na?",
    "Meri padosan Sharma aunty bol rahi thi ki aajkal bahut fraud hota hai... aap toh real ho na?",
    "Haan haan kar rahi hoon... bas ek minute... phone rakh ke wapas call karna padega kya? Battery kam hai...",
    "Acha aap branch ka number do main khud call karke confirm kar leti hoon... Rohit bolta tha verify karo...",
    "Main complaint likhi hai... aapka ID number kya tha? Woh bhi likh deti hoon... naam phir se bolo na?"
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
    
    Session structure:
    {
        "messages_exchanged": int,
        "scam_detected": bool,
        "extracted_intelligence": {
            "bankAccounts": [],
            "upiIds": [],
            "phishingLinks": [],
            "phoneNumbers": [],
            "suspiciousKeywords": []
        },
        "callback_sent": bool,
        "last_activity": float,
        "conversation": []
    }
    """
    if session_id not in sessions:
        logger.info(f"Creating new session: {session_id}")
        sessions[session_id] = {
            "messages_exchanged": 0,
            "scam_detected": False,
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
# SCAM DETECTION
# ============================================================

def detect_scam(text: str) -> bool:
    """
    Detect scam intent using multiple signals.
    Requires at least 2 independent signals to confirm scam.
    
    Special handling for lottery scams (instant detection).
    """
    hits = 0
    text_lower = text.casefold()
    
    # SPECIAL CASE: Lottery scams (very common, easy to detect)
    lottery_indicators = ["lottery", "prize", "won", "winner", "congratulations", "claim", "jackpot"]
    amount_indicators = ["lakh", "crore", "₹", "rupees", "rs"]
    
    has_lottery = any(ind in text_lower for ind in lottery_indicators)
    has_amount = any(amt in text_lower for amt in amount_indicators)
    
    if has_lottery and has_amount:
        logger.info("Lottery scam detected (lottery keyword + amount)")
        return True  # Instant detection
    
    # Signal 1: Multiple keyword hits
    keyword_hits = sum(1 for kw in SCAM_KEYWORDS if kw in text_lower)
    if keyword_hits >= 2:
        hits += 1
        logger.debug(f"Keyword signal: {keyword_hits} keywords found")
    
    # Signal 2: UPI pattern
    if COMPILED_PATTERNS["upi"].search(text):
        hits += 1
        logger.debug("UPI signal detected")
    
    # Signal 3: Phone pattern
    if COMPILED_PATTERNS["phone"].search(text):
        hits += 1
        logger.debug("Phone signal detected")
    
    # Signal 4: URL pattern
    if COMPILED_PATTERNS["url"].search(text):
        hits += 1
        logger.debug("URL signal detected")
    
    is_scam = hits >= 2
    if is_scam:
        logger.info(f"Scam detected with {hits} signals (threshold: 2)")
    else:
        logger.debug(f"Not enough signals ({hits}/2) - treating as non-scam")
    
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
    "Haan ji? Mera account ka kya hua? Aap kaun ho beta?",
    "Arey? Bank se ho? Par bank toh kabhi phone nahi karta... aap pakka bank se ho?",
    "Kya bol rahe ho? Account block? Abhi toh sab theek tha... aapka naam kya hai?",
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
    """
    if not groq_client:
        return get_agent_response(session, scammer_message)
    
    try:
        # AUTO-SELECT PERSONA based on scam type
        from personas import get_optimal_persona
        persona_name, persona_prompt = get_optimal_persona(scammer_message)
        logger.info(f"Auto-selected persona: {persona_name}")
        
        # Build minimal context (last 4 messages only)
        history = session["conversation"][-4:]
        
        # Determine conversation phase for adaptive prompting
        msg_count = session["messages_exchanged"]
        if msg_count <= 3:
            phase_instruction = "You just received this call. Be CONFUSED and SUSPICIOUS. Ask who they are. Ask for their name and branch."
        elif msg_count <= 7:
            phase_instruction = "You are starting to believe them but still CONFUSED about tech terms. Stall for time. Look for your glasses. Search for pen. Ask them to repeat slowly."
        elif msg_count <= 12:
            phase_instruction = "You are almost ready to comply. ALMOST do what they ask but pause with doubt. Ask for their UPI ID or number so you can 'send' or 'verify'. Ask innocent questions that make them reveal information."
        else:
            phase_instruction = "You are getting doubtful again. Ask for their employee ID. Say your neighbor warned about fraud. Ask for branch number to verify. Keep them talking."

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

@app.post("/api/honeypot", response_model=HoneypotResponse)
@app.post("/api/endpoint", response_model=HoneypotResponse)  # Backward compatibility
async def honeypot(request: HoneypotRequest, background_tasks: BackgroundTasks) -> HoneypotResponse:
    """
    Main honeypot endpoint for scam detection and autonomous engagement.
    
    Accepts incoming message, detects scam intent, engages scammer using AI agent,
    extracts intelligence, and triggers callback after sufficient engagement.
    
    Returns agent's response in character as confused elderly person.
    """
    session_id = request.sessionId
    session = get_session(session_id)
    
    # If callback already sent, return closing response
    if session["callback_sent"]:
        logger.info(f"Session {session_id} already completed")
        return HoneypotResponse(
            status="success",
            reply="Thank you for calling. Goodbye."
        )
    
    # Extract message text
    message = _extract_message_text(request.message)
    
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
    
    # STEP 4: Update session
    session["messages_exchanged"] += 1
    session["conversation"].append({
        "scammer": message,
        "agent": reply,
        "timestamp": datetime.now().isoformat()
    })
    
    # STEP 5: Check if should end session
    intel = session["extracted_intelligence"]
    has_enough_intel = (
        len(intel["upiIds"]) >= 1 or
        len(intel["phoneNumbers"]) >= 1 or
        len(intel["bankAccounts"]) >= 1 or
        len(intel["phishingLinks"]) >= 1
    )
    
    should_end = (
        session["messages_exchanged"] >= MAX_MESSAGES or
        (session["messages_exchanged"] >= MIN_MESSAGES and has_enough_intel)
    )
    
    # STEP 6: Send callback if ending and scam detected
    if should_end and session["scam_detected"] and not session["callback_sent"]:
        logger.info(f"Session {session_id} ending - triggering callback")
        background_tasks.add_task(send_callback, session_id, session)
    
    return HoneypotResponse(status="success", reply=reply)

@app.get("/api/honeypot")
@app.head("/api/honeypot")
@app.options("/api/honeypot")
@app.get("/api/endpoint")
@app.head("/api/endpoint")
@app.options("/api/endpoint")
async def honeypot_other_methods(request: Request) -> dict:
    """Handle non-POST requests to honeypot endpoint"""
    if request.method == "GET":
        return {"status": "success", "reply": "ScamBait AI Honeypot is active"}
    return {"status": "success", "reply": "OK"}

@app.get("/", tags=["Health"])
@app.head("/", tags=["Health"])
async def root() -> dict:
    """Root endpoint"""
    return {"status": "success", "reply": "ScamBait AI is running"}

@app.get("/health", tags=["Health"])
@app.head("/health", tags=["Health"])
async def health() -> dict:
    """Health check endpoint"""
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
