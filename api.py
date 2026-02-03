"""
ScamBait AI - FastAPI Backend
Hackathon-compliant API endpoint that wraps existing agent logic
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
import uuid
import httpx
import os
from dotenv import load_dotenv

# Import existing modules
from agent import HoneypotAgent
from personas import get_persona, list_personas
from extractor import IndianFinancialExtractor
from database import Database

load_dotenv()

# ============================================================
# FASTAPI APP INITIALIZATION
# ============================================================

app = FastAPI(
    title="ScamBait AI - Honeypot API",
    description="Autonomous AI honeypot for scam detection and intelligence extraction",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# GLOBAL INSTANCES
# ============================================================

db = Database()
extractor = IndianFinancialExtractor()

# Session storage (in-memory)
sessions = {}

# Hackathon callback URL (update when they provide it)
HACKATHON_CALLBACK_URL = os.getenv(
    "HACKATHON_CALLBACK_URL",
    "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"
)

# API Key for authentication
VALID_API_KEY = os.getenv("HONEYPOT_API_KEY", "default-secret-key-change-me")

# Rate limiting (simple in-memory tracker)
request_counts = {}

# ============================================================
# AUTHENTICATION & VALIDATION
# ============================================================

async def verify_api_key(x_api_key: str = Header(..., description="API key for authentication")):
    """Verify API key from request header"""
    if x_api_key != VALID_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    return x_api_key

def validate_message_length(message: str, max_length: int = 5000):
    """Validate message is not too long"""
    if not message:
        return message  # Let the endpoint handle empty messages
    if len(message) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Message too long. Maximum {max_length} characters allowed."
        )
    return message

# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class HoneypotRequest(BaseModel):
    """Request model for honeypot interaction - accepts both camelCase and snake_case"""
    sessionId: Optional[str] = Field(default=None, alias="session_id", description="Unique session identifier")
    message: Optional[str] = Field(default="", description="Scammer message", max_length=5000)
    conversationHistory: Optional[List[Dict]] = Field(default=[], alias="conversation_history", description="Previous conversation")
    metadata: Optional[Dict] = Field(default={}, description="Additional metadata")
    
    class Config:
        populate_by_name = True  # Accept both field name and alias
    
    @validator('message')
    def validate_message_not_empty(cls, v):
        if v and not v.strip():
            raise ValueError('Message cannot be empty or only whitespace')
        return v.strip() if v else ""
    
    @validator('sessionId')
    def generate_session_id_if_missing(cls, v):
        if not v:
            import uuid
            return f"auto-{uuid.uuid4().hex[:8]}"
        return v

class ExtractedIntelligence(BaseModel):
    """Extracted evidence from conversation"""
    upiIds: List[str] = Field(default=[], description="Extracted UPI IDs")
    bankAccounts: List[str] = Field(default=[], description="Bank account numbers")
    ifscCodes: List[str] = Field(default=[], description="IFSC codes")
    phoneNumbers: List[str] = Field(default=[], description="Phone numbers")
    phishingLinks: List[str] = Field(default=[], description="Suspicious URLs")

class HoneypotResponse(BaseModel):
    """Response model for honeypot interaction"""
    status: str = Field(default="success", description="Response status")
    reply: str = Field(..., description="Agent's response to scammer")
    sessionId: str = Field(..., description="Session identifier")
    scamDetected: bool = Field(default=False, description="Whether scam was detected")
    extractedIntelligence: Optional[ExtractedIntelligence] = None
    agentStrategy: Optional[str] = None
    currentPhase: Optional[str] = None
    messageCount: Optional[int] = None

class SessionSummary(BaseModel):
    """Final session summary for callback"""
    sessionId: str
    scamDetected: bool
    totalMessagesExchanged: int
    extractedIntelligence: ExtractedIntelligence
    agentNotes: str
    conversationLog: List[Dict]

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def create_session(session_id: str, persona: str = "Elderly Teacher"):
    """Initialize new session"""
    agent = HoneypotAgent()
    agent.set_persona(get_persona(persona))
    
    sessions[session_id] = {
        "agent": agent,
        "persona": persona,
        "created_at": datetime.now(),
        "message_count": 0,
        "extracted_data": {
            "upi_ids": [],
            "account_numbers": [],
            "ifsc_codes": [],
            "phone_numbers": [],
            "links": []
        },
        "conversation": [],
        "conversation_history": [],  # For agent's internal history
        "scam_detected": False
    }
    return sessions[session_id]

def get_session(session_id: str):
    """Get or create session"""
    if session_id not in sessions:
        return create_session(session_id)
    return sessions[session_id]

async def send_callback(session_id: str, session_data: dict):
    """Send final results to hackathon endpoint"""
    try:
        # Prepare callback payload
        payload = {
            "sessionId": session_id,
            "scamDetected": session_data["scam_detected"],
            "totalMessagesExchanged": session_data["message_count"],
            "extractedIntelligence": {
                "upiIds": session_data["extracted_data"]["upi_ids"],
                "bankAccounts": session_data["extracted_data"]["account_numbers"],
                "ifscCodes": session_data["extracted_data"]["ifsc_codes"],
                "phoneNumbers": session_data["extracted_data"]["phone_numbers"],
                "phishingLinks": session_data["extracted_data"]["links"]
            },
            "agentNotes": f"AI Agent ({session_data['persona']}) successfully engaged scammer using agentic strategies. "
                         f"Completed {session_data['message_count']} message exchanges. "
                         f"Extracted {sum(len(v) for v in session_data['extracted_data'].values())} evidence items.",
            "conversationLog": session_data["conversation"]
        }
        
        # Send async POST request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(HACKATHON_CALLBACK_URL, json=payload)
            print(f"Callback sent for session {session_id}: {response.status_code}")
            return response.status_code == 200
            
    except Exception as e:
        print(f"Callback error for session {session_id}: {e}")
        return False

# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "active",
        "service": "ScamBait AI - Honeypot API",
        "version": "1.0.0",
        "endpoints": {
            "honeypot": "/api/honeypot",
            "docs": "/docs",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(sessions)
    }

@app.get("/api/honeypot")
async def honeypot_get():
    """GET endpoint - API status"""
    return {
        "status": "success",
        "message": "ScamBait AI Honeypot API is active",
        "usage": "Send POST request with sessionId and message",
        "example": {
            "sessionId": "unique-session-id",
            "message": "Your bank account is blocked. Share UPI ID: scam@paytm"
        }
    }

@app.post("/api/honeypot", dependencies=[Depends(verify_api_key)])
async def honeypot_post(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Main honeypot endpoint - receives scammer message, returns agent response
    
    Requires X-API-Key header for authentication
    Accepts flexible JSON body formats for hackathon compatibility
    """
    try:
        # Parse raw JSON body flexibly
        try:
            body = await request.json()
        except:
            body = {}
        
        # Extract fields flexibly (try multiple possible field names)
        session_id = (
            body.get("sessionId") or 
            body.get("session_id") or 
            body.get("session") or 
            body.get("id") or 
            f"auto-{uuid.uuid4().hex[:8]}"
        )
        
        message = (
            body.get("message") or 
            body.get("msg") or 
            body.get("text") or 
            body.get("content") or 
            body.get("input") or 
            body.get("scammer_message") or
            body.get("scammerMessage") or
            ""
        )
        
        conversation_history = (
            body.get("conversationHistory") or 
            body.get("conversation_history") or 
            body.get("history") or 
            body.get("messages") or
            []
        )
        
        # Handle test requests with no message
        if not message or not message.strip():
            return {
                "status": "success",
                "reply": "Hello! This is ScamBait AI honeypot. Ready to engage scammers.",
                "sessionId": session_id,
                "scamDetected": False,
                "extractedIntelligence": {
                    "upiIds": [],
                    "bankAccounts": [],
                    "ifscCodes": [],
                    "phoneNumbers": [],
                    "phishingLinks": []
                },
                "agentStrategy": "READY",
                "currentPhase": "initialization",
                "messageCount": 0
            }
        
        # Validate message length
        if len(message) > 5000:
            message = message[:5000]
        
        # Get or create session
        session = get_session(session_id)
        agent = session["agent"]
        
        # Load conversation history from request if provided, otherwise use session history
        if conversation_history and len(conversation_history) > 0:
            # Use provided history (for external callers)
            agent.conversation_history = conversation_history
        else:
            # Use session's internal history
            agent.conversation_history = session.get("conversation_history", [])
        
        # Process scammer message with agentic logic
        result = agent.process(
            message,
            get_persona(session["persona"])
        )
        
        # Save updated conversation history back to session
        session["conversation_history"] = agent.conversation_history
        
        # Extract intelligence
        extraction = extractor.get_summary(message)
        
        # Update session data
        session["message_count"] += 1
        session["scam_detected"] = True  # Any interaction indicates scam
        
        # Merge extracted data
        for key in session["extracted_data"]:
            if key in extraction["extracted"]:
                session["extracted_data"][key].extend(extraction["extracted"][key])
                session["extracted_data"][key] = list(set(session["extracted_data"][key]))
        
        # Log conversation
        session["conversation"].append({
            "timestamp": datetime.now().isoformat(),
            "scammer": message,
            "agent": result["response"],
            "strategy": result["strategy"].get("strategy", ""),
            "phase": result["strategy"].get("new_phase", ""),
            "extracted": extraction["extracted"]
        })
        
        # Database logging
        db.log_conversation(
            session_id=session_id,
            persona=session["persona"],
            scammer_message=message,
            agent_response=result["response"],
            strategy=result["strategy"],
            extracted_data=extraction["extracted"],
            risk_level=extraction["risk_level"]
        )
        
        # Check if session should end (20 messages or high extraction)
        should_end = (
            session["message_count"] >= 20 or
            sum(len(v) for v in session["extracted_data"].values()) >= 10
        )
        
        if should_end:
            # Send callback in background
            background_tasks.add_task(send_callback, session_id, session)
            # Clean up session after callback
            background_tasks.add_task(lambda: sessions.pop(session_id, None))
        
        # Build response as dict (flexible format)
        return {
            "status": "success",
            "reply": result["response"],
            "sessionId": session_id,
            "scamDetected": session["scam_detected"],
            "extractedIntelligence": {
                "upiIds": session["extracted_data"]["upi_ids"],
                "bankAccounts": session["extracted_data"]["account_numbers"],
                "ifscCodes": session["extracted_data"]["ifsc_codes"],
                "phoneNumbers": session["extracted_data"]["phone_numbers"],
                "phishingLinks": session["extracted_data"]["links"]
            },
            "agentStrategy": result["strategy"].get("strategy", ""),
            "currentPhase": result["strategy"].get("new_phase", ""),
            "messageCount": session["message_count"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/api/honeypot/end-session")
async def end_session(sessionId: str, background_tasks: BackgroundTasks):
    """Manually end a session and trigger callback"""
    if sessionId not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[sessionId]
    
    # Send callback
    background_tasks.add_task(send_callback, sessionId, session)
    
    # Clean up
    background_tasks.add_task(lambda: sessions.pop(sessionId, None))
    
    return {
        "status": "success",
        "message": f"Session {sessionId} ended and callback triggered",
        "totalMessages": session["message_count"]
    }

@app.get("/api/sessions")
async def list_sessions():
    """List all active sessions"""
    return {
        "active_sessions": len(sessions),
        "sessions": [
            {
                "sessionId": sid,
                "persona": data["persona"],
                "messageCount": data["message_count"],
                "created": data["created_at"].isoformat(),
                "extractedItems": sum(len(v) for v in data["extracted_data"].values())
            }
            for sid, data in sessions.items()
        ]
    }

@app.get("/api/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get details of a specific session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    return {
        "sessionId": session_id,
        "persona": session["persona"],
        "messageCount": session["message_count"],
        "created": session["created_at"].isoformat(),
        "extractedIntelligence": session["extracted_data"],
        "conversation": session["conversation"]
    }

# ============================================================
# STARTUP/SHUTDOWN
# ============================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    print("🕵️ ScamBait AI API Started")
    print(f"📊 Database: {db}")
    print(f"🔍 Extractor: {extractor}")
    print(f"📞 Callback URL: {HACKATHON_CALLBACK_URL}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 ScamBait AI API Shutting Down")
    # Send callbacks for any remaining sessions
    for session_id, session_data in sessions.items():
        await send_callback(session_id, session_data)

# ============================================================
# RUN SERVER (for local testing)
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )