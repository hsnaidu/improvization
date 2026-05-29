"""
ACT0010 — Abrupt Call Detection Tool
Fires when the call is disconnected or incomplete mid-conversation.
"""

from typing import Optional
from pydantic import Field
from .._base import BaseActionResult, run_tool

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ACT0010Result(BaseActionResult):
    action_id: str = Field(default="ACT0010")
    action_type: str = Field(default="Abrupt Call")
    call_abrupt: bool = Field(default=False)
    notes: str = Field(default="")
    description: Optional[str] = None

# ---------------------------------------------------------------------------
# Specialist system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a specialist extraction agent for collections call analysis.
Your ONLY job: detect and extract ACT0010 — Abrupt Call Disconnection.

## DEFINITION:
A call is ABRUPT if the CONVERSATION/DISCUSSION is INCOMPLETE in the TRANSCRIPT:
  * Required topic/discussion is CUT OFF mid-way (not farewell, but actual conversation)
  * Agent's response to customer query cuts off unexpectedly
  * Important business logic/content appears MISSING from the transcript
  * Conversation jumps topics or has unexplained gaps
  
A call is NOT ABRUPT if:
  * The conversation logic/discussion is COMPLETE (even if agent reached voicemail, refused call, etc.)
  * Only the final FAREWELL/GOODBYE is cut off (acceptable - agent ending the call)
  * Conversation reached a conclusion and transcript shows agent explicitly ending ("I'll hang up now", "Thanks, goodbye", etc.)
  * All key exchanges that needed to happen are present in transcript

## CRITICAL: 
- Sentence cutoffs on FAREWELL/GOODBYE messages ≠ Abrupt (agent is clearly ending call)
- Sentence cutoffs on MIDDLE OF DISCUSSION ≠ Abrupt (topic cut off unexpectedly)
- Missing conversation content/logic in middle of exchange = Abrupt

## STEP-BY-STEP ANALYSIS:

1. **Check if conversation reached a conclusion:**
   - Did agent acknowledge situation and make ending statement? ("I'll hang up now", "I'll follow up", "Thank you", etc.)
   - Is the last exchange a farewell/ending, even if words cut off?
   - If YES → Conversation is COMPLETE

2. **Check for missing content BEFORE the ending:**
   - Are there gaps in the middle of conversation?
   - Does discussion jump unexpectedly?
   - Is customer's response to key question completely missing?
   - If YES → Conversation is INCOMPLETE

3. **Abrupt Detection Decision:**
   - If conversation logic is COMPLETE and only farewell cuts off → NOT ABRUPT (call_abrupt=false)
   - If conversation is CUT OFF mid-discussion before reaching conclusion → ABRUPT (call_abrupt=true)

## If found=true:
  * Set call_abrupt=true
  * Provide description with: topics discussed + specific evidence (e.g., "Discussed payment. ABRUPT because: agent's response to customer's question about reference number cuts off mid-sentence with no follow-up.")

## If criteria not met → found=false, call_abrupt=false, description=null."""

_OUTPUT_FIELDS = ["action_id", "action_type", "call_abrupt", "notes", "description"]
_DEFAULTS = {"notes": ""}

# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run(user_name: str, transcript: str) -> Optional[dict]:
    """Returns a strict-field dict for ACT0010 if found, else None."""
    return await run_tool(ACT0010Result, SYSTEM_PROMPT, user_name, transcript, _OUTPUT_FIELDS, _DEFAULTS)
