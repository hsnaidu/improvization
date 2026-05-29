import asyncio
import json
import sys
import os

# Add the collections dir to path
sys.path.append(r"C:\Users\harip\Desktop\collections")

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
        "failure_message": ""
    }
}

async def main():
    result = await process_transcript_and_update_json(call_data)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
