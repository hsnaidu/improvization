from typing import Optional
from pydantic import Field
from .._base import BaseActionResult, run_tool

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ACT0011Result(BaseActionResult):
    action_id: str = Field(default="ACT0011")
    action_type: str = Field(default="Wrong Contact")
    wrong_contact: bool = Field(default=False)
    notes: str = Field(default="")
    description: Optional[str] = None

# ---------------------------------------------------------------------------
# Specialist system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a specialist extraction agent for collections call analysis.
Your ONLY job: detect and classify ACT0011 — Wrong Contact (contact-verification ONLY).

## WHAT THIS TOOL DOES
Determine whether the call reached the INTENDED contact (Customer Name: {user_name}).
Do NOT analyse payment intent, disputes, or any other collections outcome.

## FIRE (found=true, wrong_contact=true) when ANY of the following is present:
- Respondent says "wrong number", "you have the wrong number", "you have the wrong person", "contacting the wrong person", or equivalent.
- Respondent explicitly states or implies they are not the intended contact (Customer Name: {user_name}).
  E.g., "I guess you're contacting the wrong person", "This is the wrong person", "I am not {user_name}", "There's no one by that name here."
- A different/third-party person answers and the target is not available or they offer to pass a message:
  "He is out", "She is not here", "You can tell me what to tell him."
- Any conversation flow where it is clear the call did NOT speak with or reach the intended contact {user_name}.

## DO NOT FIRE (found=false, wrong_contact=false) if:
- The intended contact IS the one speaking to the agent, or if the identity is confirmed or verified as the correct contact.

## If found=true:
  * Set wrong_contact=true
  * Provide description: one sentence summarising how the contact mismatch was identified.
  * Provide notes: any additional context from the transcript relevant to contact verification.

## If criteria not met → found=false, wrong_contact=false, description=null, notes=null."""

_OUTPUT_FIELDS = [
    "action_id",
    "action_type",
    "wrong_contact",
    "notes",
    "description"
]
_DEFAULTS = {"notes": ""}

# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run(user_name: str, transcript: str) -> Optional[dict]:
    """
    Returns a strict-field dict for ACT0011 if the call reached the wrong
    contact, else None.

    The orchestrator (main.py) reads wrong_contact from the returned dict to
    set call_data["call_data"]["call_status"] = False and
    call_data["call_data"]["failure_message"] = "Wrong Contact".
    """
    return await run_tool(
        ACT0011Result, SYSTEM_PROMPT, user_name, transcript, _OUTPUT_FIELDS, _DEFAULTS
    )