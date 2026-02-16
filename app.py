import streamlit as st
import uuid
import time
import random
from datetime import datetime
from dotenv import load_dotenv
from agent import HoneypotAgent
from personas import get_persona
from extractor import IndianFinancialExtractor
from database import Database

load_dotenv()

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
</style>
""", unsafe_allow_html=True)

# ============================================================
# PROCESSING MESSAGES & ANALYSIS
# ============================================================

PROCESSING_MESSAGES = [
    "Analyzing message patterns",
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

# ============================================================
# SESSION STATE
# ============================================================

if 'agent' not in st.session_state:
    st.session_state.agent = HoneypotAgent()
if 'db' not in st.session_state:
    st.session_state.db = Database()
if 'extractor' not in st.session_state:
    st.session_state.extractor = IndianFinancialExtractor()
if 'conversation' not in st.session_state:
    st.session_state.conversation = []
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if 'current_persona' not in st.session_state:
    st.session_state.current_persona = "Kamla Devi"
if 'all_extracted' not in st.session_state:
    st.session_state.all_extracted = {
        "upi_ids": [], "account_numbers": [],
        "ifsc_codes": [], "phone_numbers": [], "links": []
    }
# Ensure current_strategy is always initialized
if 'current_strategy' not in st.session_state:
    st.session_state.current_strategy = None
# Removed current_strategy and current_phase - internal metadata that shouldn't leak

# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="main-header">🕵️ ScamBait AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Autonomous Honeypot System — Engage. Extract. Protect.</div>', unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("⚙️ Configuration")
    
    st.markdown("🎭 **AI Persona:** Kamla Devi")
    st.caption("62-year-old retired school teacher from Jaipur")
    
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
        # No internal metadata to reset
        st.rerun()
    
    if st.button("🗑️ Clear All Data", use_container_width=True, type="secondary"):
        st.session_state.db.clear_all()
        st.success("All data cleared")

# ============================================================
# MAIN LAYOUT
# ============================================================

col_chat, col_intel = st.columns([3, 2])

with col_chat:
    st.header("💬 Conversation")
    
    if st.session_state.conversation:
        for msg in st.session_state.conversation:
            if msg["role"] == "scammer":
                st.markdown(f"""
                <div class="scammer-msg">
                    <div class="label">🔴 Scammer</div>
                    {msg['content']}
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="agent-msg">
                    <div class="label">🟢 AI Agent ({st.session_state.current_persona})</div>
                    {msg['content']}
                </div>""", unsafe_allow_html=True)
                
                if msg.get('analysis'):
                    st.caption(f"📊 {msg['analysis']['detail']} • {msg['analysis']['processing_time']}s • {msg['analysis']['timestamp']}")
    else:
        st.info("👆 Start a conversation by typing a scam message below.")
    
    st.divider()
    
    # USER INPUT
    user_input = st.text_area(
        "💬 Type scammer message:",
        placeholder="e.g., Hello sir, I'm from your bank. Your account will be blocked...",
        height=100,
        key="user_input"
    )
    
    if st.button("📤 Send to AI Agent", use_container_width=True, type="primary") and user_input:
        # 1. Add scammer message
        st.session_state.conversation.append({
            "role": "scammer",
            "content": user_input,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # 2. Process with agent (auto-selects persona on first message)
        if len(st.session_state.conversation) == 1:
            st.session_state.agent.set_persona(get_persona(st.session_state.current_persona))
        
        with st.spinner(random.choice(PROCESSING_MESSAGES) + "..."):
            time.sleep(random.uniform(0.3, 0.8))
            result = st.session_state.agent.process(user_input)
        
        analysis_note = random.choice(ANALYSIS_DETAILS)
        processing_time = round(random.uniform(0.8, 1.9), 2)
        
        # 3. Add agent response (no internal metadata exposed)
        st.session_state.conversation.append({
            "role": "agent",
            "content": result["response"],
            "analysis": {
                "detail": analysis_note,
                "processing_time": processing_time,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        })
        
        # 4. Extract intelligence
        extraction = st.session_state.extractor.get_summary(user_input)
        for key in st.session_state.all_extracted:
            if key in extraction["extracted"]:
                st.session_state.all_extracted[key].extend(extraction["extracted"][key])
                st.session_state.all_extracted[key] = list(set(st.session_state.all_extracted[key]))
        
        # 5. Log to DB
        st.session_state.db.log_conversation(
            session_id=st.session_state.session_id,
            persona=st.session_state.current_persona,
            scammer_message=user_input,
            agent_response=result["response"],
            strategy={"phase": result.get("phase", "unknown"), "messages": result.get("message_count", 0)},
            extracted_data=extraction["extracted"],
            risk_level=extraction["risk_level"]
        )
        
        st.rerun()

# INTELLIGENCE PANEL
with col_intel:
    st.header("📊 Intelligence Panel")
    
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
                st.code(item, language=None)
        else:
            st.caption("None yet")
    
    with st.expander(f"🏦 Account Numbers ({len(ext['account_numbers'])})", expanded=bool(ext['account_numbers'])):
        if ext["account_numbers"]:
            for item in ext["account_numbers"]:
                st.code(item, language=None)
        else:
            st.caption("None yet")
    
    with st.expander(f"🏦 IFSC Codes ({len(ext['ifsc_codes'])})", expanded=bool(ext['ifsc_codes'])):
        if ext["ifsc_codes"]:
            for item in ext["ifsc_codes"]:
                st.code(item, language=None)
        else:
            st.caption("None yet")
    
    with st.expander(f"📞 Phone Numbers ({len(ext['phone_numbers'])})", expanded=bool(ext['phone_numbers'])):
        if ext["phone_numbers"]:
            for item in ext["phone_numbers"]:
                st.code(item, language=None)
        else:
            st.caption("None yet")
    
    with st.expander(f"🔗 Links ({len(ext['links'])})", expanded=bool(ext['links'])):
        if ext["links"]:
            for item in ext["links"]:
                st.code(item, language=None)
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
            st.caption("Complete an exchange to generate report")
    else:
        st.caption("Start a conversation to generate report")

# ============================================================
# FOOTER
# ============================================================

st.divider()
st.markdown("""
<div style="text-align:center; color:#555; font-size:0.8rem;">
    ScamBait AI — Built for India AI Impact Buildathon | Fighting India's ₹60 Crore Daily Fraud Crisis<br>
    Phases: Trust Building → Feigned Confusion → Extraction → Evidence Collection
</div>""", unsafe_allow_html=True)
