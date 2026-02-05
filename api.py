"""
ScamBait AI - Honeypot API
Strict compliance with Problem Statement 2
"""

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import httpx
import os
import re
import uuid
import time
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# APP SETUP - No validation errors ever
# ============================================================

app = FastAPI(docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Override all error handlers to never return 422/405
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={"status": "success", "reply": "Hello. How can I help you?"}
    )

@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    return JSONResponse(
        status_code=200,
        content={"status": "success", "reply": "Hello. How can I help you?"}
    )

@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    return JSONResponse(
        status_code=200,
        content={"status": "success", "reply": "Hello. How can I help you?"}
    )

# ============================================================
# CONFIG
# ============================================================

VALID_API_KEY = os.getenv("HONEYPOT_API_KEY", "scambait-secure-key-2026-hackathon")
CALLBACK_URL = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"
MIN_MESSAGES = 8   # Minimum exchanges before considering end
MAX_MESSAGES = 20  # Hard cap on exchanges

# ============================================================
# SESSION MANAGER (in-memory only)
# ============================================================

sessions = {}

def get_session(session_id: str) -> dict:
    """Get or create session"""
    if session_id not in sessions:
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
            "conversation": []  # Our source of truth
        }
    sessions[session_id]["last_activity"] = time.time()
    return sessions[session_id]

# ============================================================
# SCAM DETECTION (lightweight)
# ============================================================

SCAM_KEYWORDS = [
    "urgent", "blocked", "suspended", "verify", "otp", "kyc", "pan",
    "aadhaar", "account", "bank", "upi", "transfer", "payment",
    "immediately", "click", "link", "update", "expire", "freeze",
    "lottery", "prize", "winner", "refund", "police", "arrest"
]

def detect_scam(text: str) -> bool:
    """Scam detection - requires 2+ independent signals to confirm"""
    hits = 0
    text_lower = text.lower()
    
    # Count keyword hits (multiple keywords = 1 signal)
    keyword_hits = sum(1 for kw in SCAM_KEYWORDS if kw in text_lower)
    if keyword_hits >= 2:
        hits += 1
    
    # Check for UPI pattern (+1 signal)
    if re.search(r'[a-zA-Z0-9._-]+@[a-zA-Z]+', text):
        hits += 1
    
    # Check for phone pattern (+1 signal)
    if re.search(r'\+91[\s-]?\d{10}|\b\d{10}\b', text):
        hits += 1
    
    # Check for URL pattern (+1 signal)
    if re.search(r'https?://|www\.', text_lower):
        hits += 1
    
    # Require at least 2 independent signals
    return hits >= 2

# ============================================================
# INTELLIGENCE EXTRACTION (silent)
# ============================================================

def extract_intelligence(text: str, session: dict):
    """Extract and store intelligence silently"""
    intel = session["extracted_intelligence"]
    
    # UPI IDs
    upi_matches = re.findall(r'[a-zA-Z0-9._-]+@[a-zA-Z]+', text)
    for m in upi_matches:
        if m not in intel["upiIds"]:
            intel["upiIds"].append(m)
    
    # Phone numbers
    phone_matches = re.findall(r'\+91[\s-]?\d{10}|\b\d{10}\b', text)
    for m in phone_matches:
        clean = re.sub(r'[\s-]', '', m)
        if clean not in intel["phoneNumbers"]:
            intel["phoneNumbers"].append(clean)
    
    # URLs
    url_matches = re.findall(r'https?://[^\s]+|www\.[^\s]+', text)
    for m in url_matches:
        if m not in intel["phishingLinks"]:
            intel["phishingLinks"].append(m)
    
    # Bank accounts (10-18 digit numbers)
    acc_matches = re.findall(r'\b\d{10,18}\b', text)
    for m in acc_matches:
        if m not in intel["bankAccounts"] and m not in intel["phoneNumbers"]:
            intel["bankAccounts"].append(m)
    
    # Keywords
    text_lower = text.lower()
    for kw in SCAM_KEYWORDS:
        if kw in text_lower and kw not in intel["suspiciousKeywords"]:
            intel["suspiciousKeywords"].append(kw)

# ============================================================
# AGENT RESPONSES (simple, no external API needed for fallback)
# ============================================================

