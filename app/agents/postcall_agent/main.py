# """
# postcallagent/main.py — Orchestrator
# ======================================
# Runs all 10 action-detection tools IN PARALLEL using asyncio.gather,
# then assembles summary + categorization via a single meta-LLM call.

# Package layout (postcallagent/):
#   _base.py                      → Shared LLM factory, TokenUsageCallback, run_tool() engine
#   main.py                       → This file — orchestrator entry point
#   act001_promise_to_pay.py      → ACT001 PromiseToPay
#   act002_escalation.py          → ACT002 Escalation
#   act003_dispute.py             → ACT003 Dispute
#   act004_document_copy.py       → ACT004 DocumentCopy
#   act005_partial_payment.py     → ACT005 PartialPayment
#   act006_doubtful_receivable.py → ACT006 DoubtfulReceivable
#   act007_credit_request.py      → ACT007 CreditRequest
#   act008_other_request.py       → ACT008 OtherCustomerRequest
#   act009_voice_mail.py          → ACT009 VoiceMail
#   act0010_abrupt_call.py        → ACT0010 AbruptCall
# """

# from __future__ import annotations

# import asyncio
# import json

# from dotenv import load_dotenv
# from langchain_core.prompts import ChatPromptTemplate
# from pydantic import BaseModel, Field

# from ._base import TokenUsageCallback, build_llm, HUMAN_TEMPLATE
# from .tools import (
#     act001_promise_to_pay,
#     act002_escalation,
#     act003_dispute,
#     act004_document_copy,
#     act005_partial_payment,
#     act006_doubtful_receivable,
#     act007_credit_request,
#     act008_other_request,
#     act009_voice_mail,
#     act0010_abrupt_call,
# )

# load_dotenv()

# # ---------------------------------------------------------------------------
# # Meta-analysis: summary + action items + categorization (one LLM call)
# # ---------------------------------------------------------------------------

# class MetaAnalysis(BaseModel):
#     summary: str = Field(description="A 2-3 sentence summary of the call transcript.")
#     user_action: str = Field(description="The action item that the USER (customer) needs to take after the call.")
#     agent_action_item: str = Field(description="The action item that the AGENT needs to take after the call.")
#     category: str = Field(description="Categorize the outcome: 'pending', 'cleared', or 'dispute'.")


# _META_SYSTEM_PROMPT = """You are an AI assistant reviewing a collections call transcript.
# Your job is to produce:
# 1. A 2-3 sentence summary covering: the main reason for the call, any payment agreements, and customer sentiment.
# 2. The action item the CUSTOMER must take after the call.
# 3. The action item the AGENT must take after the call.
# 4. The overall call outcome categorized as EXACTLY ONE of: 'pending', 'cleared', or 'dispute'."""


# async def _run_meta_analysis(
#     user_name: str, transcript: str, token_cb: TokenUsageCallback
# ) -> MetaAnalysis:
#     """Single LLM call for summary, action items, and category."""
#     llm = build_llm().with_structured_output(MetaAnalysis)
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", _META_SYSTEM_PROMPT),
#         ("human", HUMAN_TEMPLATE),
#     ])
#     return await (prompt | llm).ainvoke(
#         {"user_name": user_name, "transcript": transcript},
#         config={"callbacks": [token_cb]},
#     )


# # ---------------------------------------------------------------------------
# # Main Entry Point
# # ---------------------------------------------------------------------------

# async def process_transcript_and_update_json(call_data: dict) -> dict:
#     """
#     Runs all 10 action tools + meta-analysis IN PARALLEL, then assembles
#     the final enriched call_data dict.

#     ACT006 (DoubtfulReceivable) is always placed first in the actions list
#     per business rules, even when found alongside other actions.
#     """
#     transcript = call_data.get("transcript", "")
#     if isinstance(transcript, (dict, list)):
#         transcript = json.dumps(transcript)

#     user_name: str = call_data.get("user_name", "Unknown")
#     token_cb = TokenUsageCallback()

