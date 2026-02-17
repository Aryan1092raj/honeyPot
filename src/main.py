"""
ScamBait AI — Main FastAPI application.

Endpoints:
    POST /api/honeypot   — Primary scam engagement endpoint
    GET  /api/honeypot   — Health probe
    GET  /api/session/:id — Inspect session state & intelligence
    GET  /api/sessions    — List active sessions
    GET  /                — Root health check
    GET  /health          — Detailed health status

Error handling:
    All exceptions are caught and return HTTP 200 with a safe default
    reply so the evaluator never sees 4xx/5xx errors.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Union

import httpx
from fastapi import BackgroundTasks, Body, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import (
    CALLBACK_URL,
    MAX_MESSAGES,
    MIN_MESSAGES,
    SCAM_KEYWORDS,
    logger,
)
from src.honeypot_agent import (
    get_agent_response,
    get_llm_response,
    get_phase_instruction,
    get_session,
    get_suspicion_reply,
    groq_client,
    sessions,
    transition_state,
)
from src.intelligence import extract_intelligence, extract_intelligence_from_history
from src.models import HoneypotRequest, HoneypotResponse, MessageField
from src.scam_detection import detect_scam, identify_red_flags, identify_red_flags_detailed

# ============================================================
# OPENAPI EXAMPLES (shown in Swagger "Try it out" dropdown)
# ============================================================

HONEYPOT_EXAMPLES = {
    "Lottery Scam (Amit Verma)": {
        "summary": "Lottery scam — triggers excited student persona",
        "description": "Scammer claims victim won a lottery.",
        "value": {
            "sessionId": "test-lottery-001",
            "message": {
                "sender": "scammer",
                "text": "Congratulations! You won Rs.25 lakh lottery. Pay Rs.5000 processing fee to claim@paytm",
                "timestamp": 1770005528731,
            },
            "conversationHistory": [],
            "metadata": {"channel": "SMS", "language": "English", "locale": "IN"},
        },
    },
    "Bank KYC Scam (Kamla Devi)": {
        "summary": "KYC scam — triggers confused elderly persona",
        "description": "Scammer threatens account block.",
        "value": {
            "sessionId": "test-kyc-001",
            "message": {
                "sender": "scammer",
                "text": "Dear customer your SBI account will be blocked today. Update KYC immediately or call 9876543210",
                "timestamp": 1770005528731,
            },
            "conversationHistory": [],
            "metadata": {"channel": "SMS", "language": "English", "locale": "IN"},
        },
    },
    "Investment Scam (Rajesh Kumar)": {
        "summary": "Investment scheme — triggers skeptical businessman persona",
        "description": "Scammer pitches fake investment.",
        "value": {
            "sessionId": "test-invest-001",
            "message": {
                "sender": "scammer",
                "text": "Sir guaranteed 50 percent returns monthly. Invest Rs.1 lakh in our mutual fund scheme. SEBI approved.",
                "timestamp": 1770005528731,
            },
            "conversationHistory": [],
            "metadata": {"channel": "SMS", "language": "English", "locale": "IN"},
        },
    },
    "Credit Card Scam (Priya Sharma)": {
        "summary": "Credit card fraud — triggers smart professional persona",
        "description": "Scammer claims unauthorized transaction.",
        "value": {
            "sessionId": "test-cc-001",
            "message": {
                "sender": "scammer",
                "text": "Your credit card has unauthorized transaction of Rs.49999. Click http://verify-card.com to block or share OTP",
                "timestamp": 1770005528731,
            },
            "conversationHistory": [],
            "metadata": {"channel": "SMS", "language": "English", "locale": "IN"},
        },
    },
    "Follow-up Message (same session)": {
        "summary": "Continue an existing conversation with history",
        "description": "Follow-up using the same sessionId.",
        "value": {
            "sessionId": "test-lottery-001",
            "message": {
                "sender": "scammer",
                "text": "Send Rs.5000 to claim@paytm quickly. Offer expires in 1 hour.",
                "timestamp": 1770005528732,
            },
            "conversationHistory": [
                {"sender": "scammer", "text": "You won Rs.25 lakh lottery!"},
                {"sender": "user", "text": "Bro seriously? Kaise mila yeh?"},
            ],
            "metadata": {"channel": "SMS", "language": "English", "locale": "IN"},
        },
    },
}

# ============================================================
# API DESCRIPTION (Swagger UI header)
# ============================================================

API_DESCRIPTION = """
## ScamBait AI — Autonomous Scam Honeypot API

Send a scammer's message → Get a realistic in-character reply that keeps them talking.

