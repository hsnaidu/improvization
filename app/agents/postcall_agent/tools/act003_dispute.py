"""
ACT003 — Dispute Tool
Fires when the customer contests a charge they believe is wrong or for a service not delivered.
"""

from typing import Optional
from pydantic import Field
from .._base import BaseActionResult, run_tool

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ACT003Result(BaseActionResult):
    action_id: str = Field(default="ACT003")
    action_type: str = Field(default="Dispute")
    notes: Optional[str] = None
    description: Optional[str] = None
    dispute_reason: Optional[str] = None
    invoice_number: Optional[str] = None
    resolution_status: Optional[str] = None

# ---------------------------------------------------------------------------
# Specialist system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a specialist extraction agent for collections call analysis.
Your ONLY job: detect and extract ACT003 — Dispute.

## STRICT RULES:
- FIRE (found=true) when the customer CONTESTS or CHALLENGES a charge, invoice, or balance they believe is incorrect or for a service not delivered/not as described.
- Examples: "I have a dispute on invoice #123", "That charge is wrong", "I never received that service."
- Populate dispute_reason with the customer's specific reason.
- Populate invoice_number if explicitly mentioned.
- Default resolution_status to 'Pending' unless transcript says otherwise.

If no dispute is present → found=false, all other fields null."""

_OUTPUT_FIELDS = ["action_id", "action_type", "notes", "description",
                  "dispute_reason", "invoice_number", "resolution_status"]
_DEFAULTS = {"resolution_status": "Pending"}

# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run(user_name: str, transcript: str) -> Optional[dict]:
    """Returns a strict-field dict for ACT003 if found, else None."""
    return await run_tool(ACT003Result, SYSTEM_PROMPT, user_name, transcript, _OUTPUT_FIELDS, _DEFAULTS)
