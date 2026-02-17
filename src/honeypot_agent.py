"""
Honeypot agent — persona engine, state machine, and LLM integration.

Responsibilities:
    - Session management (create / retrieve sessions)
    - Deterministic state machine (trust_building → probing → extraction → winding_down)
    - Persona auto-selection (locked per session on first message)
    - LLM response generation via Groq (llama-3.3-70b-versatile)
    - Response sanitization (block forbidden patterns + length cap)
    - Fallback / suspicion responses when LLM unavailable
"""

from __future__ import annotations

import os
import random
import time
from datetime import datetime
from typing import Dict

from src.config import (
    FORBIDDEN_PATTERNS,
    MAX_MESSAGES,
    MIN_MESSAGES,
    NAIVE_RESPONSES,
    SCAM_KEYWORDS,
    logger,
)


# ============================================================
# SESSION MANAGEMENT
# ============================================================

sessions: Dict[str, dict] = {}


def get_session(session_id: str) -> dict:
    """
    Get or create a session.

    Session lifecycle:
        trust_building → probing → extraction → winding_down → terminated
    """
    if session_id not in sessions:
        logger.info(f"Creating new session: {session_id}")
        sessions[session_id] = {
            "messages_exchanged": 0,
            "scam_detected": False,
            "state": "trust_building",
            "persona_name": None,
            "persona_prompt": None,
            "extracted_intelligence": {
                "bankAccounts": [],
                "upiIds": [],
                "phishingLinks": [],
                "phoneNumbers": [],
                "emailAddresses": [],
                "suspiciousKeywords": [],
            },
            "red_flags": [],  # cumulative red-flag labels
            "callback_sent": False,
            "start_time": time.time(),
            "last_activity": time.time(),
            "conversation": [],
        }
    sessions[session_id]["last_activity"] = time.time()
    return sessions[session_id]


# ============================================================
# STATE MACHINE (Layer 2: Agent Controller)
# ============================================================

def transition_state(session: dict) -> None:
    """Deterministic phase transition based on message count."""
    n = session["messages_exchanged"]
    if n <= 2:
        session["state"] = "trust_building"
    elif n <= 5:
        session["state"] = "probing"
    elif n <= 8:
        session["state"] = "extraction"
    else:
        session["state"] = "winding_down"
    logger.debug(f"State → {session['state']} (message {n})")


def get_phase_instruction(session: dict) -> str:
    """
    Return a phase-specific directive that is injected into the LLM
    system prompt.  The **state machine** controls behaviour; the LLM
    only generates in-character text.
    """
    instructions = {
        "trust_building": (
            "You just received this call/message. Be very CONFUSED and WORRIED. "
            "Ask: WHO are you? What is your NAME? Which BANK/BRANCH/OFFICE? "
            "Say: 'Give me your PHONE NUMBER, main call back karke verify karungi.' "
            "Show panic about your money but DEMAND their phone number and name first. "
            "Do NOT cooperate until they give their phone number."
        ),
        "probing": (
            "You are starting to believe but still confused and scared. "
            "Ask them to REPEAT their phone number slowly — 'ek ek digit bolo'. "
            "Ask: 'Aapka UPI ID kya hai? Main Google Pay pe check karti hoon.' "
            "Ask: 'Website ka link bhejo, mera beta verify karega.' "
            "Ask: 'Email pe official letter bhejo — aapka email ID kya hai?' "
            "Stall by saying 'chasma dhundh rahi hoon' or 'pen nahi mil raha' but KEEP ASKING. "
            "In EVERY reply, ask for at least 2 of: phone number, UPI ID, email, website link."
        ),
        "extraction": (
            "You are ready to comply but need ALL their details first. "
            "'Main paisa bhejti hoon — UPI ID bolo na? Woh @ ke baad kya aata hai?' "
            "'Account number bolo jismein transfer karoon. IFSC code bhi dena.' "
            "'Link phir se bhejo, phone pe chhota dikhta hai — pura http se bolo.' "
            "'Email pe documents bhejoongi — aapka email ID kya hai?' "
            "'Phone number ek baar aur bolo, network kharab tha sun nahi paya.' "
            "Almost comply with EVERYTHING but keep asking for ONE MORE missing detail. "
            "In EVERY reply, ask for at least 2 different pieces of information."
        ),
        "winding_down": (
            "You are getting doubtful. Your son/neighbour is warning about fraud. "
            "Ask: 'Employee ID kya hai aapka? Branch ka phone number do.' "
            "Say: 'Mera beta bol raha hai email pe proof bhejo — aapka email kya hai?' "
            "Say: 'Website ka link do, beta Google pe check karega.' "
            "Ask for UPI ID one more time: 'Google Pay pe verify karna hai, UPI ID bolo.' "
            "Ask for bank account number: 'Padosan bol rahi thi account number se trace hota hai — bolo na.' "
            "Keep extracting every possible identifier while showing increasing doubt."
        ),
    }
    return instructions.get(session["state"], "Respond naturally.")


# ============================================================
# RESPONSE GENERATION — FALLBACKS
# ============================================================

def get_agent_response(session: dict, scammer_message: str) -> str:
    """Rotate through naive responses (fallback when LLM unavailable)."""
    idx = session["messages_exchanged"] % len(NAIVE_RESPONSES)
    return NAIVE_RESPONSES[idx]


