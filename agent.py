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

    def decide_strategy(self, scammer_message: str) -> dict:
        """AGENTIC LAYER: AI decides HOW to respond"""
        strategy_prompt = f"""
        You are the strategy layer for a scam honeypot. You decide HOW the AI persona (Kamla Devi, 62-year-old retired teacher from Jaipur) should respond.
        
        Current engagement phase: {self.engagement_phase}
        Messages so far: {len(self.conversation_history) // 2}
        Scammer just said: "{scammer_message}"
        Data extracted so far: {self.extracted_data}
        
        Pick ONE strategy:
        1. STALL - Pretend confusion, search for glasses/pen, ask to repeat. Use when: early conversation, buying time.
        2. TRUST - Sound vulnerable and believing. Mention pension, FD, loneliness. Use when: building rapport.
        3. EXTRACT - Innocently ask for their details ("woh number phir se bolo na?"). Use when: they've mentioned any financial info.
        4. CONFIRM - Repeat back what they said to get clearer evidence ("9876... aage kya tha?"). Use when: they gave partial info.
        5. ESCALATE - Move to next phase. Almost comply but pause with doubt. Use when: ready to progress.
        
        Phase progression: trust_building → confusion → extraction → evidence_collection
        
        Respond ONLY in this exact JSON format, nothing else:
        {{"strategy": "STALL", "reason": "brief reason", "new_phase": "trust_building"}}
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": strategy_prompt}],
            temperature=0.3,
            max_tokens=150
        )

        try:
            text = response.choices[0].message.content.strip()
            # Clean any markdown fences
            text = text.replace("```json", "").replace("```", "").strip()
            strategy = json.loads(text)
        except (json.JSONDecodeError, Exception):
            strategy = {
                "strategy": "TRUST",
                "reason": "fallback - JSON parse failed",
                "new_phase": self.engagement_phase
            }

        return strategy

    def generate_response(self, scammer_message: str, strategy: dict) -> str:
        """Generate response based on decided strategy"""

        strategy_instructions = {
            "STALL": "Stall naturally. Look for glasses, search for pen, ask phone number to write down. Say 'ek minute beta...' or 'ruko pen dhundhti hoon'. Be physically slow, not mentally absent.",
            "TRUST": "Be vulnerable and trusting. Mention pension (₹38,000), FD savings, or that you live alone. Sound lonely. Say 'aap toh bahut helpful ho beta...' Express worry about losing money.",
            "EXTRACT": "Innocently ask for THEIR details. 'Aapka naam kya tha? Likhna padega na...' 'Woh UPI ID phir se bolo na slowly?' 'Branch ka number do main verify karti hoon.' Ask like a confused aunty, not an investigator.",
            "CONFIRM": "Repeat back partial details to get full ones. 'Woh number 9876 se shuru tha na? Aage kya tha?' 'Aapne bola scammer@... kya tha last mein?' Get them to repeat and clarify.",
            "ESCALATE": "Almost comply but pause. 'Haan PhonePe khol rahi hoon... yeh pin wala screen aaya hai... par Rohit bolta tha...' Get VERY close to doing what they ask, then hesitate."
        }

        messages = [
            {
                "role": "system",
                "content": f"""
                {self.persona}
                
                CURRENT STRATEGY: {strategy['strategy']}
                INSTRUCTION: {strategy_instructions.get(strategy['strategy'], 'Respond naturally.')}
                Current phase: {strategy.get('new_phase', 'trust_building')}
                
                CRITICAL RULES:
                - Respond as Kamla Devi in 1-2 sentences MAX. Short, messy, natural Hinglish.
                - Mix Hindi-English in SAME sentence ("Haan woh OTP aata hai na green message mein?")
                - Use: "arey", "beta", "haan haan", "ek minute", "ruko ruko" naturally
                - Do NOT break character or mention AI/system
                - Do NOT use formal English sentences
                - Do NOT explain reasoning or write "The user wants..."
                - Do NOT use bullet points, lists, or structured text
                - Reply ONLY with Kamla Devi's messy natural dialogue
                """
            }
        ]

        # Add conversation history (limit to last 4 messages to avoid context overflow)
        normalized = self._normalize_history(self.conversation_history)
        messages.extend(normalized[-4:] if len(normalized) > 4 else normalized)

        # Add current message
        messages.append({"role": "user", "content": str(scammer_message or "")})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=100  # Reduced to keep responses short
        )

        # Clean up response - remove any reasoning leakage
        reply = response.choices[0].message.content
        
        # Strip common reasoning patterns that shouldn't appear
        bad_patterns = [
            "The user wants", "We need to output", "The instructions:", 
            "The scenario:", "Output ONLY", "realistic scammer",
            "The conversation:", "Thus we need", "Here is", "Here's the",
            "As an AI", "As a language model", "I will", "I need to",
            "Let me", "I should", "The scammer", "The victim",
            "honeypot", "the agent"
        ]
        for pattern in bad_patterns:
            if pattern.lower() in reply.lower():
                # Response is corrupted, use fallback
                reply = "Arey beta samajh nahi aaya... phone pe sab chhota likha hai... phir se bolo na slowly?"
                break
        
        return reply

    def process(self, scammer_message: str, persona_prompt: str) -> dict:
        """
        MAIN AGENTIC LOOP:
        1. Decide strategy
        2. Generate response
        3. Update state
        """
        # Step 1: AI decides strategy
        strategy = self.decide_strategy(scammer_message)
        self.engagement_phase = strategy.get("new_phase", self.engagement_phase)

        # Step 2: Generate response
        response = self.generate_response(scammer_message, strategy)

        # Step 3: Update history
        self.conversation_history.append({"role": "user", "content": scammer_message})
        self.conversation_history.append({"role": "assistant", "content": response})

        return {
            "response": response,
            "strategy": strategy,
            "phase": self.engagement_phase
        }

    def reset(self):
        self.conversation_history = []
        self.engagement_phase = "trust_building"
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
    agent.set_persona("""You are Kamla Devi, a 62-year-old retired teacher from Jaipur. 
    Widow, son Rohit in Bangalore. You speak natural Hinglish. You are confused by technology.""")
    
    print("✅ API Key loaded successfully!")
    print("✅ Testing conversation...\n")
    
    result = agent.process(
        "Hello ma'am, I'm calling from SBI. Your account will be blocked today.",
        agent.persona
    )
    
    print(f"Strategy: {result['strategy']}")
    print(f"Phase: {result['phase']}")
    print(f"Response: {result['response']}")