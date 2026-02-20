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

    Turn 1 is deliberately casual so the honeypot doesn't look
    suspicious — a real person wouldn't interrogate a stranger
    immediately.
    """
    turn = session["messages_exchanged"] + 1  # next turn about to happen

    if turn <= 1:
        return (
            "You just received this call/message from a STRANGER. "
            "Be naturally confused or curious — you don't know who this is. "
            "Ask only ONE simple question like 'Kaun bol raha hai?' or "
            "'Haan ji, kya baat hai?' or 'Aap kaun?'. "
            "Do NOT ask for bank/UPI/phone/email yet — that would be weird "
            "on the very first message. Just respond like any normal person "
            "who got a random call. Keep it to 1-2 short sentences."
        )
    elif turn <= 3:
        return (
            "You are starting to understand what they want. Show mild "
            "concern or interest based on what they said. "
            "Ask ONE natural follow-up question — like 'Aapka number kya hai, "
            "main call back karungi?' OR 'Kaunsi bank se ho aap?'. "
            "Only ONE question per turn — don't interrogate. "
            "Show your personality — be chatty, confused, or worried."
        )
    elif turn <= 6:
        return (
            "You are now somewhat engaged and starting to worry/believe. "
            "Ask for verification details more actively: "
            "'UPI pe bhej do na details' or 'Apna phone number do, main note kar leti hoon'. "
            "Try to get: phone number, UPI ID, bank name, any links they share. "
            "Ask for 1-2 things per turn — be more direct but still in character. "
            "Express confusion about technology to seem authentic."
        )
    elif turn <= 8:
        return (
            "You are ready to comply but need ALL their details first. "
            "'Main paisa bhejti hoon — UPI ID bolo na? Woh @ ke baad kya aata hai?' "
            "'Account number bolo jismein transfer karoon. IFSC code bhi dena.' "
            "'Link phir se bhejo, phone pe chhota dikhta hai — pura http se bolo.' "
            "'Email pe documents bhejoongi — aapka email ID kya hai?' "
            "'Phone number ek baar aur bolo, network kharab tha sun nahi paya.' "
            "Almost comply with EVERYTHING but keep asking for ONE MORE missing detail. "
            "In EVERY reply, ask for at least 2 different pieces of information."
        )
    else:
        return (
            "You are getting doubtful. Your son/neighbour is warning about fraud. "
            "Ask: 'Employee ID kya hai aapka? Branch ka phone number do.' "
            "Say: 'Mera beta bol raha hai email pe proof bhejo — aapka email kya hai?' "
            "Say: 'Website ka link do, beta Google pe check karega.' "
            "Ask for UPI ID one more time: 'Google Pay pe verify karna hai, UPI ID bolo.' "
            "Ask for bank account number: 'Padosan bol rahi thi account number se trace hota hai — bolo na.' "
            "Keep extracting every possible identifier while showing increasing doubt."
        )


# ============================================================
# RESPONSE GENERATION — FALLBACKS
# ============================================================

def get_agent_response(session: dict, scammer_message: str) -> str:
    """Rotate through naive responses (fallback when LLM unavailable)."""
    idx = session["messages_exchanged"] % len(NAIVE_RESPONSES)
    return NAIVE_RESPONSES[idx]


_SUSPICION_REPLIES: tuple[str, ...] = (
    "Ji? Kaun bol raha hai? Pehchaan nahi aaya...",
    "Hello? Haan ji, kaun?",
    "Arey, kaun hai? Kya baat hai?",
    "Ji haan, boliye? Aap kaun bol rahe ho?",
    "Hello? Aap kaun? Main samajh nahi paayi...",
    "Ji? Kya hua? Aap kaun bol rahe ho?",
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
            groq_client = Groq(api_key=api_key, timeout=15.0)
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

        # Turn-aware rules: early turns are casual, later turns probe hard
        turn = session["messages_exchanged"] + 1
        if turn <= 1:
            rules = (
                "RULES:\n"
                "- 1-2 sentences ONLY. Very short, casual.\n"
                "- NEVER give real OTP/PIN/password/account number\n"
                "- NEVER break character\n"
                "- NEVER say 'I will' or 'Let me' (English-style)\n"
                "- NEVER write explanations or reasoning\n"
                "- Do NOT ask for phone/UPI/email/bank yet — just respond naturally\n"
                "- Sound confused or curious, like a normal person getting a random message"
            )
        elif turn <= 3:
            rules = (
                "RULES:\n"
                "- 2-3 sentences. Short, messy, natural Hinglish.\n"
                "- NEVER give real OTP/PIN/password/account number\n"
                "- NEVER break character\n"
                "- NEVER say 'I will' or 'Let me' (English-style)\n"
                "- NEVER write explanations or reasoning\n"
                "- Ask for ONE thing naturally (phone number OR bank name OR UPI)\n"
                "- Show concern or interest naturally — be in character"
            )
        else:
            rules = (
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
            )

        messages = [
            {
                "role": "system",
                "content": (
                    f"{prompt}\n\n"
                    f"CURRENT PHASE: {phase_instruction}\n\n"
                    f"STILL MISSING: We still need their {missing_str}.\n\n"
                    f"{rules}"
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
            max_tokens=200,
            temperature=0.85,
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
