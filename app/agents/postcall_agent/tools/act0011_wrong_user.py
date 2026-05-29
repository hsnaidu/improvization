from typing import Optional
from pydantic import Field
from .._base import BaseActionResult, run_tool

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ACT0011Result(BaseActionResult):
    action_id: str = Field(default="ACT0011")
    action_type: str = Field(default="Wrong User")
    wrong_contact: bool = Field(default=False)
    notes: Optional[str] = None
    description: Optional[str] = None
    agent_action_item: Optional[str] = None

# ---------------------------------------------------------------------------
# Specialist system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a specialist extraction agent for collections call analysis.
Your ONLY job: detect and classify ACT0011 — Wrong User (contact-verification ONLY).

## WHAT THIS TOOL DOES
Determine whether the call reached the INTENDED contact named in the transcript.
Do NOT analyse payment intent, disputes, or any other collections outcome.

## FIRE (found=true, wrong_contact=true) when ANY of the following is clearly present:
- Respondent says "wrong number", "you have the wrong number / wrong person", or equivalent.
- Respondent explicitly states they are not the target contact:
  "I am not [name]", "There's no one by that name here", "[Name] doesn't live here."
- A different person answers and denies being the target:
  "She doesn't live here", "He no longer works here", "[Name] moved out."
- Any conversation flow where it can be reasonably inferred from full context that
  the call did not reach the intended individual — even without exact keywords
  (e.g., agent asks for a named individual → respondent gives a confidently different
  name and the intended contact is never confirmed; or respondent is clearly an
  unrelated third party with no knowledge of the account).

## DO NOT FIRE if:
- The respondent does NOT deny being the target (silence or evasion alone is not enough).
- The intended contact is confirmed but unavailable or refuses to engage → ACT003/ACT006.
- The call reached voicemail/IVR with no human identity confirmation → ACT009.
- The respondent's identity is genuinely ambiguous with no clear denial.
- The agent never asked for identity and no denial was made.

## This tool is STRICTLY for contact-verification and wrong-user detection.
   Do NOT classify any other call outcome here.

## IF found=true:
- Set wrong_contact = true
- description: one sentence summarising how the mismatch was identified.
- agent_action_item: concise recommended follow-up for the collections agent
  (e.g., "Verify correct phone number in CRM, update contact record, and retry
  outreach using alternative contact information.").
- notes: any additional context from the transcript relevant to contact verification.

## IF found=false:
- wrong_contact = false, all other fields null.
- Do NOT speculate or fire on vague or inconclusive signals."""

_OUTPUT_FIELDS = [
    "action_id",
    "action_type",
    "wrong_contact",
    "notes",
    "description",
    "agent_action_item",
]
_DEFAULTS: dict = {}

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