#     # Fan-out: all 10 action tools + meta-analysis run simultaneously
#     (
#         act001_result,
#         act002_result,
#         act003_result,
#         act004_result,
#         act005_result,
#         act006_result,
#         act007_result,
#         act008_result,
#         act009_result,
#         act0010_result,
#         meta_result,
#     ) = await asyncio.gather(
#         act001_promise_to_pay.run(user_name, transcript),
#         act002_escalation.run(user_name, transcript),
#         act003_dispute.run(user_name, transcript),
#         act004_document_copy.run(user_name, transcript),
#         act005_partial_payment.run(user_name, transcript),
#         act006_doubtful_receivable.run(user_name, transcript),
#         act007_credit_request.run(user_name, transcript),
#         act008_other_request.run(user_name, transcript),
#         act009_voice_mail.run(user_name, transcript),
#         act0010_abrupt_call.run(user_name, transcript),
#         _run_meta_analysis(user_name, transcript, token_cb),
#         return_exceptions=True,  # one tool failure must not kill all others
#     )

#     # Log any per-tool exceptions (non-fatal)
#     raw_actions = [
#         ("ACT001", act001_result),
#         ("ACT002", act002_result),
#         ("ACT003", act003_result),
#         ("ACT004", act004_result),
#         ("ACT005", act005_result),
#         ("ACT006", act006_result),
#         ("ACT007", act007_result),
#         ("ACT008", act008_result),
#         ("ACT009", act009_result),
#         ("ACT0010", act0010_result),
#     ]
#     for act_id, res in raw_actions:
#         if isinstance(res, Exception):
#             print(f"[postcallagent] {act_id} tool raised an exception: {res}")

#     # ACT006 goes first (business rule: doubtful receivable leads the list)
#     actions: list[dict] = []
#     if isinstance(act006_result, dict):
#         actions.append(act006_result)

#     for act_id, res in raw_actions:
#         if act_id == "ACT006":
#             continue  # already inserted above
#         if isinstance(res, dict):
#             actions.append(res)

#     # Set voice_mail flag based on ACT009 detection and call_abrupt flag based on ACT0010
#     # If voice_mail detected and no other failure_message exists: set call_status=False and failure_message in call_data
#     voice_mail_detected = isinstance(act009_result, dict) and act009_result.get("found", False)
    
#     # Also check if voice_mail is already marked in call_data (fallback)
#     if not voice_mail_detected and "call_data" in call_data:
#         voice_mail_detected = call_data["call_data"].get("voice_mail", False)
    
#     if voice_mail_detected and "call_data" in call_data:
#         call_data["call_data"]["voice_mail"] = True
#         # Only set failure_message if it's empty or None (Twilio failure takes precedence)
#         current_failure = call_data["call_data"].get("failure_message", "").strip()
#         if not current_failure:
#             call_data["call_data"]["call_status"] = False
#             call_data["call_data"]["failure_message"] = "Voice-mail: Could not connect to Customer"

#     # Set call_abrupt flag based on ACT0010 detection
#     call_abrupt_detected = isinstance(act0010_result, dict) and act0010_result.get("call_abrupt", False)
#     if "call_data" in call_data and call_abrupt_detected:
#         call_data["call_data"]["call_abrupt"] = True

#     # Assemble final output
#     if isinstance(meta_result, Exception):
#         print(f"[postcallagent] Meta-analysis raised an exception: {meta_result}")
#         call_data["summary"] = "Error extracting summary."
#         call_data["action_items"] = {"user_action": "", "agent_action_item": ""}
#         call_data["categorization"] = "Unknown"
#     else:
#         call_data["summary"] = meta_result.summary
#         # call_data["action_items"] = {
#         #     "user_action": meta_result.user_action,
#         #     "agent_action_item": meta_result.agent_action_item,
#         # }
#         call_data["categorization"] = meta_result.category

#     call_data["actions"] = actions
#     call_data["token_usage"] = token_cb.to_dict()

#     return call_data



## Second Itteration


from __future__ import annotations

