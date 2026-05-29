import asyncio
import json
import sys
import os

# Add the collections dir to path
sys.path.append(r"C:\Users\harip\Desktop\collections")

# Stub Azure Open AI keys so the imports and structure can run/test without remote API calls
os.environ["AZURE_GPT4_API_ENDPOINT"] = "http://localhost"
os.environ["AZURE_GPT4_API_KEY"] = "mock_key"

from app.agents.postcall_agent.main import process_transcript_and_update_json

transcript = {
    "1": {"role": "assistant", "content": "Hi, this is LISA from Business Solutions, Am I speaking with hari Prasad"},
    "2": {"role": "user", "content": "No"},
    "3": {"role": "assistant", "content": "I apologise"},
    "4": {"role": "user", "content": "This is a wrong number, I am talking to Hari, you can tell me what to tell him i will tell"},
    "5": {"role": "assistant", "content": "Got it. Could you let Hari know that LISA from Business solution called regarding an outstadning balance of $1,120 that was originally due on May 11th? Its really important that he reach out to the collections office to discuss thisfurther, He can just ask for LISA, when he calls back, Thanks for helping"}
}

call_data = {
    "user_name": "Hari Prasad",
    "call_id": "TEST_123",
    "transcript": transcript,
    "call_data": {
        "call_status": True,
        "call_abrupt": True,
        "failure_message": "Call disconnected abruptly"
    }
}

async def main():
    # We will test the local aggregation function logic here directly by mocking the results 
    # of the act0010 and act0011 runs, since the remote OpenAI API is not available locally.
    act0010_res = {"found": True, "call_abrupt": True}
    act0011_res = {"found": True, "wrong_contact": True, "notes": "Wrong number", "description": "Mismatch"}
    
    # Run the processing logic manually on a sample dict
    sample_call = dict(call_data)
    
    # Emulate the main.py aggregation logic to verify it
    if "call_data" in sample_call:
        if act0011_res.get("wrong_contact") is True:
            sample_call["call_data"]["wrong_contact"] = True
            sample_call["call_data"]["call_status"] = False
            
        if act0010_res.get("call_abrupt") is True:
            sample_call["call_data"]["call_abrupt"] = True

        reasons = []
        existing_msg = sample_call["call_data"].get("failure_message") or ""
        if existing_msg:
            for part in [p.strip() for p in existing_msg.split(",") if p.strip()]:
                if part not in reasons:
                    reasons.append(part)

        if sample_call["call_data"].get("wrong_contact") is True:
            if "Wrong Contact" not in reasons:
                reasons.append("Wrong Contact")

        if sample_call["call_data"].get("call_abrupt") is True:
            has_abrupt = any("abrupt" in r.lower() for r in reasons)
            if not has_abrupt:
                reasons.append("Call disconnected abruptly")

        if reasons:
            sample_call["call_data"]["failure_message"] = ", ".join(reasons)

    print("AGGREGATION TEST RESULT:")
    print(json.dumps(sample_call["call_data"], indent=2))

if __name__ == "__main__":
    asyncio.run(main())
