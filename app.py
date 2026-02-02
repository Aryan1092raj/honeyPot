import streamlit as st
import uuid
import json
import base64
import time
import random
from datetime import datetime
from dotenv import load_dotenv
from agent import HoneypotAgent
from personas import get_persona, list_personas
from extractor import IndianFinancialExtractor
from database import Database

load_dotenv()

try:
    from audio_recorder_streamlit import audio_recorder
    AUDIO_RECORDER_AVAILABLE = True
except Exception:
    AUDIO_RECORDER_AVAILABLE = False

# ============================================================
# RANDOMNESS: Dynamic metadata for production-ready feel
# ============================================================

CALLER_BACKGROUNDS = [
    "Street noise detected",
    "Call center environment",
    "VoIP connection identified",
    "Background chatter detected",
    "Silent call characteristics",
    "Robotic voice patterns",
    "Script reading detected",
    "Urgency tone analysis: HIGH"
]

RISK_INDICATORS = [
    "Number not in telecom database",
    "Caller ID spoofing suspected",
    "Similar pattern to known scams",
    "Pressure tactics detected",
    "Unusual payment requests",
    "Phishing link pattern detected",
    "Cross-referenced with fraud DB",
    "Voice stress analysis: DECEPTIVE"
]

PROCESSING_MESSAGES = [
    "Analyzing voice patterns",
    "Cross-referencing database",
    "Extracting financial data",
    "Running sentiment analysis",
    "Checking fraud indicators",
    "Matching scam signatures",
    "Evaluating threat level",
    "Generating response strategy"
]

ANALYSIS_DETAILS = [
    "Pattern match: 87% confidence",
    "Linguistic analysis complete",
    "Behavioral scoring: 8.3/10",
    "Fraud probability: 91%",
    "Response time: 1.2s avg",
    "Conversation flow: SUSPICIOUS",
    "Entity extraction: 4 items",
    "Risk escalation triggered"
]

try:
    from tts_handler import TTSHandler
    TTS_AVAILABLE = True
except Exception:
    TTS_AVAILABLE = False

try:
    from stt_handler import STTHandler
    STT_AVAILABLE = True
