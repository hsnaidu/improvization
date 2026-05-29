"""
ACT008 — OtherCustomerRequest Tool
Fires for any customer request NOT covered by ACT001–ACT007.
Examples: invoice number inquiry, account details, address updates, general account questions.
"""

from typing import Optional
from pydantic import Field
from .._base import BaseActionResult, run_tool

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ACT008Result(BaseActionResult):
    action_id: str = Field(default="ACT008")
    action_type: str = Field(default="OtherCustomerRequest")
    notes: Optional[str] = None
    description: Optional[str] = None
    request_details: Optional[str] = None
    preferred_time: Optional[str] = None

# ---------------------------------------------------------------------------
# Specialist system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a specialist extraction agent for collections call analysis.
Your ONLY job: detect and extract ACT008 — OtherCustomerRequest.

## STRICT RULES:
- FIRE (found=true) for any customer request that is NOT covered by ACT001–ACT007.
- Examples of ACT008 requests:
  - Asking for invoice number or account details: "What is my invoice number?"
  - Requesting an address or email update
  - Any general account inquiry not involving payment, escalation, dispute, documents, or credit
- IMPORTANT: If the customer asks "What is my invoice number?" (ACT008) AND THEN asks "Can you email it to me?" (ACT004), these are TWO SEPARATE actions.
  Only capture the INQUIRY here. The email/send request belongs to ACT004.
- Populate request_details with a full, clear description of what the customer is asking for.
- Populate preferred_time if the customer mentions a preferred callback or contact time.

If no uncategorized customer request is present → found=false, all other fields null."""

_OUTPUT_FIELDS = ["action_id", "action_type", "notes", "description",
                  "request_details", "preferred_time"]

# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run(user_name: str, transcript: str) -> Optional[dict]:
    """Returns a strict-field dict for ACT008 if found, else None."""
    return await run_tool(ACT008Result, SYSTEM_PROMPT, user_name, transcript, _OUTPUT_FIELDS)