import asyncio
import json

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from ._base import TokenUsageCallback, build_llm, HUMAN_TEMPLATE
try:
    from app.caller_features.open_telemetry import call_span, record_token_usage
except ImportError:
    # Local/test environment fallback stubs
    def call_span(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def record_token_usage(*args, **kwargs):
        pass
from .tools import (
    act001_promise_to_pay,
    act002_escalation,
    act003_dispute,
    act004_document_copy,
    act005_partial_payment,
    act006_doubtful_receivable,
    act007_credit_request,
    act008_other_request,
    act009_voice_mail,
    act0010_abrupt_call,
    act0011_wrong_contact,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Meta-analysis: summary + action items + categorization (one LLM call)
# ---------------------------------------------------------------------------

class MetaAnalysis(BaseModel):
    summary: str = Field(description="A 2-3 sentence summary of the call transcript.")
    user_action: str = Field(description="The action item that the USER (customer) needs to take after the call.")
    agent_action_item: str = Field(description="The action item that the AGENT needs to take after the call.")
    category: str = Field(description="Categorize the outcome: 'pending', 'cleared', or 'dispute'.")


_META_SYSTEM_PROMPT = """You are an AI assistant reviewing a collections call transcript.
Your job is to produce:
1. A 2-3 sentence summary covering: the main reason for the call, any payment agreements, and customer sentiment.
2. The action item the CUSTOMER must take after the call.
3. The action item the AGENT must take after the call.
4. The overall call outcome categorized as EXACTLY ONE of: 'pending', 'cleared', or 'dispute'."""


async def _run_meta_analysis(
    user_name: str, transcript: str, token_cb: TokenUsageCallback
) -> MetaAnalysis:
    """Single LLM call for summary, action items, and category."""
    llm = build_llm().with_structured_output(MetaAnalysis)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _META_SYSTEM_PROMPT),
        ("human", HUMAN_TEMPLATE),
    ])
    return await (prompt | llm).ainvoke(
        {"user_name": user_name, "transcript": transcript},
        config={"callbacks": [token_cb]},
    )


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

