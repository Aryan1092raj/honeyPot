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
        You are an AI strategy layer for a scam honeypot system.
        
        Current engagement phase: {self.engagement_phase}
        Scammer just said: "{scammer_message}"
        Data extracted so far: {self.extracted_data}
        
        Decide the STRATEGY for next response. Pick ONE:
        1. STALL - Ask for repetition, pretend confusion
        2. TRUST - Build rapport, seem vulnerable and trusting
        3. EXTRACT - Gently push for financial details
        4. CONFIRM - Repeat back what they said to get clearer evidence
        5. ESCALATE - Move to next engagement phase
        
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
            "STALL": "Ask them to repeat. Pretend you didn't hear clearly. Say something like 'Sorry, my hearing is not good today...'",
            "TRUST": "Be trusting and vulnerable. Show you believe them. Express worry about your account.",
            "EXTRACT": "Gently ask for their details. Say something like 'Can you send me the account number so I can transfer?'",
            "CONFIRM": "Repeat back what they said to confirm details. Ask for clarification on any numbers.",
            "ESCALATE": "Move conversation forward naturally toward financial details."
        }

        messages = [
            {
                "role": "system",
                "content": f"""
                {self.persona}
                
                CURRENT STRATEGY: {strategy['strategy']}
                INSTRUCTION: {strategy_instructions.get(strategy['strategy'], 'Respond naturally.')}
                Current phase: {strategy.get('new_phase', 'trust_building')}
                
                IMPORTANT RULES:
                - Respond naturally as the persona in 2-3 sentences MAX
                - Do NOT break character or mention you are an AI
                - Do NOT explain your reasoning or say things like "The user wants..."
                - Do NOT use bullet points or lists
                - Just speak naturally as the persona would
                - Reply ONLY with the persona's dialogue, nothing else
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
            "The conversation:", "Thus we need"
        ]
        for pattern in bad_patterns:
            if pattern.lower() in reply.lower():
                # Response is corrupted, use fallback
                reply = "Beta, main thoda confused hoon... can you please explain again slowly? My son usually helps me with these bank matters."
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
    agent.set_persona("""You are Ramesh, a 62-year-old retired teacher from Pune. 
    You are kind, trusting, and not very tech-savvy. Respond naturally.""")
    
    print("✅ API Key loaded successfully!")
    print("✅ Testing conversation...\n")
    
    result = agent.process(
        "Hello sir, I'm from SBI. Your account is blocked.",
        agent.persona
    )
    
    print(f"Strategy: {result['strategy']}")
    print(f"Phase: {result['phase']}")
    print(f"Response: {result['response']}")