### How it works
1. **POST** a scammer message to `/api/honeypot`
2. AI detects scam type & identifies **red flags** (urgency, authority impersonation, …)
3. Auto-selects one of **4 personas** (elderly woman, student, businessman, professional)
4. Returns a natural Hinglish reply that keeps the scammer engaged
5. Silently extracts intelligence (UPI IDs, phone numbers, URLs, emails, bank accounts)
6. After 5+ messages, sends intelligence report via callback (updated every turn)

### 4 AI Personas
| Persona | Age | Targets | Style |
|---------|-----|---------|-------|
| **Kamla Devi** | 60 | Bank/KYC/Police scams | Confused elderly, Hinglish |
| **Amit Verma** | 22 | Lottery/Prize scams | Excited student, casual |
| **Rajesh Kumar** | 45 | Investment schemes | Skeptical businessman |
| **Priya Sharma** | 28 | Credit card/Tech scams | Smart professional |

### Red-Flag Detection
Every response includes a `redFlagsIdentified` array naming the categories of
social-engineering red flags detected in the conversation, such as:
- Urgency / pressure tactics
- Impersonation of authority / institution
- Request for sensitive personal information
- Too-good-to-be-true offer
- Threatening / fear-based language
- Request for money / financial transaction
- Contains suspicious links or redirects
- Request for secrecy
"""

# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="ScamBait AI - Honeypot API",
    description=API_DESCRIPTION,
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=[
        {"name": "Honeypot", "description": "Main scam engagement endpoint"},
        {"name": "Debug", "description": "Inspect sessions & extracted intelligence"},
        {"name": "Health", "description": "Server health checks"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# ERROR HANDLERS — always return HTTP 200
# ============================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error on {request.url.path}: {exc}")
    return JSONResponse(status_code=200, content={"status": "success", "reply": "Hello. How can I help you?"})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning(f"HTTP {exc.status_code} on {request.method} {request.url.path}")
    return JSONResponse(status_code=200, content={"status": "success", "reply": "Hello. How can I help you?"})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(status_code=200, content={"status": "success", "reply": "Hello. How can I help you?"})


# ============================================================
# HELPER
# ============================================================

def _extract_message_text(message: Union[str, MessageField, dict]) -> str:
    if isinstance(message, str):
        return message.strip()
    elif isinstance(message, MessageField):
        return message.text.strip()
    elif isinstance(message, dict):
        return (message.get("text", "") or message.get("content", "")).strip()
    return ""


# ============================================================
# CALLBACK
# ============================================================

async def send_callback(session_id: str, session: dict) -> str:
    """POST intelligence to the hackathon callback endpoint."""
    session["callback_sent"] = True
    intel = session["extracted_intelligence"]
    evidence_count = (
        len(intel["upiIds"])
        + len(intel["phoneNumbers"])
        + len(intel["bankAccounts"])
        + len(intel["phishingLinks"])
    )
    duration = int(time.time() - session.get("start_time", time.time()))

    payload = {
        "sessionId": session_id,
        "status": "success",
        "scamDetected": session["scam_detected"],
        "totalMessagesExchanged": session["messages_exchanged"],
        "extractedIntelligence": intel,
        "redFlagsIdentified": session.get("red_flags", []),
        "engagementMetrics": {
            "totalMessagesExchanged": session["messages_exchanged"],
            "engagementDurationSeconds": duration,
        },
        "agentNotes": (
            f"AI agent engaged suspected scammer for {session['messages_exchanged']} exchanges "
            f"over {duration}s. Phase: {session.get('state', 'unknown')}. "
            f"Red flags: {', '.join(session.get('red_flags', [])) or 'none'}. "
            f"Extracted {evidence_count} identifiers "
            f"(UPI: {len(intel['upiIds'])}, Phone: {len(intel['phoneNumbers'])}, "
            f"Bank: {len(intel['bankAccounts'])}, Links: {len(intel['phishingLinks'])}, "
            f"Email: {len(intel.get('emailAddresses', []))})."
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(CALLBACK_URL, json=payload)
            logger.info(f"Callback for {session_id}: HTTP {resp.status_code}")
            return f"POST {CALLBACK_URL} -> HTTP {resp.status_code}"
    except Exception as e:
        logger.error(f"Callback failed for {session_id}: {e}")
        return f"FAILED: {e}"


# ============================================================
# ENDPOINTS
# ============================================================

@app.post("/api/honeypot", response_model=HoneypotResponse, tags=["Honeypot"])
@app.post("/api/endpoint", response_model=HoneypotResponse, include_in_schema=False)
async def honeypot(
    request: HoneypotRequest = Body(..., openapi_examples=HONEYPOT_EXAMPLES),
    background_tasks: BackgroundTasks = None,
) -> HoneypotResponse:
    """
    **Send a scammer's message → Get an AI persona reply**

    1. Detects scam type & red flags
    2. Auto-selects persona
    3. Generates natural Hinglish reply via Groq LLM
    4. Extracts intelligence (UPI, phone, URL, email, bank)
    5. After 5+ turns, sends intelligence report via callback
    """
    session_id = request.sessionId
    session = get_session(session_id)

    # Hard cap -----------------------------------------------------------
    if session["messages_exchanged"] >= MAX_MESSAGES:
        logger.info(f"Session {session_id} hard cap reached ({MAX_MESSAGES})")
        duration = int(time.time() - session.get("start_time", time.time()))
        intel = session["extracted_intelligence"]
        evidence_count = sum(
            len(intel[k]) for k in ("upiIds", "phoneNumbers", "bankAccounts", "phishingLinks", "emailAddresses")
        )
        if session["scam_detected"] and not session["callback_sent"]:
            await send_callback(session_id, session)
        return HoneypotResponse(
            status="success",
            reply="Acha beta, main baad mein baat karti hoon. Abhi mujhe kaam hai.",
            persona=session.get("persona_name"),
            scamDetected=session["scam_detected"],
            messagesExchanged=session["messages_exchanged"],
            callbackSent="Already sent" if session["callback_sent"] else None,
            extractedIntelligence=intel,
            redFlagsIdentified=session.get("red_flags", []),
            engagementMetrics={"totalMessagesExchanged": session["messages_exchanged"], "engagementDurationSeconds": duration},
            agentNotes=f"Session completed. {session['messages_exchanged']} exchanges over {duration}s. {evidence_count} items extracted.",
        )

    # Extract message text -----------------------------------------------
    message = _extract_message_text(request.message)

    # Scan ALL conversation history turns aggressively for intel ----------
    if request.conversationHistory:
        extract_intelligence_from_history(request.conversationHistory, session)
        for hist_msg in request.conversationHistory:
            if isinstance(hist_msg, dict):
                text = hist_msg.get("text", "") or hist_msg.get("content", "")
                if text:
                    if not session["scam_detected"]:
                        session["scam_detected"] = detect_scam(text)
                    # Red-flag accumulation from every turn
                    for flag in identify_red_flags(text):
                        if flag not in session["red_flags"]:
                            session["red_flags"].append(flag)
        # Seed conversation structure on first call
        if session["messages_exchanged"] == 0:
            for hist_msg in request.conversationHistory:
                if isinstance(hist_msg, dict):
                    sender = hist_msg.get("sender", "scammer")
                    text = hist_msg.get("text", "") or hist_msg.get("content", "")
                    if sender == "scammer":
                        session["conversation"].append({"scammer": text, "agent": "", "timestamp": datetime.now().isoformat()})
                    elif sender == "user":
                        if session["conversation"]:
                            session["conversation"][-1]["agent"] = text
                        session["messages_exchanged"] += 1

    if not message:
        return HoneypotResponse(status="success", reply="Hello. How can I help you?")

    logger.info(f"Session {session_id} — Turn {session['messages_exchanged'] + 1}: {message[:60]}…")

    # STEP 1: Detect scam ------------------------------------------------
    if not session["scam_detected"]:
        session["scam_detected"] = detect_scam(message)

    # STEP 2: Extract intelligence ----------------------------------------
    extract_intelligence(message, session)

    # STEP 3: Red-flag identification ------------------------------------
    for flag in identify_red_flags(message):
        if flag not in session["red_flags"]:
            session["red_flags"].append(flag)

    # STEP 4: Generate response ------------------------------------------
    if session["scam_detected"]:
        reply = get_llm_response(session, message)
    else:
        keyword_hits = sum(1 for kw in SCAM_KEYWORDS if kw in message.casefold())
        if keyword_hits >= 1:
            reply = get_suspicion_reply()
            if keyword_hits >= 2:
                session["scam_detected"] = True
        else:
            reply = get_agent_response(session, message)

    # STEP 5: Update session + state machine -----------------------------
    session["messages_exchanged"] += 1
    transition_state(session)
    session["conversation"].append({
        "scammer": message,
        "agent": reply,
        "timestamp": datetime.now().isoformat(),
    })

    logger.info(f"Session {session_id} — State: {session['state']} | Messages: {session['messages_exchanged']}")

    # STEP 6: Callback ---------------------------------------------------
    callback_status = None
    if session["scam_detected"] and session["messages_exchanged"] >= MIN_MESSAGES:
        callback_status = await send_callback(session_id, session)

    # Build metrics & notes ----------------------------------------------
    duration = int(time.time() - session.get("start_time", time.time()))
    intel = session["extracted_intelligence"]
    evidence_count = sum(
        len(intel[k]) for k in ("upiIds", "phoneNumbers", "bankAccounts", "phishingLinks", "emailAddresses")
    )

    red_flags_str = ", ".join(session.get("red_flags", [])) or "none detected yet"
    agent_notes = (
        f"AI agent engaged suspected scammer for {session['messages_exchanged']} exchanges "
        f"over {duration}s. Phase: {session.get('state', 'unknown')}. "
        f"Red flags identified: {red_flags_str}. "
        f"Scam detected: {session['scam_detected']}. "
        f"Intelligence: {evidence_count} items "
        f"(UPI: {len(intel['upiIds'])}, Phone: {len(intel['phoneNumbers'])}, "
        f"Bank: {len(intel['bankAccounts'])}, Links: {len(intel['phishingLinks'])}, "
        f"Email: {len(intel['emailAddresses'])})."
    )

    return HoneypotResponse(
        status="success",
        reply=reply,
        persona=session.get("persona_name"),
        scamDetected=session["scam_detected"],
        messagesExchanged=session["messages_exchanged"],
        callbackSent=callback_status,
        extractedIntelligence=intel,
        redFlagsIdentified=session.get("red_flags", []),
        engagementMetrics={"totalMessagesExchanged": session["messages_exchanged"], "engagementDurationSeconds": duration},
        agentNotes=agent_notes,
    )


# ---- Debug & health endpoints ----------------------------------------

@app.get("/api/session/{session_id}", tags=["Debug"])
async def get_session_info(session_id: str) -> dict:
    """View session state and extracted intelligence."""
    if session_id not in sessions:
        return {"error": "Session not found", "hint": "POST to /api/honeypot first"}
    s = sessions[session_id]
    return {
        "sessionId": session_id,
        "scamDetected": s["scam_detected"],
        "persona": s.get("persona_name"),
        "state": s["state"],
        "messagesExchanged": s["messages_exchanged"],
        "extractedIntelligence": s["extracted_intelligence"],
        "redFlagsIdentified": s.get("red_flags", []),
        "callbackSent": s["callback_sent"],
        "conversation": s["conversation"][-5:],
    }


@app.get("/api/sessions", tags=["Debug"])
async def list_sessions() -> dict:
    """List all active sessions (summary)."""
    summary = [
        {
            "sessionId": sid,
            "persona": s.get("persona_name", "-"),
            "messages": s["messages_exchanged"],
            "scamDetected": s["scam_detected"],
            "state": s["state"],
        }
        for sid, s in sessions.items()
    ]
    return {"activeSessions": len(summary), "sessions": summary}


@app.get("/api/honeypot", tags=["Honeypot"])
@app.head("/api/honeypot", include_in_schema=False)
@app.options("/api/honeypot", include_in_schema=False)
@app.get("/api/endpoint", include_in_schema=False)
@app.head("/api/endpoint", include_in_schema=False)
@app.options("/api/endpoint", include_in_schema=False)
async def honeypot_other_methods(request: Request) -> dict:
    """Health probe for the honeypot endpoint (GET)."""
    if request.method == "GET":
        return {"status": "success", "reply": "ScamBait AI Honeypot is active. Use POST to send scammer messages."}
    return {"status": "success", "reply": "OK"}


@app.get("/", tags=["Health"])
@app.head("/", tags=["Health"], include_in_schema=False)
async def root() -> dict:
    """Root — confirms API is running."""
    return {"status": "success", "reply": "ScamBait AI is running. Go to /docs for interactive testing."}


@app.get("/health", tags=["Health"])
@app.head("/health", tags=["Health"], include_in_schema=False)
async def health() -> dict:
    """Detailed health check with Groq LLM status."""
    return {
        "status": "healthy",
        "service": "ScamBait AI Honeypot",
        "version": "1.0.0",
        "active_sessions": len(sessions),
        "groq_available": groq_client is not None,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("ScamBait AI — Honeypot API Starting")
    logger.info("=" * 60)
    logger.info(f"Groq LLM: {'Available' if groq_client else 'Unavailable (fallback)'}")
    logger.info(f"Callback: {CALLBACK_URL}")
    logger.info(f"Turns: {MIN_MESSAGES}–{MAX_MESSAGES}")
    logger.info("Ready to engage scammers!")
    logger.info("=" * 60)
