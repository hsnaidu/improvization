"""
ACT006 — DoubtfulReceivable Tool
Fires when the customer says they CANNOT or WILL NOT make any payment.
Must ALWAYS be fired first and coexist with other actions when initial refusal is present.
"""

from typing import Optional
from pydantic import Field
from .._base import BaseActionResult, run_tool

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ACT006Result(BaseActionResult):
    action_id: str = Field(default="ACT006")
    action_type: str = Field(default="DoubtfulReceivable")
    notes: Optional[str] = None
    description: Optional[str] = None
    settlement_amount: Optional[float] = None
    settlement_due_date: Optional[str] = None

# ---------------------------------------------------------------------------
# Specialist system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a specialist extraction agent for collections call analysis.
Your ONLY job: detect and extract ACT006 — DoubtfulReceivable.

## STRICT RULES:
- FIRE (found=true) whenever a customer says they CANNOT or WILL NOT make any payment.
- Trigger phrases: "I won't be able to make that payment", "I cannot pay", "I refuse to pay",
  "I have financial issues and cannot pay", "I'm not able to pay anything right now."
- CRITICAL: Even if the customer LATER agrees to a callback, negotiation, or credit discussion,
  you MUST STILL fire ACT006 for the initial refusal. It coexists with ACT007/ACT002 etc.
- Populate settlement_amount if a negotiated settlement figure is discussed.
- Populate settlement_due_date if a settlement deadline is mentioned.

If no refusal or inability-to-pay is present → found=false, all other fields null."""

_OUTPUT_FIELDS = ["action_id", "action_type", "notes", "description",
                  "settlement_amount", "settlement_due_date"]

# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run(user_name: str, transcript: str) -> Optional[dict]:
    """Returns a strict-field dict for ACT006 if found, else None."""
    return await run_tool(ACT006Result, SYSTEM_PROMPT, user_name, transcript, _OUTPUT_FIELDS)
