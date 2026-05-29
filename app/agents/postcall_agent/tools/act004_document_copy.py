"""
ACT004 — DocumentCopy Tool
Fires when the customer requests that a document be sent to them via any channel.
"""

from typing import List, Optional
from pydantic import Field
from .._base import BaseActionResult, run_tool

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ACT004Result(BaseActionResult):
    action_id: str = Field(default="ACT004")
    action_type: str = Field(default="DocumentCopy")
    notes: Optional[str] = None
    description: Optional[str] = None
    documents_requested: Optional[List[str]] = None
    document_type: Optional[str] = None
    delivery_channel: Optional[str] = None

# ---------------------------------------------------------------------------
# Specialist system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a specialist extraction agent for collections call analysis.
Your ONLY job: detect and extract ACT004 — DocumentCopy.

## STRICT RULES:
- FIRE (found=true) when the customer REQUESTS that a document be SENT to them (via email, post, or any channel).
- Examples: "Can you send me that invoice to my email?", "Send me the receipt", "Email me the statement."
- IMPORTANT: Based on the CUSTOMER'S REQUEST — not whether the agent fulfilled it.
  Even if the agent says "I cannot send it", the customer's request MUST still be ACT004.
- SEPARATE from ACT008: if the customer asks ABOUT their invoice number (ACT008) and THEN asks to have it emailed (ACT004), these are two separate actions — only capture the send/email request here.
- Default delivery_channel to 'Email' unless another channel is specified.
- Populate documents_requested as a list of each specific document mentioned.

If no document send request is present → found=false, all other fields null."""

_OUTPUT_FIELDS = ["action_id", "action_type", "notes", "description",
                  "documents_requested", "document_type", "delivery_channel"]
_DEFAULTS = {"delivery_channel": "Email"}

# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run(user_name: str, transcript: str) -> Optional[dict]:
    """Returns a strict-field dict for ACT004 if found, else None."""
    return await run_tool(ACT004Result, SYSTEM_PROMPT, user_name, transcript, _OUTPUT_FIELDS, _DEFAULTS)
