import requests
import uuid
import json
from datetime import datetime

# Your API configuration
ENDPOINT_URL = "https://scambait-api.onrender.com/api/honeypot"
API_KEY = "scambait-secure-key-2026-hackathon"  # Optional

# Test scenario
test_scenario = {
    'scenarioId': 'bank_fraud',
    'name': 'Bank Fraud Detection',
    'scamType': 'bank_fraud',
    'initialMessage': 'URGENT: Your SBI account has been compromised. Your account will be blocked in 2 hours. Share your account number and OTP immediately to verify your identity.',
    'metadata': {
        'channel': 'SMS',
        'language': 'English',
        'locale': 'IN'
    },
    'maxTurns': 10,
    'fakeData': {
        'bankAccount': '1234567890123456',
        'upiId': 'scammer.fraud@fakebank',
        'phoneNumber': '+91-9876543210'
    }
}

# Simulated scammer follow-ups that contain fake data (mimics what the real evaluator AI would generate)
SCAMMER_FOLLOWUPS = [
    # Turn 2: Share phone number
    "I am calling from SBI fraud department. My ID is SBI-12345. Call me back at +91-9876543210 if you don't believe me.",
    # Turn 3: Push urgency
    "Ma'am your account 1234567890123456 has been flagged for suspicious activity. We need to verify immediately!",
    # Turn 4: Share UPI
    "Please send Rs. 1 to scammer.fraud@fakebank for verification. This is standard SBI procedure.",
    # Turn 5: Push harder  
    "Time is running out! Your account will be permanently blocked. Send OTP to +91-9876543210 now!",
    # Turn 6: Threaten
    "Ma'am if you don't cooperate, we will have to file a police complaint. Send verification fee to scammer.fraud@fakebank",
    # Turn 7: Pretend to be helpful
    "I understand your concern. You can verify by calling +91-9876543210. I am senior manager Rajesh.",
    # Turn 8: Final push
    "This is your last warning. Account 1234567890123456 will be suspended. Transfer Rs 5000 to scammer.fraud@fakebank immediately.",
    # Turn 9: Emotional manipulation
    "Ma'am your life savings are at risk. Please cooperate. My direct number is +91-9876543210.",
]