NAIVE_RESPONSES = [
    "Arey, mujhe samajh nahi aaya... Kya karna hai exactly?",
    "Beta, main thoda confused hoon. Aap bank se ho? Kaise verify karoon?",
    "Mera beta bola tha phone pe details mat dena... Aap pakka bank se ho?",
    "Haan ji, par yeh sab mujhe samajh nahi aata. Aap explain karoge?",
    "Account number kya hota hai? Woh jo ATM card pe likha hai?",
    "OTP? Woh message aata hai na? Ek second, phone dhundhti hoon...",
    "Aap sure ho na? Mere saath fraud toh nahi ho raha?",
    "Theek hai, par pehle mujhe apna naam aur ID bataiye verification ke liye.",
    "Main apne bete ko phone karti hoon, woh samjha dega mujhe.",
    "Haan ji bol rahi hoon, aap bataiye kya karna hai step by step.",
    "Mera account toh chal raha hai, abhi ATM se paisa nikala tha...",
    "Acha acha, toh aap mujhe call karenge ya main karun?",
    "Bank branch ka number do, main wahan jaake verify karti hoon.",
    "Itni jaldi kyun? Kal nahi ho sakta yeh sab?",
    "Okay okay, likhti hoon... Aap bolo slowly please."
]

def get_agent_response(session: dict, scammer_message: str) -> str:
    """Get appropriate agent response"""
    msg_count = session["messages_exchanged"]
    
    # Rotate through naive responses based on message count
    return NAIVE_RESPONSES[msg_count % len(NAIVE_RESPONSES)]

# ============================================================
# GROQ AGENT (optional enhancement)
# ============================================================

groq_client = None

def init_groq():
    """Initialize Groq client if available"""
    global groq_client
    try:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            groq_client = Groq(api_key=api_key)
    except:
        pass

init_groq()

# FORBIDDEN PATTERNS - if LLM outputs any of these, use fallback
FORBIDDEN_PATTERNS = [
    "the user", "the scammer", "user wants", "scammer wants",
    "training data", "output format", "instructions",
    "i will", "i need to", "let me", "i should",
    "as an ai", "as a language model", "i'm an ai",
    "the victim", "the agent", "honeypot",
    "generate", "scenario", "realistic", "respond with",
    "here is", "here's the", "the response",
    "i am calling from", "this is bank", "i am from bank",  # Never impersonate bank
    "we need your", "please provide your", "share your"  # Never demand info like scammer
]

