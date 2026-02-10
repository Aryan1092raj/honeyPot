import os
import json
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

# Fix for Windows: load .env using explicit path
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

class HoneypotAgent:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        
        # Debug: show what's happening
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found!\n"
                f"Looking for .env at: {env_path}\n"
                f".env exists: {env_path.exists()}\n"
                "Make sure .env file contains: GROQ_API_KEY=gsk_xxxxx"
            )
        
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
        self.conversation_history = []
        self.persona = ""
        self.engagement_phase = "trust_building"
        self.extracted_data = {
            "upi_ids": [],
            "account_numbers": [],
            "ifsc_codes": [],
            "phone_numbers": [],
            "links": []
        }

    def set_persona(self, persona_prompt: str):
        self.persona = persona_prompt
        self.conversation_history = []

    def _normalize_history(self, history: list) -> list:
        """Normalize history entries to Groq format with role/content."""
        normalized = []
        for msg in history or []:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            content = msg.get("content")
            if not role:
                sender = msg.get("sender")
                role = "assistant" if sender == "user" else "user"
            if content is None:
                content = msg.get("text") or ""
            normalized.append({"role": role, "content": str(content)})
        return normalized

    def generate_response(self, scammer_message: str) -> str:
        """Generate response with SINGLE LLM call - no separate strategy layer"""
        
        # Simple phase detection based on message count
        msg_count = len(self.conversation_history) // 2
        
        if msg_count <= 3:
            phase_instruction = "Be confused and suspicious. Ask who they are. Ask for their name and which branch/company."
        elif msg_count <= 8:
            phase_instruction = "Stall for time naturally. Look for pen, glasses. Ask them to repeat slowly. Mention checking with family."
        else:
            phase_instruction = "Almost comply but pause with doubt. Ask for their UPI ID, phone number, or details 'to verify'. Stay in character."
        
        messages = [
            {
                "role": "system",
                "content": f"""{self.persona}

CURRENT PHASE: {phase_instruction}

CRITICAL RULES:
- Respond in 1-2 sentences MAX
- Mix Hindi-English naturally in same sentence
- Use natural filler words: "arey", "beta", "haan", "ek minute"
- Ask innocent questions that make them reveal details
- NEVER say "I will", "Let me", "I should", "The user", "The scammer"
- NEVER break character or mention AI
- Reply ONLY with natural dialogue, nothing else"""
            }
        ]
        
        # Add conversation history (last 4 messages only)
        normalized = self._normalize_history(self.conversation_history)
        messages.extend(normalized[-4:] if len(normalized) > 4 else normalized)
        
        # Add current message
        messages.append({"role": "user", "content": str(scammer_message or "")})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.75,
            max_tokens=80  # Keep responses very short
        )
        
        reply = response.choices[0].message.content.strip()
        
        # Strict sanitization - block any metadata leakage
        forbidden_patterns = [
            "the user", "the scammer", "user wants", "scammer wants",
            "output format", "instructions", "i will", "i need to", "let me", 
            "i should", "as an ai", "as a language model", "i'm an ai",
            "the victim", "the agent", "honeypot", "generate", "scenario",
            "here is", "here's the", "respond with", "the conversation"
        ]
        
        reply_lower = reply.lower()
        for pattern in forbidden_patterns:
            if pattern in reply_lower:
                # Metadata leaked - use safe fallback
                return "Arey beta... samajh nahi aaya... phone pe dikkat hai... phir se bolo na?"
        
        # ── POST-GENERATION SAFETY FILTER ──
        # Block any reply that facilitates payment mechanics
        import re
        payment_patterns = [
            r'\bupi\b', r'\bnet\s*banking\b', r'\bpaytm\b', r'\bgpay\b',
            r'\bphonepe\b', r'\bneft\b', r'\brtgs\b', r'\bimps\b',
            r'\bpay\s+(now|here|using|via|through)\b',
            r'\bsend\s+(money|amount|payment)\b',
            r'\btransfer\s+(money|amount|fund)\b',
            r'\bwallet\b', r'\bkaise\s+(pay|bhej|transfer)\b',
            r'\bkahan\s+(bhej|send)\b',
        ]
        for pat in payment_patterns:
            if re.search(pat, reply_lower):
                # Payment facilitation detected - regenerate with safe fallback
                return "Beta... mujhe samajh nahi aa raha... aap pehle apna naam aur office ka address bolo?"
        
        # Block overly long responses (likely reasoning leak)
        if len(reply) > 200:
            return "Haan haan... par thoda slow bolo na... pen se likhna hai..."
        
        return reply

    def process(self, scammer_message: str) -> dict:
        """
        MAIN PROCESSING LOOP (SINGLE LLM CALL):
        1. Auto-select persona if not set
        2. Generate response with phase detection
        3. Update conversation history
        """
        # Auto-select persona if not already set
        if not self.persona:
            from personas import get_optimal_persona
            persona_name, self.persona = get_optimal_persona(scammer_message)
        
        # Generate response (single LLM call with built-in phase logic)
        response = self.generate_response(scammer_message)
        
        # Update history
        self.conversation_history.append({"role": "user", "content": scammer_message})
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # Calculate phase for tracking
        msg_count = len(self.conversation_history) // 2
        if msg_count <= 3:
            self.engagement_phase = "trust_building"
        elif msg_count <= 8:
            self.engagement_phase = "extraction"
        else:
            self.engagement_phase = "evidence_collection"
        
        return {
            "response": response,
            "phase": self.engagement_phase,
            "message_count": msg_count
        }

    def reset(self):
        """Reset conversation state and persona"""
        self.conversation_history = []
        self.engagement_phase = "trust_building"
        self.persona = ""  # Clear persona for auto-selection
        self.extracted_data = {
            "upi_ids": [],
            "account_numbers": [],
            "ifsc_codes": [],
            "phone_numbers": [],
            "links": []
        }


# ============================================================
# QUICK TEST (run: python agent.py)
# ============================================================

if __name__ == "__main__":
    agent = HoneypotAgent()
    
    print("✅ API Key loaded successfully!")
    print("✅ Testing auto-persona selection...\n")
    
    # Test 1: KYC scam (should auto-select Kamla Devi)
    print("Test 1: KYC Scam")
    result = agent.process(
        "Hello ma'am, I'm calling from SBI. Your account will be blocked today."
    )
    print(f"Phase: {result['phase']}")
    print(f"Messages: {result['message_count']}")
    print(f"Response: {result['response']}")
    
    # Test 2: Lottery scam (should auto-select Amit Verma)
    print("\nTest 2: Lottery Scam")
    agent.reset()
    result = agent.process(
        "Congratulations! You won ₹25 lakh lottery! Pay ₹5000 to claim."
    )
    print(f"Response: {result['response']}")