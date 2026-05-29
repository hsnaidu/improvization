"""
ACT005 — PartialPayment Tool
Fires when the customer commits to paying a specific amount LESS than the full balance.
"""

from typing import Optional
from pydantic import Field
from .._base import BaseActionResult, run_tool

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ACT005Result(BaseActionResult):
    action_id: str = Field(default="ACT005")
    action_type: str = Field(default="PartialPayment")
    amount: Optional[float] = None
    date: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    payment_method: Optional[str] = None

# ---------------------------------------------------------------------------
# Specialist system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a specialist extraction agent for collections call analysis.
Your ONLY job: detect and extract ACT005 — PartialPayment.

## STRICT RULES:
- FIRE (found=true) when the customer commits to paying a SPECIFIC AMOUNT that is LESS than the full outstanding balance.
- Examples: "I'll send $50 today", "I can pay $200 by end of week."
- ACT005 ALWAYS takes priority over ACT001 (PromiseToPay) when the amount is partial.
- Populate amount with the specific amount mentioned.
- Populate date if the customer specifies when they will make the partial payment.
- Populate payment_method if mentioned (e.g., Bank Transfer, UPI, Credit Card, Check).

If no partial payment commitment is present → found=false, all other fields null."""

_OUTPUT_FIELDS = ["action_id", "action_type", "amount", "date", "notes", "description", "payment_method"]

# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run(user_name: str, transcript: str) -> Optional[dict]:
    """Returns a strict-field dict for ACT005 if found, else None."""
    return await run_tool(ACT005Result, SYSTEM_PROMPT, user_name, transcript, _OUTPUT_FIELDS)
