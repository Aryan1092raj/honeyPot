# ScamBait AI — Autonomous Scam Honeypot

> AI-powered honeypot that detects scam intent, identifies red flags, engages
> scammers with realistic personas, extracts intelligence (UPI IDs, phone numbers,
> bank accounts, phishing links, emails), and sends evidence to a callback
> endpoint — all autonomously.

**India AI Impact Buildathon 2026 — Finalist**

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [License](#license)

---

## Features

| Capability | Details |
|------------|---------|
| **Scam Detection** | Multi-layer: lottery+amount, urgency+finance, keyword density, multi-signal |
| **Red-Flag Identification** | 9 categories: urgency, authority impersonation, financial request, personal info, too-good-to-be-true, threats, suspicious links, upfront payment, secrecy |
| **4 AI Personas** | Kamla Devi (elderly), Amit Verma (student), Rajesh Kumar (businessman), Priya Sharma (professional) |
| **Intelligence Extraction** | UPI IDs, phone numbers, bank accounts, phishing URLs, email addresses, suspicious keywords |
| **State Machine** | Deterministic 4-phase engagement: trust-building → probing → extraction → winding-down |
| **Adaptive Probing** | LLM receives "STILL MISSING" directive listing uncollected intelligence types |
| **Callback Reporting** | Auto-sends intelligence report to GUVI endpoint from turn 5 onwards (updated each turn) |
| **Error Resilience** | Never returns HTTP errors — all exceptions produce HTTP 200 with safe default reply |

---

## Architecture

The system is built as a **5-layer pipeline**:

```
Scammer Message
      │
      ▼
┌─────────────────────┐
│ 1. Scam Detection   │  Rule-based + keyword + regex signals
│ 2. Red-Flag ID      │  9 social-engineering red-flag categories
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 3. State Machine    │  trust_building → probing → extraction → winding_down
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 4. Persona Engine   │  Groq LLM (llama-3.3-70b-versatile) + 4 personas
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 5. Intel Extraction │  UPI, phone, URL, bank account, email (regex, dedup)
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 6. Callback Engine  │  POST intelligence to GUVI endpoint every turn
└─────────────────────┘
```

> The **state machine** controls engagement — not the LLM. The LLM only
> generates in-character text. Termination, transitions, and callback
> triggers are all deterministic backend logic.

See [docs/architecture.md](docs/architecture.md) for detailed layer documentation.

---

## Quick Start

### Prerequisites

- Python 3.12+
- A [Groq API key](https://console.groq.com/keys) (free tier works)

### Installation

```bash
# Clone
git clone https://github.com/Aryan1092raj/HoneyPot.git
cd HoneyPot

# Virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Dependencies
pip install -r requirements-api.txt

# Environment variables
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### Run Locally

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

- **API docs:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

### Send a Test Message

```bash
curl -X POST http://localhost:8000/api/honeypot \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-001",
    "message": {
      "sender": "scammer",
      "text": "Your SBI account will be blocked! Update KYC immediately or call 9876543210",
      "timestamp": "2025-02-11T10:30:00Z"
    },
    "conversationHistory": [],
    "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
  }'
```

---

## API Reference

### `POST /api/honeypot`

Send a scammer message and receive an in-character persona reply.

**Request body:**

```json
{
  "sessionId": "unique-session-id",
  "message": {
    "sender": "scammer",
    "text": "Your bank account is blocked. Verify immediately.",
    "timestamp": "2025-02-11T10:30:00Z"
  },
  "conversationHistory": [],
  "metadata": { "channel": "SMS", "language": "English", "locale": "IN" }
}
```

**Response:**

```json
{
  "status": "success",
  "reply": "Arey beta, kaun se bank se ho? Naam batao na? Aapka phone number do, main call back karungi.",
  "persona": "Kamla Devi",
  "scamDetected": true,
  "messagesExchanged": 1,
  "callbackSent": null,
  "extractedIntelligence": {
    "upiIds": [],
    "phoneNumbers": ["9876543210"],
    "phishingLinks": [],
    "bankAccounts": [],
    "emailAddresses": [],
    "suspiciousKeywords": ["blocked", "verify", "immediately", "bank", "kyc", "account"]
  },
  "redFlagsIdentified": [
    "Urgency / pressure tactics",
    "Impersonation of authority / institution",
    "Request for sensitive personal information",
    "Threatening / fear-based language"
  ],
  "engagementMetrics": {
    "totalMessagesExchanged": 1,
    "engagementDurationSeconds": 0
  },
  "agentNotes": "AI agent engaged suspected scammer for 1 exchanges over 0s. Phase: trust_building. Red flags identified: Urgency / pressure tactics, Impersonation of authority / institution, Request for sensitive personal information, Threatening / fear-based language. Scam detected: True. Intelligence: 1 items (UPI: 0, Phone: 1, Bank: 0, Links: 0, Email: 0)."
}
```

### `GET /api/session/{sessionId}`

Inspect a session''s state, extracted intelligence, and red flags.

### `GET /api/sessions`

List all active sessions (summary).

### `GET /health`

Server health check with Groq LLM status and active session count.

---

## Project Structure

```
├── README.md                  # This file
├── api.py                     # Entry point (thin wrapper → src/)
├── src/
│   ├── __init__.py            # Package metadata
│   ├── main.py                # FastAPI app, endpoints, error handlers
│   ├── honeypot_agent.py      # Persona engine, state machine, LLM
│   ├── scam_detection.py      # Multi-layer detection + red-flag ID
│   ├── intelligence.py        # Regex-based intelligence extraction
│   ├── models.py              # Pydantic request/response models
│   ├── config.py              # Constants, logging, compiled patterns
│   └── personas.py            # 4 AI persona definitions
├── test.py                    # Automated 10-turn integration test
├── requirements-api.txt       # API server dependencies
├── requirements.txt           # Streamlit UI dependencies
├── .env.example               # Environment variable template
├── .gitignore                 # Standard Python gitignore
└── docs/
    └── architecture.md        # Detailed architecture documentation
```

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `src/config.py` | Environment vars, logging, SCAM_KEYWORDS, RED_FLAG_CATEGORIES, regex patterns |
| `src/models.py` | Pydantic `HoneypotRequest` / `HoneypotResponse` with OpenAPI examples |
| `src/scam_detection.py` | `detect_scam()` (4-layer), `identify_red_flags()`, `identify_red_flags_detailed()` |
| `src/intelligence.py` | `extract_intelligence()` — regex extraction + dedup for 5 intel types |
| `src/honeypot_agent.py` | Session management, state machine, persona selection, LLM calls, fallbacks |
| `src/personas.py` | 4 persona prompts + `get_optimal_persona()` semantic intent router |
| `src/main.py` | FastAPI app, POST/GET endpoints, error handlers, callback logic |

---

## Configuration

All configuration is in `src/config.py` and `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key for LLM responses |
| `HONEYPOT_API_KEY` | Yes | API authentication key |
| `HACKATHON_CALLBACK_URL` | No | Callback endpoint (default: GUVI hackathon) |

### Tunable Constants (in `src/config.py`)

| Constant | Default | Purpose |
|----------|---------|---------|
| `MIN_MESSAGES` | 5 | First callback is sent at this turn |
| `MAX_MESSAGES` | 10 | Hard session cap (evaluator max) |
| `SCAM_KEYWORDS` | 36 keywords | Keyword-density scam detection |
| `RED_FLAG_CATEGORIES` | 9 categories | Social-engineering red-flag identification |

---

## Testing

Run the automated 10-turn integration test:

```bash
python test.py
```

This simulates a full evaluator interaction: sends 10 scammer messages,
verifies scam detection, intelligence extraction, and callback delivery.

---

## Deployment

### Render (Production)

The API is deployed on Render with auto-deploy from the `main` branch:

- **Live URL:** `https://scambait-api.onrender.com`
- **Honeypot endpoint:** `POST https://scambait-api.onrender.com/api/honeypot`
- **Docs:** `https://scambait-api.onrender.com/docs`

Render start command:

```bash
uvicorn api:app --host 0.0.0.0 --port $PORT
```

### Environment Variables on Render

Set `GROQ_API_KEY` and `HONEYPOT_API_KEY` in Render dashboard → Environment.

---

## 4 Personas

| Persona | Scam Types | Engagement Style |
|---------|-----------|-----------------|
| **Kamla Devi** (60, retired teacher, Jaipur) | Bank/KYC/authority | Confused Hinglish; asks for phone number to "call back and verify"; mentions grandson |
| **Amit Verma** (22, college student, Meerut) | Lottery/prize | Excited but hesitant; asks for link to "show roommate"; worries parents will scold |
| **Rajesh Kumar** (45, kirana store owner, Pune) | Investment/loan | Skeptical; demands SEBI registration, company website, official email |
| **Priya Sharma** (28, marketing pro, Hyderabad) | Credit card/tech | Methodical; asks for direct number, verifies on banking app, forwards to dad |

---

## Red-Flag Categories

| # | Category | Example Triggers |
|---|----------|-----------------|
| 1 | Urgency / pressure tactics | urgent, immediately, expire, act now, hurry |
| 2 | Impersonation of authority | bank, RBI, police, government, SBI |
| 3 | Request for money | send money, transfer, payment, UPI, deposit |
| 4 | Request for personal info | OTP, password, PIN, Aadhaar, KYC |
| 5 | Too-good-to-be-true | lottery, won, prize, guaranteed returns |
| 6 | Threatening language | arrest, court, legal action, jail, penalty |
| 7 | Suspicious links | http://, www., bit.ly, click here |
| 8 | Upfront payment | processing fee, registration fee, advance |
| 9 | Secrecy request | don''t tell, keep secret, confidential |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