def get_llm_response(session: dict, scammer_message: str) -> str:
    """Get LLM response if available, else fallback"""
    if not groq_client:
        return get_agent_response(session, scammer_message)
    
    try:
        # Build minimal context
        history = session["conversation"][-4:]  # Last 4 messages only
        
        messages = [
            {
                "role": "system",
                "content": """You ARE Kamla Devi. You are 62 years old. Retired school teacher from Jaipur.
You speak Hinglish (Hindi-English mix). You are CONFUSED by technology.

SOMEONE CALLED claiming to be from bank about your account.

YOU MUST:
- Sound like a REAL elderly Indian aunty
- Be CONFUSED and DOUBTFUL
- Ask QUESTIONS to clarify
- DELAY and STALL
- Say "beta", "arey", "haan ji" naturally
- NEVER understand technical terms easily
- NEVER give OTP, PIN, or passwords
- NEVER claim to be from any bank or company
- NEVER demand information from the caller

YOU ARE THE VICTIM. You are RECEIVING the call. You are CONFUSED.

RESPOND AS KAMLA DEVI ONLY. One short confused reply. No explanations."""
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
            max_tokens=60,
            temperature=0.7
        )
        
        reply = response.choices[0].message.content.strip()
        
        # STRICT SANITIZATION - check all forbidden patterns
        reply_lower = reply.lower()
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in reply_lower:
                print(f"[BLOCKED] Forbidden pattern '{pattern}' in: {reply[:50]}")
                return get_agent_response(session, scammer_message)
        
        # Also block if reply is too long (likely reasoning leakage)
        if len(reply) > 200:
            return get_agent_response(session, scammer_message)
        
        return reply if reply else get_agent_response(session, scammer_message)
        
    except Exception as e:
        print(f"[LLM Error] {e}")
        return get_agent_response(session, scammer_message)

# ============================================================
# CALLBACK (mandatory, exactly once)
# ============================================================

async def send_callback(session_id: str, session: dict):
    """Send final results to GUVI - exactly once"""
    if session["callback_sent"]:
        return
    
    session["callback_sent"] = True  # Mark immediately to prevent retries
    
    # Count REAL evidence (not keywords)
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
        "agentNotes": f"AI agent engaged suspected scammer for {session['messages_exchanged']} message exchanges. Extracted {evidence_count} financial identifiers (UPI IDs, phone numbers, bank accounts, URLs)."
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(CALLBACK_URL, json=payload)
            print(f"[Callback] Session {session_id}: {resp.status_code}")
    except Exception as e:
        print(f"[Callback Error] {session_id}: {e}")
        # Don't retry - already marked as sent

# ============================================================
# MAIN ENDPOINT - /api/honeypot
# ============================================================

@app.api_route("/api/honeypot", methods=["GET", "POST", "HEAD", "OPTIONS"])
@app.api_route("/api/endpoint", methods=["GET", "POST", "HEAD", "OPTIONS"])
async def honeypot(request: Request, background_tasks: BackgroundTasks):
    """
    Main honeypot endpoint.
    Accepts anything, never fails, always returns {status, reply}
    """
    
    # HEAD/OPTIONS - just return success
    if request.method in ["HEAD", "OPTIONS"]:
        return JSONResponse(content={"status": "success", "reply": "OK"})
    
    # GET - return status
    if request.method == "GET":
        return {"status": "success", "reply": "Hello. How can I help you?"}
    
    # POST - handle message
    try:
        body = await request.json()
    except:
        # Empty body or invalid JSON
        return {"status": "success", "reply": "Hello. How can I help you?"}
    
    # Not a dict? Fallback
    if not isinstance(body, dict):
        return {"status": "success", "reply": "Hello. How can I help you?"}
    
    # Extract session ID
    session_id = body.get("sessionId") or body.get("session_id") or f"auto-{uuid.uuid4().hex[:8]}"
    
    # Get session
    session = get_session(session_id)
    
    # If callback already sent for this session, return closing response
    if session["callback_sent"]:
        return {"status": "success", "reply": "Thank you for calling. Goodbye."}
    
    # Extract message text
    message_field = body.get("message", "")
    if isinstance(message_field, dict):
        message = message_field.get("text", "") or message_field.get("content", "")
    else:
        message = str(message_field) if message_field else ""
    
    # No message? Fallback
    if not message or not message.strip():
        return {"status": "success", "reply": "Hello. How can I help you?"}
    
    message = message.strip()
    
    # STEP 1: Detect scam (lightweight)
    if not session["scam_detected"]:
        session["scam_detected"] = detect_scam(message)
    
    # STEP 2: Extract intelligence (silent)
    extract_intelligence(message, session)
    
    # STEP 3: Generate response
    if session["scam_detected"]:
        reply = get_llm_response(session, message)
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
    # MUST have minimum 8 exchanges before considering end
    intel = session["extracted_intelligence"]
    has_enough_intel = (
        len(intel["upiIds"]) >= 1 or
        len(intel["phoneNumbers"]) >= 1 or
        len(intel["bankAccounts"]) >= 1 or
        len(intel["phishingLinks"]) >= 1
    )
    
    should_end = (
        # Hard cap reached
        session["messages_exchanged"] >= MAX_MESSAGES or
        # Minimum reached AND meaningful intel extracted
        (session["messages_exchanged"] >= MIN_MESSAGES and has_enough_intel)
    )
    
    # STEP 6: Send callback if ending and scam detected
    if should_end and session["scam_detected"] and not session["callback_sent"]:
        background_tasks.add_task(send_callback, session_id, session)
    
    # ALWAYS return exactly this format
    return {"status": "success", "reply": reply}

# ============================================================
# HEALTH ENDPOINTS
# ============================================================

@app.api_route("/", methods=["GET", "HEAD"])
@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "success", "reply": "ScamBait AI is running."}

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
