import json
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, Form, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from twilio.rest import Client

from app.config.src import (
    WEBHOOK_URL, 
    TWILIO_CALLBACK_EVENTS, 
    TWILIO_PHONE_NUMBER,
    account_sid,
    auth_token,
    active_calls, 
    blob_manager
)
from app.caller_features.call_report import report_call_result
from app.caller_features.audit_manager import fire_and_forget_log
from caller import handle_voice_agent

router = APIRouter()

'''
Twilio opens a websocket conection to our server
'''

@router.post("/")
async def twilio_connect():
    """Twilio entry point: Establishes the WebSocket stream."""
    ws_url = WEBHOOK_URL.replace("https://", "wss://").replace("http://", "ws://")
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}/api/ws" />
    </Connect>
</Response>"""
    return HTMLResponse(content=content, media_type="application/xml")

'''
To fetch the audio to play from the blob storage
'''
@router.get("/audio/{call_id}")
async def get_audio_playback(call_id: str):
    """Provides a temporary redirect to the audio SAS URL for playback."""
    sas_url = blob_manager.get_sas_url(call_id)
    if not sas_url:
        return {"error": "Recording not found"}
    return RedirectResponse(sas_url)

'''
This will trigger a call to the end user
'''

@router.post("/call")
async def initiate_outbound_call(request: Dict[str, Any]):
    """Initiates an outbound call via Twilio."""
    if not account_sid or not auth_token:
        fire_and_forget_log(request, "Pre‑Call Workflow Initialization", "callhandler_e001", False, "Pre‑call workflow could not be initialized due to missing or invalid inputs")
        return {"error": "Twilio credentials missing"}

    client = Client(account_sid, auth_token)
    user_phone = request.get("phone_number")
    if not user_phone:
        fire_and_forget_log(request, "Pre‑Call Workflow Initialization", "callhandler_e001", False, "Pre‑call workflow could not be initialized due to missing or invalid inputs")
        return {"error": "phone_number is required"}

    fire_and_forget_log(request, "Pre‑Call Workflow Initialization", "callhandler_e001", True)

    try:
        call = client.calls.create(
            from_=TWILIO_PHONE_NUMBER,
            to=user_phone,
            url=f"{WEBHOOK_URL}/api/",
            status_callback=f"{WEBHOOK_URL}/api/status-callback",
            status_callback_event=TWILIO_CALLBACK_EVENTS
        )
        # Store Twilio SID and ensure call_id is set (preserving user-provided ID if it exists)
        request["twilio_sid"] = call.sid
        if "call_id" not in request:
            request["call_id"] = call.sid
            
        active_calls[call.sid] = request
        fire_and_forget_log(request, "Outbound Call Initiation", "callhandler_e003", True)
        return {"status": "Call initiated", "call_sid": call.sid}
    except Exception as e:
        fire_and_forget_log(request, "Outbound Call Initiation", "callhandler_e003", False, "Call could not be initiated due to telephony service or network failure")
        return {"error": str(e)}

'''
If the call is disconnected or busy or no-answer, set the call status to false
'''

@router.post("/status-callback")
async def twilio_status_callback(CallSid: str = Form(...), CallStatus: str = Form(...)):
    """Handles Twilio status updates and triggers failure reporting if needed."""
    user_data = active_calls.get(CallSid, {})
    if CallStatus in ['failed', 'busy', 'no-answer', 'canceled']:
        status_messages = {
            'failed': "Call failed: technical error on telephony side",
            'busy': "Customer busy: line was engaged",
            'no-answer': "Customer did not pick the call",
            'canceled': "Call canceled before connection"
        }
        msg = status_messages.get(CallStatus, f"Call unreachable: {CallStatus}")
        fire_and_forget_log(user_data, "Outbound Call Termination", "callhandler_e004", False, f"Call ended unexpectedly: {msg}")
        await report_call_result(CallSid, user_data, transcript=[], call_status=False, failure_message=msg)
    elif CallStatus == 'completed':
        if not user_data.get('ws_connected'):
            msg = "Customer unreachable: call not answered or connection failed"
            fire_and_forget_log(user_data, "Outbound Call Termination", "callhandler_e004", False, msg)
            await report_call_result(CallSid, user_data, transcript=[], call_status=False, failure_message=msg)
        else:
            fire_and_forget_log(user_data, "Outbound Call Termination", "callhandler_e004", True)
    return {"status": "received"}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket handler for Twilio Media Stream."""
    await websocket.accept()
    try:
        init_data = websocket.iter_text()
        await init_data.__anext__()
        call_data = json.loads(await init_data.__anext__())
        
        stream_sid = call_data["start"]["streamSid"]
        call_sid = call_data["start"]["callSid"]
        
        if call_sid in active_calls:
            active_calls[call_sid]['ws_connected'] = True
        
        user_data = active_calls.get(call_sid, {})
        await handle_voice_agent(websocket, stream_sid, call_sid, user_data)
        
    except (WebSocketDisconnect, StopAsyncIteration):
        fire_and_forget_log(active_calls.get(call_sid, {}), "Outbound Call Termination", "callhandler_e004", True)
    except Exception as e:
        print(f"WebSocket error: {e}")
        fire_and_forget_log(active_calls.get(call_sid, {}), "Outbound Call Termination", "callhandler_e004", False, "Call ended unexpectedly due to connection drop or system interruption")

# --- EXAMPLE: HOW TO ADD A NEW ENDPOINT ---
# @router.get("/summary/{call_id}")
# async def get_call_summary(call_id: str):
#     """
#     Example of a new endpoint to fetch a call summary from your state.
#     """
#     call_info = active_calls.get(call_id)
#     if not call_info:
#         return {"error": "Call not found"}
#     return {"call_id": call_id, "summary": call_info.get("summary", "Pending...")}