async def process_transcript_and_update_json(call_data: dict) -> dict:
    """
    Runs all 11 action tools + meta-analysis IN PARALLEL, then assembles
    the final enriched call_data dict.

    ACT006 (DoubtfulReceivable) is always placed first in the actions list
    per business rules, even when found alongside other actions.

    ACT0011 (WrongUser): if wrong_contact=True, sets
        call_data["call_data"]["call_status"]     = False
        call_data["call_data"]["failure_message"] = "Wrong Contact"
    This is evaluated before voice_mail and call_abrupt flags.
    """
    transcript = call_data.get("transcript", "")
    if isinstance(transcript, (dict, list)):
        transcript = json.dumps(transcript)

    user_name: str = call_data.get("user_name", "Unknown")
    token_cb = TokenUsageCallback()

    # Fan-out: all 11 action tools + meta-analysis run simultaneously
    (
        act001_result,
        act002_result,
        act003_result,
        act004_result,
        act005_result,
        act006_result,
        act007_result,
        act008_result,
        act009_result,
        act0010_result,
        act0011_result,
        meta_result,
    ) = await asyncio.gather(
        act001_promise_to_pay.run(user_name, transcript),
        act002_escalation.run(user_name, transcript),
        act003_dispute.run(user_name, transcript),
        act004_document_copy.run(user_name, transcript),
        act005_partial_payment.run(user_name, transcript),
        act006_doubtful_receivable.run(user_name, transcript),
        act007_credit_request.run(user_name, transcript),
        act008_other_request.run(user_name, transcript),
        act009_voice_mail.run(user_name, transcript),
        act0010_abrupt_call.run(user_name, transcript),
        act0011_wrong_contact.run(user_name, transcript),
        _run_meta_analysis(user_name, transcript, token_cb),
        return_exceptions=True,  # one tool failure must not kill all others
    )

    # Log any per-tool exceptions (non-fatal)
    raw_actions = [
        ("ACT001",  act001_result),
        ("ACT002",  act002_result),
        ("ACT003",  act003_result),
        ("ACT004",  act004_result),
        ("ACT005",  act005_result),
        ("ACT006",  act006_result),
        ("ACT007",  act007_result),
        ("ACT008",  act008_result),
        ("ACT009",  act009_result),
        ("ACT0010", act0010_result),
        ("ACT0011", act0011_result),
    ]
    for act_id, res in raw_actions:
        if isinstance(res, Exception):
            print(f"[postcallagent] {act_id} tool raised an exception: {res}")

    # ---------------------------------------------------------------------------
    # Process Call Status and Failure Message Aggregation
    # ---------------------------------------------------------------------------
    if "call_data" in call_data:
        wrong_user_detected = (
            isinstance(act0011_result, dict)
            and act0011_result.get("wrong_contact") is True
        )
        if wrong_user_detected:
            call_data["call_data"]["wrong_contact"] = True
            call_data["call_data"]["call_status"] = False

        voice_mail_detected = (
            isinstance(act009_result, dict)
            and act009_result.get("found", False)
        )
        if voice_mail_detected:
            call_data["call_data"]["voice_mail"] = True

        call_abrupt_detected = (
            isinstance(act0010_result, dict)
            and act0010_result.get("call_abrupt", False)
        )
        if call_abrupt_detected:
            call_data["call_data"]["call_abrupt"] = True

        # Build list of unique failure reasons
        reasons = []
        
        # Start with any existing failure message (e.g., from Twilio or base caller)
        existing_msg = call_data["call_data"].get("failure_message") or ""
        if existing_msg:
            for part in [p.strip() for p in existing_msg.split(",") if p.strip()]:
                if part not in reasons:
                    reasons.append(part)

        # Add detected postcall reasons
        if call_data["call_data"].get("wrong_contact") is True:
            if "Wrong Contact" not in reasons:
                reasons.append("Wrong Contact")

        if call_data["call_data"].get("call_abrupt") is True:
            # Check if there is already an abrupt string, e.g. "Call disconnected abruptly"
            has_abrupt = any("abrupt" in r.lower() for r in reasons)
            if not has_abrupt:
                reasons.append("Call disconnected abruptly")

        if call_data["call_data"].get("voice_mail") is True:
            has_vm = any("voice-mail" in r.lower() or "voicemail" in r.lower() for r in reasons)
            if not has_vm:
                reasons.append("Voice-mail: Could not connect to Customer")

        # Join unique reasons with a comma
        if reasons:
            call_data["call_data"]["failure_message"] = ", ".join(reasons)

    # ACT006 goes first (business rule: doubtful receivable leads the list)
    actions: list[dict] = []
    if isinstance(act006_result, dict):
        actions.append(act006_result)

    for act_id, res in raw_actions:
        if act_id == "ACT006":
            continue  # already inserted above
        if isinstance(res, dict):
            actions.append(res)

    # Assemble final output
    if isinstance(meta_result, Exception):
        print(f"[postcallagent] Meta-analysis raised an exception: {meta_result}")
        call_data["summary"]        = "Error extracting summary."
        call_data["action_items"]   = {"user_action": "", "agent_action_item": ""}
        call_data["categorization"] = "Unknown"
    else:
        call_data["summary"]        = meta_result.summary
        # call_data["action_items"] = {
        #     "user_action":       meta_result.user_action,
        #     "agent_action_item": meta_result.agent_action_item,
        # }
        call_data["categorization"] = meta_result.category

    call_data["actions"]     = actions
    call_data["token_usage"] = token_cb.to_dict()

    # --- Telemetry: record postcall LLM token consumption ---
    call_sid = str(call_data.get("call_id") or call_data.get("call_sid") or "unknown")
    tu = token_cb.to_dict()
    record_token_usage(
        call_sid=call_sid,
        prompt_tokens=tu.get("prompt_tokens", 0),
        completion_tokens=tu.get("completion_tokens", 0),
        model=tu.get("model"),
    )

    return call_data