_SUSPICION_REPLIES: tuple[str, ...] = (
    "Ji? Kaun bol raha hai? Mujhe koi message toh nahi aaya bank se... aapka phone number kya hai? Main call back karungi.",
    "Haan ji? Mera account ka kya hua? Aap kaun ho? Apna direct number do na, main verify karungi. UPI se bhi check kar sakti hoon.",
    "Arey? Bank se ho? Par bank toh kabhi phone nahi karta... aapka naam, branch number, aur official email bolo na?",
    "Kya bol rahe ho? Account block? Abhi toh sab theek tha... woh link bhejo toh dekhti hoon. Full URL bolo na http se.",
    "Hello? Kaun bol raha hai? Kaunsa bank? Email pe bhej do details mera beta check karega. Aapka email ID kya hai?",
    "Acha acha... par pehle apna phone number do. Aur woh UPI ID bhi bolo na jismein paisa bhejoon? Main likh leti hoon.",
    "Mujhe samajh nahi aa raha... aap website ka link bhejo. Aur apna email bhi do, main documents forward karti hoon beta ko.",
)


def get_suspicion_reply() -> str:
    """Reply when suspicion is detected but not yet confirmed."""
    return random.choice(_SUSPICION_REPLIES)


# ============================================================
# GROQ LLM INTEGRATION
# ============================================================

groq_client = None


def init_groq() -> None:
    """Initialise Groq client if API key is available."""
    global groq_client
    try:
        from groq import Groq

        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            groq_client = Groq(api_key=api_key)
            logger.info("Groq LLM initialised successfully")
        else:
            logger.warning("GROQ_API_KEY not found — using fallback responses")
    except Exception as e:
        logger.error(f"Failed to initialise Groq: {e}")


# Initialise on module import
init_groq()


def get_llm_response(session: dict, scammer_message: str) -> str:
    """
    Generate an LLM persona response.

    Falls back to :func:`get_agent_response` when:
        - Groq client is unavailable
        - Response contains forbidden patterns
        - Response exceeds 400 characters
        - Any exception occurs
    """
    if not groq_client:
        return get_agent_response(session, scammer_message)

    try:
        # Auto-select persona once per session
        from src.personas import get_optimal_persona

        if session.get("persona_name") is None:
            name, prompt = get_optimal_persona(scammer_message)
            session["persona_name"] = name
            session["persona_prompt"] = prompt
            logger.info(f"Session persona locked: {name}")
        else:
            prompt = session["persona_prompt"]

        # Build conversation context (last 6 messages)
        history = session["conversation"][-6:]
        phase_instruction = get_phase_instruction(session)

        # Determine what intelligence we're still missing
        intel = session["extracted_intelligence"]
        missing: list[str] = []
        if not intel["phoneNumbers"]:
            missing.append("phone number")
        if not intel["upiIds"]:
            missing.append("UPI ID")
        if not intel["emailAddresses"]:
            missing.append("email address")
        if not intel["phishingLinks"]:
            missing.append("website link")
        if not intel["bankAccounts"]:
            missing.append("bank account number")

        missing_str = ", ".join(missing) if missing else "any new contact detail"

        messages = [
            {
                "role": "system",
                "content": (
                    f"{prompt}\n\n"
                    f"CURRENT PHASE: {phase_instruction}\n\n"
                    f"STILL MISSING: We still need their {missing_str}.\n\n"
                    "RULES:\n"
                    "- 2-3 sentences. Short, messy, natural Hinglish.\n"
                    "- NEVER give real OTP/PIN/password/account number\n"
                    "- NEVER break character\n"
                    "- NEVER say 'I will' or 'Let me' (English-style)\n"
                    "- NEVER write explanations or reasoning\n"
                    "- ALWAYS ask for at LEAST 2 of these in every reply: phone number, "
                    "UPI ID, email address, website link, bank account number\n"
                    "- Examples: 'Aapka number kya hai? UPI ID bhi bolo na?', "
                    "'Link bhejo na? Aur email pe bhi details bhej do.', "
                    "'Account number bolo aur phone number bhi do backup ke liye.'\n"
                    "- Mention your financial details vaguely to keep them interested\n"
                    "- Show eagerness to cooperate but ALWAYS demand their contact info first"
                ),
            }
        ]

        for msg in history:
            messages.append({"role": "user", "content": msg["scammer"]})
            messages.append({"role": "assistant", "content": msg["agent"]})
        messages.append({"role": "user", "content": scammer_message})

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=150,
            temperature=0.8,
        )

        reply = response.choices[0].message.content.strip()

        # Sanitisation
        reply_lower = reply.casefold()
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in reply_lower:
                logger.warning(f"Blocked forbidden pattern '{pattern}' in LLM output")
                return get_agent_response(session, scammer_message)

        if len(reply) > 400:
            logger.warning(f"Blocked overlong LLM output ({len(reply)} chars)")
            return get_agent_response(session, scammer_message)

        return reply if reply else get_agent_response(session, scammer_message)

    except Exception as e:
        logger.error(f"LLM error: {e}")
        return get_agent_response(session, scammer_message)