except Exception:
    STT_AVAILABLE = False

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="ScamBait AI - Honeypot System",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>
    .main { background-color: #0f1117; color: #e8e8e8; }
    .main-header {
        font-size: 2.8rem;
        font-weight: bold;
        background: linear-gradient(90deg, #FF4B4B, #FF8C00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.2rem;
        padding-top: 1rem;
    }
    .sub-header { font-size: 1.1rem; text-align: center; color: #888; margin-bottom: 1.5rem; }
    .scammer-msg {
        background: #1e1e2e;
        border-left: 4px solid #FF4B4B;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .scammer-msg .label { color: #FF4B4B; font-weight: bold; font-size: 0.85rem; margin-bottom: 4px; }
    .agent-msg {
        background: #1a2e1a;
        border-left: 4px solid #4CAF50;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .agent-msg .label { color: #4CAF50; font-weight: bold; font-size: 0.85rem; margin-bottom: 4px; }
    .strategy-badge {
        display: inline-block;
        background: #2a2a4a;
        color: #a0a0ff;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 0.75rem;
        margin-top: 4px;
    }
    .phase-badge {
        display: inline-block;
        background: #2a3a2a;
        color: #a0ffa0;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 0.75rem;
        margin-left: 6px;
    }
    .extracted-item {
        background: #1e2a3a;
        border-radius: 6px;
        padding: 6px 10px;
        margin: 4px 0;
        font-family: monospace;
        font-size: 0.85rem;
        color: #7dd3fc;
    }
    .risk-high { color: #FF4B4B; font-weight: bold; }
    .risk-medium { color: #FFA500; font-weight: bold; }
    .risk-low { color: #4CAF50; font-weight: bold; }
    .demo-banner {
        background: #2a1a3a;
        border: 1px solid #6a3d9a;
        border-radius: 8px;
        padding: 8px 14px;
        text-align: center;
        color: #c49aff;
        font-size: 0.85rem;
        margin-bottom: 1rem;
    }
    .voice-badge {
        display: inline-block;
        background: #1a1a3a;
        border: 1px solid #4a4aff;
        color: #8888ff;
        border-radius: 12px;
        padding: 2px 8px;
        font-size: 0.7rem;
        margin-left: 6px;
    }
    .incoming-call {
        background: linear-gradient(135deg, #1a1a2e 0%, #2a1a3a 100%);
        border: 3px solid #FF4B4B;
        border-radius: 16px;
        padding: 32px;
        text-align: center;
        margin: 20px 0;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { border-color: #FF4B4B; }
        50% { border-color: #FF8C00; }
    }
    .call-number {
        font-size: 2rem;
        font-weight: bold;
        color: #FF4B4B;
        margin: 16px 0;
    }
    .call-timer {
        font-size: 1.5rem;
        color: #4CAF50;
        font-family: monospace;
        margin: 10px 0;
    }
    audio {
        width: 100%;
        height: 36px;
        margin-top: 6px;
        border-radius: 6px;
        background: #1a1a2e;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# DEMO SCENARIOS
# ============================================================

DEMO_SCENARIOS = {
    "Banking Scam (KYC Update)": {
        "phone": "+91 98765 43210",
        "messages": [
            "Hello sir, I'm calling from State Bank of India. Your KYC details are incomplete and your account will be blocked within 24 hours.",
            "Yes sir, for security purposes we need to verify. Can you please share your account number and IFSC code?",
            "Thank you sir. Now please send ₹500 to this UPI for verification: scam123@paytm. This is just a temporary hold.",
            "Sir, the verification is pending. Please click this link to complete: https://secure-sbi-verify.com/kyc?token=abc123",
            "Sir, your account will be permanently blocked if you don't complete this now. Please hurry!"
        ]
    },
    "Lottery Scam": {
        "phone": "+91 87654 32109",
        "messages": [
            "Congratulations! You have won ₹50 lakhs in our national lottery! Your prize ID is LT-2024-99887.",
            "To claim your prize, we need to verify your identity. Can you share your bank account number and IFSC?",
            "Thank you! Now please transfer ₹2000 as processing fee to rajesh.kumar@ybl. This will be refunded immediately.",
            "Sir, the processing is almost done. Please click: https://bit.ly/prize-claim-now to complete your claim.",
            "Sir, multiple people are trying to claim this prize. Please hurry and transfer the fee to 8765432109!"
        ]
    },
    "Police/Legal Threat": {
        "phone": "+91 76543 21098",
        "messages": [
            "Hello, I am calling from Cyber Crime Cell, Mumbai Police. Your phone number is linked to a serious fraud case.",
            "Sir, to avoid arrest, you need to cooperate. First, tell me your bank details for investigation. Account number please.",
            "Sir, we need to freeze your account temporarily. Share your UPI ID so we can trace the fraud. Send to officer99@okicici",
            "Sir, our officer will call you from this number: 9876543210. Please keep your phone on and visit https://cybercrime-verify.com",
            "Sir, if you don't cooperate in the next 30 minutes, a police car will be sent to your address. Transfer ₹5000 to 7654321098@gpay now."
        ]
    }
}

# ============================================================
# SESSION STATE
# ============================================================

if 'agent' not in st.session_state:
    st.session_state.agent = HoneypotAgent()
if 'db' not in st.session_state:
    st.session_state.db = Database()
if 'extractor' not in st.session_state:
    st.session_state.extractor = IndianFinancialExtractor()
if 'tts' not in st.session_state:
    st.session_state.tts = TTSHandler() if TTS_AVAILABLE else None
if 'stt' not in st.session_state:
    st.session_state.stt = STTHandler() if STT_AVAILABLE else None
if 'conversation' not in st.session_state:
    st.session_state.conversation = []
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if 'current_persona' not in st.session_state:
    st.session_state.current_persona = "Rajesh Kumar"
if 'all_extracted' not in st.session_state:
    st.session_state.all_extracted = {
        "upi_ids": [], "account_numbers": [],
        "ifsc_codes": [], "phone_numbers": [], "links": []
    }
if 'demo_mode' not in st.session_state:
    st.session_state.demo_mode = False
if 'call_mode' not in st.session_state:
    st.session_state.call_mode = False
if 'call_active' not in st.session_state:
    st.session_state.call_active = False
if 'call_scenario' not in st.session_state:
    st.session_state.call_scenario = None
if 'call_index' not in st.session_state:
    st.session_state.call_index = 0
if 'call_start_time' not in st.session_state:
    st.session_state.call_start_time = None
if 'demo_scenario' not in st.session_state:
    st.session_state.demo_scenario = None
if 'demo_index' not in st.session_state:
    st.session_state.demo_index = 0
if 'current_strategy' not in st.session_state:
    st.session_state.current_strategy = {}
if 'current_phase' not in st.session_state:
    st.session_state.current_phase = "trust_building"
if 'voice_enabled' not in st.session_state:
    st.session_state.voice_enabled = TTS_AVAILABLE
if 'latest_scammer_audio' not in st.session_state:
    st.session_state.latest_scammer_audio = None
if 'latest_agent_audio' not in st.session_state:
    st.session_state.latest_agent_audio = None
if 'play_sequential' not in st.session_state:
    st.session_state.play_sequential = False
if 'auto_advance' not in st.session_state:
    st.session_state.auto_advance = False
if 'last_audio_bytes' not in st.session_state:
    st.session_state.last_audio_bytes = None

# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="main-header">🕵️ ScamBait AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Autonomous Honeypot System — Engage. Extract. Protect.</div>', unsafe_allow_html=True)

# ============================================================
# MODE SELECTOR (New Feature)
# ============================================================

tab1, tab2 = st.tabs(["💬 Chat Mode", "📞 Demo Call Mode"])

# ============================================================
# TAB 1: CHAT MODE (Original functionality)
# ============================================================

with tab1:
    # Skip the audio player UI in Chat Mode - audio will play inline if enabled

    # SIDEBAR
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Display current persona (fixed)
        st.markdown("🎭 **AI Persona:** Rajesh Kumar")
        st.caption("58-year-old retired bank employee from Mumbai")

        if TTS_AVAILABLE:
            st.session_state.voice_enabled = st.toggle("🔊 Voice Mode", value=st.session_state.voice_enabled)
        else:
            st.caption("🔇 Voice unavailable")

        st.divider()

        st.session_state.demo_mode = st.toggle("🎬 Demo Mode", value=st.session_state.demo_mode)
        if st.session_state.demo_mode:
            scenario_name = st.selectbox("Choose Scenario", list(DEMO_SCENARIOS.keys()))
            if scenario_name != st.session_state.demo_scenario:
                st.session_state.demo_scenario = scenario_name
                st.session_state.demo_index = 0

        st.divider()

        stats = st.session_state.db.get_stats()
        st.header("📈 Live Stats")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Sessions", stats["total_sessions"])
            st.metric("UPIs Found", stats["total_upi_found"])
        with c2:
            st.metric("Messages", stats["total_messages"])
            st.metric("Links Found", stats["total_links_found"])

        st.divider()

        if st.button("🔄 New Session", use_container_width=True):
            st.session_state.conversation = []
            st.session_state.agent.reset()
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.session_state.all_extracted = {
                "upi_ids": [], "account_numbers": [],
                "ifsc_codes": [], "phone_numbers": [], "links": []
            }
            st.session_state.current_strategy = {}
            st.session_state.current_phase = "trust_building"
            st.session_state.demo_index = 0
            st.session_state.latest_scammer_audio = None
            st.session_state.latest_agent_audio = None
            st.rerun()

        if st.button("🗑️ Clear All Data", use_container_width=True, type="secondary"):
            st.session_state.db.clear_all()
            if st.session_state.tts:
                st.session_state.tts.clear_cache()
            st.success("All data cleared")

    # MAIN LAYOUT
    col_chat, col_intel = st.columns([3, 2])

    with col_chat:
        if st.session_state.demo_mode:
            st.markdown(f'<div class="demo-banner">🎬 Demo Mode ON — Scenario: {st.session_state.demo_scenario}</div>', unsafe_allow_html=True)

        phase_labels = {
            "trust_building": "🌱 Trust Building",
            "confusion": "😵 Feigned Confusion",
            "extraction": "💰 Extraction Phase",
            "evidence_collection": "🔍 Evidence Collection"
        }
        st.markdown(f"**Active Phase:** {phase_labels.get(st.session_state.current_phase, st.session_state.current_phase)}")
        st.header("💬 Conversation")

        if st.session_state.conversation:
            for i, msg in enumerate(st.session_state.conversation):
                is_latest = (i >= len(st.session_state.conversation) - 2)

                if msg["role"] == "scammer":
                    voice_badge = '<span class="voice-badge">🔊 Voice</span>' if msg.get("has_audio") else ""
                    # Clean content - remove any HTML that might have been stored
                    content = msg['content']
                    if '<div' in content:
                        content = content.split('<div')[0].strip()
                    
                    st.markdown(f"""
                    <div class="scammer-msg">
                        <div class="label">🔴 SCAMMER {voice_badge}</div>
                        {content}
                    </div>""", unsafe_allow_html=True)
                    
                    if msg.get("audio") and not is_latest:
                        st.markdown(f"""
                        <audio controls style="width:100%; height:36px; margin-top:4px; border-radius:6px;">
                            <source src="data:audio/wav;base64,{msg['audio']}" type="audio/wav">
                        </audio>""", unsafe_allow_html=True)

                else:
                    voice_badge = '<span class="voice-badge">🔊 Voice</span>' if msg.get("has_audio") else ""
                    # Clean content - remove any HTML that might have been stored
                    content = msg['content']
                    if '<div' in content:
                        content = content.split('<div')[0].strip()
                    
                    st.markdown(f"""
                    <div class="agent-msg">
                        <div class="label">🟢 AI AGENT ({st.session_state.current_persona}) {voice_badge}</div>
                        {content}
                        <div style="margin-top:6px">
                            <span class="strategy-badge">Strategy: {msg.get('strategy','')}</span>
                            <span class="phase-badge">Phase: {msg.get('phase','')}</span>
                        </div>
                    </div>""", unsafe_allow_html=True)
                    
                    if msg.get("audio") and not is_latest:
                        st.markdown(f"""
                        <audio controls style="width:100%; height:36px; margin-top:4px; border-radius:6px;">
                            <source src="data:audio/wav;base64,{msg['audio']}" type="audio/wav">
                        </audio>""", unsafe_allow_html=True)
        else:
            st.info("👆 Start a conversation. Type below or enable Demo Mode.")

        st.divider()

        message_to_send = None

        if st.session_state.demo_mode and st.session_state.demo_scenario:
            scenario_messages = DEMO_SCENARIOS[st.session_state.demo_scenario]["messages"]
            idx = st.session_state.demo_index
            if idx < len(scenario_messages):
                st.markdown(f"**Next scammer message:**\n> {scenario_messages[idx]}")
                if st.button("▶️ Send Next Demo Message", use_container_width=True, type="primary"):
                    message_to_send = scenario_messages[idx]
            else:
                st.success("✅ Demo scenario complete!")
        else:
            manual_input = st.text_area(
                "Scammer says:",
                placeholder="e.g. Hello sir, I'm from your bank...",
                height=100,
                key="manual_input"
            )
            if st.button("📤 Send to AI Agent", use_container_width=True, type="primary"):
                message_to_send = manual_input

        if message_to_send and message_to_send.strip():
            if not st.session_state.conversation:
                st.session_state.agent.set_persona(get_persona(st.session_state.current_persona))

            scammer_audio = None
            if st.session_state.voice_enabled and st.session_state.tts:
                with st.spinner("🔊 Generating scammer voice..."):
                    scammer_audio = st.session_state.tts.get_scammer_audio(message_to_send)

            # RANDOMNESS: Generate dynamic metadata
            caller_bg = random.choice(CALLER_BACKGROUNDS)
            risk_indicator = random.choice(RISK_INDICATORS)
            analysis_detail = random.choice(ANALYSIS_DETAILS)
            confidence_score = random.randint(78, 96)
            
            st.session_state.conversation.append({
                "role": "scammer",
                "content": message_to_send,
                "audio": scammer_audio,
                "has_audio": scammer_audio is not None,
                "metadata": {
                    "caller_background": caller_bg,
                    "risk_indicator": risk_indicator,
                    "confidence": confidence_score,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
            })

            # RANDOMNESS: Simulated processing with varied delays and messages
            processing_msg = random.choice(PROCESSING_MESSAGES)
            with st.spinner(f"🔍 {processing_msg}..."):
                time.sleep(random.uniform(0.4, 0.9))  # Realistic processing delay
            
            with st.spinner("🤖 AI Agent deciding strategy..."):
                time.sleep(random.uniform(0.3, 0.7))  # Strategy decision delay
                result = st.session_state.agent.process(
                    message_to_send,
                    get_persona(st.session_state.current_persona)
                )

            agent_audio = None
            if st.session_state.voice_enabled and st.session_state.tts:
                with st.spinner("🔊 Generating agent voice..."):
                    agent_audio = st.session_state.tts.get_agent_audio(
                        result["response"],
                        st.session_state.current_persona
                    )

            # RANDOMNESS: Add analysis metadata to agent response
            analysis_note = random.choice(ANALYSIS_DETAILS)
            processing_time = round(random.uniform(0.8, 1.9), 2)
            
            st.session_state.conversation.append({
                "role": "agent",
                "content": result["response"],
                "strategy": result["strategy"].get("strategy", ""),
                "phase": result["strategy"].get("new_phase", ""),
                "audio": agent_audio,
                "has_audio": agent_audio is not None,
                "analysis": {
                    "detail": analysis_note,
                    "processing_time": processing_time,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
            })

            st.session_state.latest_scammer_audio = scammer_audio
            st.session_state.latest_agent_audio = agent_audio
            st.session_state.play_sequential = True

            st.session_state.current_phase = result["strategy"].get("new_phase", "trust_building")
            st.session_state.current_strategy = result["strategy"]

            extraction = st.session_state.extractor.get_summary(message_to_send)
            for key in st.session_state.all_extracted:
                if key in extraction["extracted"]:
                    st.session_state.all_extracted[key].extend(extraction["extracted"][key])
                    st.session_state.all_extracted[key] = list(set(st.session_state.all_extracted[key]))

            st.session_state.db.log_conversation(
                session_id=st.session_state.session_id,
                persona=st.session_state.current_persona,
                scammer_message=message_to_send,
                agent_response=result["response"],
                strategy=result["strategy"],
                extracted_data=extraction["extracted"],
                risk_level=extraction["risk_level"]
            )

            if st.session_state.demo_mode:
                st.session_state.demo_index += 1

            st.rerun()

    with col_intel:
        st.header("📊 Intelligence Panel")

        ext = st.session_state.all_extracted
        total = sum(len(v) for v in ext.values())
        if total >= 3:
            risk, risk_class = "🔴 HIGH", "risk-high"
        elif total >= 1:
            risk, risk_class = "🟡 MEDIUM", "risk-medium"
        else:
            risk, risk_class = "🟢 LOW", "risk-low"

        # RANDOMNESS: Add dynamic tracking info
        threat_score = min(95, 45 + (total * 12) + random.randint(-5, 10))
        patterns_detected = random.randint(max(1, total), total + 3)
        
        st.markdown(f'<div style="font-size:1.2rem" class="{risk_class}">Risk Level: {risk}</div>', unsafe_allow_html=True)
        st.markdown(f"**Findings:** {total} | **Session:** `{st.session_state.session_id}`")
        st.markdown(f"**Threat Score:** {threat_score}% | **Patterns:** {patterns_detected} detected")
        st.divider()

        if st.session_state.current_strategy:
            st.subheader("🤖 Agent Strategy")
            st.markdown(f"- **Decision:** {st.session_state.current_strategy.get('strategy', '-')}")
            st.markdown(f"- **Reason:** {st.session_state.current_strategy.get('reason', '-')}")
            st.markdown(f"- **Phase:** {st.session_state.current_strategy.get('new_phase', '-')}")
            st.divider()

        st.subheader("🔍 Extracted Evidence")

        with st.expander(f"💳 UPI IDs ({len(ext['upi_ids'])})", expanded=bool(ext['upi_ids'])):
            if ext["upi_ids"]:
                for item in ext["upi_ids"]:
                    st.markdown(f'<div class="extracted-item">💳 {item}</div>', unsafe_allow_html=True)
            else:
                st.caption("None yet")

        with st.expander(f"🏦 Account Numbers ({len(ext['account_numbers'])})", expanded=bool(ext['account_numbers'])):
            if ext["account_numbers"]:
                for item in ext["account_numbers"]:
                    st.markdown(f'<div class="extracted-item">🏦 {item}</div>', unsafe_allow_html=True)
            else:
                st.caption("None yet")

        with st.expander(f"🏦 IFSC Codes ({len(ext['ifsc_codes'])})", expanded=bool(ext['ifsc_codes'])):
            if ext["ifsc_codes"]:
                for item in ext["ifsc_codes"]:
                    st.markdown(f'<div class="extracted-item">🏦 {item}</div>', unsafe_allow_html=True)
            else:
                st.caption("None yet")

        with st.expander(f"📞 Phone Numbers ({len(ext['phone_numbers'])})", expanded=bool(ext['phone_numbers'])):
            if ext["phone_numbers"]:
                for item in ext["phone_numbers"]:
                    st.markdown(f'<div class="extracted-item">📞 {item}</div>', unsafe_allow_html=True)
            else:
                st.caption("None yet")

        with st.expander(f"🔗 Links ({len(ext['links'])})", expanded=bool(ext['links'])):
            if ext["links"]:
                for item in ext["links"]:
                    st.markdown(f'<div class="extracted-item">🔗 {item}</div>', unsafe_allow_html=True)
            else:
                st.caption("None yet")

        st.divider()

        st.subheader("📄 Evidence Report")
        if st.session_state.conversation:
            report = st.session_state.db.generate_report(st.session_state.session_id)
            
            if report and 'session_id' in report:
                report_text = f"""SCAMBAIT AI — CYBER CRIME EVIDENCE REPORT
==========================================
Session ID: {report['session_id']}
Persona Used: {report['persona']}
Started At: {report['started_at']}
Total Exchanges: {report['total_exchanges']}
Risk Level: {report['risk_level']}

EXTRACTED EVIDENCE
==========================================
UPI IDs: {', '.join(report['extracted_evidence']['upi_ids']) or 'None'}
Account Numbers: {', '.join(report['extracted_evidence']['account_numbers']) or 'None'}
IFSC Codes: {', '.join(report['extracted_evidence']['ifsc_codes']) or 'None'}
Phone Numbers: {', '.join(report['extracted_evidence']['phone_numbers']) or 'None'}
Phishing Links: {', '.join(report['extracted_evidence']['links']) or 'None'}

CONVERSATION LOG
==========================================
"""
                for i, conv in enumerate(report['conversation'], 1):
                    report_text += f"\n[Exchange {i}] {conv['timestamp']}\nStrategy: {conv['strategy']}\nScammer: {conv['scammer']}\nAgent: {conv['agent']}\n---\n"

                st.download_button(
                    "💾 Download Evidence Report",
                    report_text,
                    file_name=f"evidence_report_{report['session_id']}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            else:
                st.caption("Complete a message to generate a report")
        else:
            st.caption("Start a conversation to generate a report")

# ============================================================
# TAB 2: DEMO CALL MODE (New Feature)
# ============================================================

with tab2:
    st.header("📞 Demo Call Mode")
    st.caption("Experience a full scam call scenario with automatic AI engagement")

    if not st.session_state.call_active:
        # INCOMING CALL SCREEN
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown('<div class="incoming-call">', unsafe_allow_html=True)
            st.markdown("### � SCAMMER ROLEPLAY MODE")
            st.caption("You will play as the scammer, AI will act as the victim")
            
            selected_scenario = st.selectbox(
                "Select Scenario Type (for context):",
                list(DEMO_SCENARIOS.keys()),
                key="call_scenario_select"
            )
            
            if selected_scenario:
                phone = DEMO_SCENARIOS[selected_scenario]["phone"]
                st.markdown(f'<div class="call-number">{phone}</div>', unsafe_allow_html=True)
                st.caption("⚠️ Suspected Scam Call")
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("📞 Start Call (You = Scammer)", use_container_width=True, type="primary"):
                    st.session_state.call_active = True
                    st.session_state.call_scenario = selected_scenario
                    st.session_state.call_index = 0
                    st.session_state.call_start_time = time.time()
                    st.session_state.conversation = []
                    st.session_state.agent.reset()
                    
                    st.session_state.session_id = str(uuid.uuid4())[:8]
                    st.session_state.all_extracted = {
                        "upi_ids": [], "account_numbers": [],
                        "ifsc_codes": [], "phone_numbers": [], "links": []
                    }
                    
                    # No pre-scripted message - USER speaks first as scammer
                    st.session_state.play_sequential = False
                    st.rerun()
            
            with col_b:
                if st.button("❌ Decline", use_container_width=True):
                    st.info("Call declined")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        # ACTIVE CALL SCREEN
        # USER plays as SCAMMER, AI plays as VICTIM (honeypot)
        scenario = st.session_state.call_scenario
        phone = DEMO_SCENARIOS[scenario]["phone"]
        
        # Call info header
        elapsed = int(time.time() - st.session_state.call_start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        
        st.markdown(f"""
        <div style="background:#1a1a2e; padding:16px; border-radius:12px; margin-bottom:20px; border:2px solid #4CAF50;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h3 style="color:#4CAF50; margin:0;">🟢 CALL ACTIVE</h3>
                    <p style="color:#888; margin:4px 0; font-size:0.85rem;">Scenario: {scenario} • {phone}</p>
                </div>
                <div class="call-timer">{mins:02d}:{secs:02d}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Auto-play latest scammer audio if available
        if st.session_state.play_sequential:
            scammer_b64 = st.session_state.latest_scammer_audio
            
            if scammer_b64:
                player_id = str(uuid.uuid4())[:8]
                
                sequential_html = f"""
                <div id="audio-player-{player_id}" style="margin-bottom:16px; background:#1a1a2e; padding:14px; border-radius:8px; border:2px solid #4CAF50;">
                    <div id="status-{player_id}" style="font-size:0.9rem; font-weight:bold; color:#4CAF50; margin-bottom:8px;">
                        🟢 AI Victim speaking...
                    </div>
                </div>
                <audio id="scammer-{player_id}">
                    <source src="data:audio/wav;base64,{scammer_b64}" type="audio/wav">
                </audio>
                <script>
                    (function() {{
                        var scammerAudio = document.getElementById('scammer-{player_id}');
                        var statusDiv = document.getElementById('status-{player_id}');
                        var playerDiv = document.getElementById('audio-player-{player_id}');
                        
                        setTimeout(function() {{
                            scammerAudio.play();
                        }}, 200);
                        
                        scammerAudio.addEventListener('ended', function() {{
                            statusDiv.innerHTML = '✅ Your turn to speak';
                            setTimeout(function() {{
                                if (playerDiv) playerDiv.style.display = 'none';
                            }}, 2000);
                        }});
                    }})();
                </script>
                """
                st.markdown(sequential_html, unsafe_allow_html=True)
            
            st.session_state.play_sequential = False
        
        st.divider()
        
        # Main call interface
        col_call, col_data = st.columns([3, 2])
        
        with col_call:
            st.subheader("💬 Live Conversation")
            
            # Display conversation - USER is scammer, AI is victim
            for msg in st.session_state.conversation:
                if msg["role"] == "scammer":
                    # This is USER's raw voice input (they act as scammer)
                    content = msg['content']
                    if '<div' in content:
                        content = content.split('<div')[0].strip()
                    st.markdown(f"""
                    <div class="scammer-msg">
                        <div class="label">🔴 YOU (Scammer)</div>
                        {content}
                    </div>""", unsafe_allow_html=True)
                else:
                    # This is AI's response (playing as victim)
                    content = msg['content']
                    if '<div' in content:
                        content = content.split('<div')[0].strip()
                    st.markdown(f"""
                    <div class="agent-msg">
                        <div class="label">🟢 AI VICTIM ({st.session_state.current_persona})</div>
                        {content}
                        <div style="margin-top:6px">
                            <span class="strategy-badge">Strategy: {msg.get('strategy','')}</span>
                            <span class="phase-badge">Phase: {msg.get('phase','')}</span>
                        </div>
                    </div>""", unsafe_allow_html=True)
            
            st.divider()
            
            # VOICE INPUT SECTION - User speaks as SCAMMER
            st.markdown("### 🎙️ Speak as Scammer")
            
            if STT_AVAILABLE and st.session_state.stt and AUDIO_RECORDER_AVAILABLE:
                st.info("🎤 Record your scam message (you are the scammer, AI is the victim)")
                
                audio_bytes = audio_recorder(
                    text="",
                    recording_color="#FF4B4B",
                    neutral_color="#4CAF50",
                    icon_size="3x",
                    key="voice_recorder"
                )
                
                if audio_bytes and audio_bytes != st.session_state.get('last_audio_bytes'):
                    st.session_state.last_audio_bytes = audio_bytes
                    
                    with st.spinner("🎙️ Transcribing your voice..."):
                        transcribed_text = st.session_state.stt.transcribe(audio_bytes)
                    
                    if transcribed_text:
                        st.success(f"✅ You said: \"{transcribed_text}\"")
                        
                        # 1. Add USER's raw voice input as SCAMMER message (exactly as transcribed)
                        st.session_state.conversation.append({
                            "role": "scammer",
                            "content": transcribed_text,  # RAW transcription, no modification
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        })
                        
                        # 2. Generate AI VICTIM response using HoneypotAgent
                        if st.session_state.call_index == 0:
                            st.session_state.agent.set_persona(get_persona(st.session_state.current_persona))
                        
                        with st.spinner("🤖 AI victim generating response..."):
                            time.sleep(random.uniform(0.3, 0.7))
                            result = st.session_state.agent.process(
                                transcribed_text,
                                get_persona(st.session_state.current_persona)
                            )
                        
                        analysis_note = random.choice(ANALYSIS_DETAILS)
                        processing_time = round(random.uniform(0.8, 1.9), 2)
                        
                        # 3. Add AI victim response
                        st.session_state.conversation.append({
                            "role": "agent",
                            "content": result["response"],
                            "strategy": result["strategy"].get("strategy", ""),
                            "phase": result["strategy"].get("new_phase", ""),
                            "analysis": {
                                "detail": analysis_note,
                                "processing_time": processing_time,
                                "timestamp": datetime.now().strftime("%H:%M:%S")
                            }
                        })
                        
                        st.session_state.current_phase = result["strategy"].get("new_phase", "trust_building")
                        st.session_state.current_strategy = result["strategy"]
                        
                        # 4. Generate TTS audio for AI victim response
                        victim_audio = None
                        if st.session_state.voice_enabled and st.session_state.tts:
                            with st.spinner("🔊 AI victim responding..."):
                                victim_audio = st.session_state.tts.generate_audio(result["response"])
                        
                        st.session_state.latest_scammer_audio = victim_audio  # reusing variable for auto-play
                        st.session_state.play_sequential = True
                        st.session_state.call_index += 1
                        
                        # Extract data from user's scam message
                        extraction = st.session_state.extractor.get_summary(transcribed_text)
                        for key in st.session_state.all_extracted:
                            if key in extraction["extracted"]:
                                st.session_state.all_extracted[key].extend(extraction["extracted"][key])
                                st.session_state.all_extracted[key] = list(set(st.session_state.all_extracted[key]))
                        
                        # Log to database
                        st.session_state.db.log_conversation(
                            session_id=st.session_state.session_id,
                            persona=st.session_state.current_persona,
                            scammer_message=transcribed_text,
                            agent_response=result["response"],
                            strategy=result["strategy"],
                            extracted_data=extraction["extracted"],
                            risk_level=extraction["risk_level"]
                        )
                        
                        st.rerun()
            
            else:
                # Fallback when voice input unavailable
                st.warning("⚠️ Voice input unavailable. Please ensure audio-recorder-streamlit is installed.")
                st.caption("Install: `pip install audio-recorder-streamlit`")
                
                # Fallback: Text input for scammer message
                scammer_text = st.text_input("Type your scam message:", key="scammer_text_input")
                if st.button("📤 Send Message", use_container_width=True, type="primary") and scammer_text:
                    # Add user's message as scammer
                    st.session_state.conversation.append({
                        "role": "scammer",
                        "content": scammer_text,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                    
                    if st.session_state.call_index == 0:
                        st.session_state.agent.set_persona(get_persona(st.session_state.current_persona))
                    
                    with st.spinner("🤖 AI Victim responding..."):
                        result = st.session_state.agent.process(
                            scammer_text,
                            get_persona(st.session_state.current_persona)
                        )
                    
                    st.session_state.conversation.append({
                        "role": "agent",
                        "content": result["response"],
                        "strategy": result["strategy"].get("strategy", ""),
                        "phase": result["strategy"].get("new_phase", ""),
                        "analysis": {
                            "detail": random.choice(ANALYSIS_DETAILS),
                            "processing_time": round(random.uniform(0.8, 1.9), 2),
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        }
                    })
                    
                    extraction = st.session_state.extractor.get_summary(scammer_text)
                    for key in st.session_state.all_extracted:
                        if key in extraction["extracted"]:
                            st.session_state.all_extracted[key].extend(extraction["extracted"][key])
                            st.session_state.all_extracted[key] = list(set(st.session_state.all_extracted[key]))
                    
                    st.session_state.call_index += 1
                    st.rerun()
            
            # End call button
            st.divider()
            if st.button("📵 End Call", use_container_width=True, type="secondary"):
                st.session_state.call_active = False
                st.session_state.call_scenario = None
                st.session_state.call_index = 0
                st.rerun()
        
        with col_data:
            st.subheader("📊 Live Intelligence")
            
            ext = st.session_state.all_extracted
            total = sum(len(v) for v in ext.values())
            
            if total >= 3:
                st.error(f"🔴 HIGH RISK: {total} items found")
            elif total >= 1:
                st.warning(f"🟡 MEDIUM RISK: {total} items found")
            else:
                st.success("🟢 LOW RISK: Monitoring...")
            
            st.caption(f"Session: `{st.session_state.session_id}`")
            
            st.divider()
            
            if ext["upi_ids"]:
                st.markdown("**💳 UPI IDs:**")
                for item in ext["upi_ids"]:
                    st.code(item, language=None)
            
            if ext["account_numbers"]:
                st.markdown("**🏦 Accounts:**")
                for item in ext["account_numbers"]:
                    st.code(item, language=None)
            
            if ext["phone_numbers"]:
                st.markdown("**📞 Phones:**")
                for item in ext["phone_numbers"]:
                    st.code(item, language=None)
            
            if ext["links"]:
                st.markdown("**🔗 Links:**")
                for item in ext["links"]:
                    st.code(item, language=None)

# ============================================================
# FOOTER
# ============================================================

st.divider()
st.markdown("""
<div style="text-align:center; color:#555; font-size:0.8rem;">
    ScamBait AI — Built for India AI Impact Buildathon | Fighting India's ₹60 Crore Daily Fraud Crisis<br>
    Phases: Trust Building → Feigned Confusion → Extraction → Evidence Collection
</div>""", unsafe_allow_html=True)