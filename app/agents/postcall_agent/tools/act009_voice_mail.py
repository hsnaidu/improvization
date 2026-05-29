"""
ACT009 — Voice Mail Detection Tool
Fires when the call reaches a voicemail system or automated response.
"""

from typing import Optional
from pydantic import Field
from .._base import BaseActionResult, run_tool

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ACT009Result(BaseActionResult):
    action_id: str = Field(default="ACT009")
    action_type: str = Field(default="Voice Mail")
    notes: str = Field(default="")
    description: Optional[str] = None

# ---------------------------------------------------------------------------
# Specialist system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a specialist extraction agent for collections call analysis.
Your ONLY job: detect and extract ACT009 — Voice Mail.

## STRICT RULES:
- FIRE (found=true) ONLY when the agent reached a voicemail system, automated response, or IVR (Interactive Voice Response).
- Indicators of voicemail:
  * Repeated voicemail prompts ("Please choose an option", "To send the message, just hang up", etc.)
  * Agent saying "It seems like I've reached a voicemail", "This call went to voicemail", "I'll follow up"
  * No actual human conversation or minimal interaction with a human
  * Robotic/automated responses from the other party
  
- DO NOT fire if there was a real human conversation, even if brief.
- DO NOT fire for legitimate call disconnections or wrong numbers.

## OUTPUT INSTRUCTIONS:
If criteria not met → found=false, description=null.

If found=true (voice mail detected):
  * Populate description with a summary of what happened during the voicemail interaction."""

_OUTPUT_FIELDS = ["found" ,"action_id", "action_type", "notes", "description"]
_DEFAULTS = {"notes": ""}

# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run(user_name: str, transcript: str) -> Optional[dict]:
    """Returns a strict-field dict for ACT009 if found, else None."""
    return await run_tool(ACT009Result, SYSTEM_PROMPT, user_name, transcript, _OUTPUT_FIELDS, _DEFAULTS)

