import os
import json
import aiohttp
from twilio.rest import Client

from app.agents.postcall_agent.main import process_transcript_and_update_json
from app.config.src import (
    WEBHOOK_URL, 
    BLOB_CONTAINER_NAME, 
    ORCHESTRATION_LAYER, 
    processed_calls,
    account_sid, 
    auth_token
)
from app.cosmos.db import save_final_payload_to_cosmos
from app.caller_features.audit_manager import fire_and_forget_log

async def report_call_result(call_sid: str, user_data: dict, transcript: list, call_status: bool, recording_info: dict = None, failure_message: str = None, realtime_usage: dict = None):
    """
    Collates call metadata, fetches Twilio details, and triggers post-call analysis.
    """
    if call_sid in processed_calls: 
        return
    processed_calls.add(call_sid)
    
    try:
        # 1. Fetch Twilio Metadata
        twilio_metadata = {}
        try:
            if account_sid and auth_token:
                twilio_client = Client(account_sid, auth_token)
                call_details = twilio_client.calls(call_sid).fetch()
                twilio_metadata['start_time'] = str(call_details.start_time) if call_details.start_time else ""
                twilio_metadata['end_time'] = str(call_details.end_time) if call_details.end_time else ""
        except Exception: 
            pass

        # 2. Prepare Document for Analysis
        document = user_data.copy()
        if "call_data" not in document or not isinstance(document["call_data"], dict):
            document["call_data"] = {}
        
        # Preserve the original call_status from Twilio/caller
        document["call_data"]["call_status"] = call_status
        
        # Set failure_message if provided
        if failure_message:
            document["call_data"]["failure_message"] = failure_message
        elif "failure_message" not in document["call_data"]:
            document["call_data"]["failure_message"] = ""
        
        # Merge Timestamps
        document["call_data"]["call_start_at"] = twilio_metadata.get('start_time') or document["call_data"].get("call_start_at") or ""
        document["call_data"]["call_end_at"] = twilio_metadata.get('end_time') or document["call_data"].get("call_end_at") or ""

        document.update({
            "id": user_data.get("case_id", call_sid),
            "user_id": user_data.get("customer_number") or user_data.get("customer_id", call_sid),
            "call_sid": call_sid,
            "transcript": transcript
        })

        # 3. AI Post-Call Analysis (Extract actions, summary, etc.)
        # Always run postcall analysis to detect voicemail and abrupt calls, even with empty transcript
        try:
            document = await process_transcript_and_update_json(document)
            fire_and_forget_log(user_data, "Call Summary and Transcript Generation", "callhandler_e005", True)
        except Exception as e:
            print(f"[Analysis Error] {e}")
            fire_and_forget_log(user_data, "Call Summary and Transcript Generation", "callhandler_e005", False, "Call summary, transcripts, or notes generation failed due to processing error")
            document['summary'] = "Processing error"
            document['actions'] = []

        # 4. Construct Final Structured Payload
        full_transcript_obj = {str(i+1): msg for i, msg in enumerate(document.get("transcript") or [])}
        
        # Robust Invoice Extraction
        invoice_nos = []
        # Check invoice_details list
        details = document.get("invoice_details") or []
        if isinstance(details, list):
            for item in details:
                if isinstance(item, dict):
                    # Check common keys: invoice_number, invoice_no, inv_no, etc.
                    raw_inv = (item.get("invoice_number") or item.get("invoice_no") or 
                               item.get("inv_no") or item.get("invoiceNumber"))
                    if isinstance(raw_inv, list):
                        invoice_nos.extend([str(x) for x in raw_inv])
                    elif raw_inv:
                        invoice_nos.append(str(raw_inv))
                elif isinstance(item, (str, int)):
                    invoice_nos.append(str(item))
        
        # Fallback to top-level fields if list is empty
        if not invoice_nos:
            top_inv = document.get("invoice_numbers") or document.get("invoice_number") or document.get("invoice_no")
            if isinstance(top_inv, list):
                invoice_nos.extend([str(x) for x in top_inv])
            elif top_inv:
                invoice_nos.append(str(top_inv))
        
        # Unique and cleaned (preserving order)
        invoice_nos = list(dict.fromkeys([x.strip() for x in invoice_nos if x]))
        
        final_payload = {
            "call_id": document.get("call_id") or call_sid,
            "case_id": document.get("case_id"),
            "customer_number": document.get("customer_number") or document.get("customer_id") or document.get("user_id") or call_sid,
            "invoice_numbers": invoice_nos,
            "recording_url": f"{WEBHOOK_URL}/audio/{document.get('call_id') or call_sid}",
            "recording": recording_info or {
                "call_id": document.get("call_id") or call_sid,
                "storage": "azure_blob",
                "container": BLOB_CONTAINER_NAME,
                "blob_name": f"{(document.get('call_id') or call_sid)}.wav"
            },
            "call_data": {
                "attempt_number": int(document.get("attempt_number") or 1),
                "call_status": document.get("call_data", {}).get("call_status", call_status),
                "call_abrupt": document.get("call_data", {}).get("call_abrupt", False),
                "failure_message": failure_message or ("Call reached voicemail system" if document.get("call_data", {}).get("voice_mail", False) else "Call disconnected abruptly" if document.get("call_data", {}).get("call_abrupt", False) else ""),
                "call_start_at": str(document.get("call_data", {}).get("call_start_at") or ""),
                "call_end_at": str(document.get("call_data", {}).get("call_end_at") or ""),
                "voice_mail": document.get("call_data", {}).get("voice_mail", False)
            },
            "transcript": {
                "full_transcript": full_transcript_obj,
                "call_summary": [document.get("summary")] if document.get("summary") else []
            },
            "actions": document.get("actions") or [],
            "token_usage": document.get("token_usage") or {},
            "realtime_usage": realtime_usage or {}
        }

        # 5. External Integration (Webhooks)
        if ORCHESTRATION_LAYER and "placeholder" not in ORCHESTRATION_LAYER:
            # We remove token_usage for external payloads to save bandwidth/privacy
            external_payload = final_payload.copy()
            external_payload.pop("token_usage", None)
            external_payload.pop("realtime_usage", None)
            # Remove unwanted fields from actions
            if "actions" in external_payload and isinstance(external_payload["actions"], list):
                for action in external_payload["actions"]:
                    action.pop("call_abrupt", None)
                    action.pop("found", None)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(ORCHESTRATION_LAYER, json=external_payload) as response:
                        print(f"[Webhook] Report sent for {call_sid} | Status: {response.status}")
                        if response.status in [200, 201]:
                            fire_and_forget_log(user_data, "Send Call Records to Post‑Call Handler", "callhandler_e006", True)
                        else:
                            fire_and_forget_log(user_data, "Send Call Records to Post‑Call Handler", "callhandler_e006", False, "Call records could not be delivered to post‑call handler due to pipeline failure")
            except Exception as e:
                print(f"[Webhook] Failed to send report: {e}")
                fire_and_forget_log(user_data, "Send Call Records to Post‑Call Handler", "callhandler_e006", False, "Call records could not be delivered to post‑call handler due to pipeline failure")
        
        # 6. Database Persistence
        try:
            await save_final_payload_to_cosmos(final_payload)
        except Exception as e:
            print(f"[Cosmos] Failed to save result: {e}")

    except Exception as e:
        print(f"[Critical] Error during reporting for {call_sid}: {e}")