def test_honeypot_api():
    """Test your honeypot API endpoint"""
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    conversation_history = []
    
    # Setup headers
    headers = {'Content-Type': 'application/json'}
    if API_KEY:
        headers['x-api-key'] = API_KEY
    
    print(f"Testing Session: {session_id}")
    print("=" * 60)
    
    last_response_data = None
    
    # Simulate conversation turns (fully automated)
    for turn in range(1, test_scenario['maxTurns'] + 1):
        print(f"\n--- Turn {turn} ---")
        
        # First turn: use initial message; rest: use pre-scripted follow-ups
        if turn == 1:
            scammer_message = test_scenario['initialMessage']
        else:
            followup_idx = turn - 2  # 0-indexed into SCAMMER_FOLLOWUPS
            if followup_idx < len(SCAMMER_FOLLOWUPS):
                scammer_message = SCAMMER_FOLLOWUPS[followup_idx]
            else:
                scammer_message = "Please hurry up ma'am, your account is about to be blocked permanently!"
        
        # Prepare message object
        message = {
            "sender": "scammer",
            "text": scammer_message,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        # Prepare request
        request_body = {
            'sessionId': session_id,
            'message': message,
            'conversationHistory': conversation_history,
            'metadata': test_scenario['metadata']
        }
        
        print(f"Scammer: {scammer_message}")
        
        try:
            # Call your API
            response = requests.post(
                ENDPOINT_URL,
                headers=headers,
                json=request_body,
                timeout=30
            )
            
            # Check response
            if response.status_code != 200:
                print(f"❌ ERROR: API returned status {response.status_code}")
                print(f"Response: {response.text}")
                break
            
            response_data = response.json()
            
            # Extract honeypot reply
            honeypot_reply = response_data.get('reply') or \
                           response_data.get('message') or \
                           response_data.get('text')
            
            if not honeypot_reply:
                print("❌ ERROR: No reply/message/text field in response")
                print(f"Response data: {response_data}")
                break
            
            print(f"✅ Honeypot: {honeypot_reply}")
            
            # Store full response for final scoring
            last_response_data = response_data
            
            # Update conversation history
            conversation_history.append(message)
            conversation_history.append({
                'sender': 'user',
                'text': honeypot_reply,
                'timestamp': datetime.utcnow().isoformat() + "Z"
            })
            
        except requests.exceptions.Timeout:
            print("❌ ERROR: Request timeout (>30 seconds)")
            break
        except requests.exceptions.ConnectionError as e:
            print(f"❌ ERROR: Connection failed - {e}")
            break
        except Exception as e:
            print(f"❌ ERROR: {e}")
            break
    
    # Test final output structure (use actual API response, not hardcoded)
    print("\n" + "=" * 60)
    print("Final output from API (last response):")
    print("=" * 60)
    
    if last_response_data:
        print(json.dumps(last_response_data, indent=2))
        
        # Build final_output from the actual API response
        final_output = {
            "sessionId": session_id,
            "status": last_response_data.get("status", "success"),
            "scamDetected": last_response_data.get("scamDetected", False),
            "totalMessagesExchanged": last_response_data.get("messagesExchanged", 0),
            "extractedIntelligence": last_response_data.get("extractedIntelligence", {}),
            "engagementMetrics": last_response_data.get("engagementMetrics", {}),
            "agentNotes": last_response_data.get("agentNotes", "")
        }
    else:
        print("❌ No response data available")
        return None
    
    # Evaluate the final output
    score = evaluate_final_output(final_output, test_scenario, conversation_history)
    
    print(f"\n📊 Your Score: {score['total']}/100")
    print(f"   - Scam Detection: {score['scamDetection']}/20")
    print(f"   - Intelligence Extraction: {score['intelligenceExtraction']}/40")
    print(f"   - Engagement Quality: {score['engagementQuality']}/20")
    print(f"   - Response Structure: {score['responseStructure']}/20")
    
    return score

def evaluate_final_output(final_output, scenario, conversation_history):
    """Evaluate final output using the same logic as the evaluator"""
    
    score = {
        'scamDetection': 0,
        'intelligenceExtraction': 0,
        'engagementQuality': 0,
        'responseStructure': 0,
        'total': 0
    }
    
    # 1. Scam Detection (20 points)
    if final_output.get('scamDetected', False):
        score['scamDetection'] = 20
    
    # 2. Intelligence Extraction (40 points)
    extracted = final_output.get('extractedIntelligence', {})
    fake_data = scenario.get('fakeData', {})
    
    key_mapping = {
        'bankAccount': 'bankAccounts',
        'upiId': 'upiIds',
        'phoneNumber': 'phoneNumbers',
        'phishingLink': 'phishingLinks',
        'emailAddress': 'emailAddresses'
    }
    
    for fake_key, fake_value in fake_data.items():
        output_key = key_mapping.get(fake_key, fake_key)
        extracted_values = extracted.get(output_key, [])
        
        if isinstance(extracted_values, list):
            if any(fake_value in str(v) for v in extracted_values):
                score['intelligenceExtraction'] += 10
        elif isinstance(extracted_values, str):
            if fake_value in extracted_values:
                score['intelligenceExtraction'] += 10
    
    score['intelligenceExtraction'] = min(score['intelligenceExtraction'], 40)
    
    # 3. Engagement Quality (20 points)
    metrics = final_output.get('engagementMetrics', {})
    duration = metrics.get('engagementDurationSeconds', 0)
    messages = metrics.get('totalMessagesExchanged', 0)
    
    if duration > 0:
        score['engagementQuality'] += 5
    if duration > 60:
        score['engagementQuality'] += 5
    if messages > 0:
        score['engagementQuality'] += 5
    if messages >= 5:
        score['engagementQuality'] += 5
    
    # 4. Response Structure (20 points)
    required_fields = ['status', 'scamDetected', 'extractedIntelligence']
    optional_fields = ['engagementMetrics', 'agentNotes']
    
    for field in required_fields:
        if field in final_output:
            score['responseStructure'] += 5
    
    for field in optional_fields:
        if field in final_output and final_output[field]:
            score['responseStructure'] += 2.5
    
    score['responseStructure'] = min(score['responseStructure'], 20)
    
    # Calculate total
    score['total'] = sum([
        score['scamDetection'],
        score['intelligenceExtraction'],
        score['engagementQuality'],
        score['responseStructure']
    ])
    
    return score

# Run the test
if __name__ == "__main__":
    test_honeypot_api()
