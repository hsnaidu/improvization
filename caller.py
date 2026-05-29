import time
from typing import Optional
from fastapi import WebSocket

# Voice Activity Detection
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams

# Context & Frames
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext, OpenAILLMContextFrame
from pipecat.frames.frames import TextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


# Services & Transport
from pipecat.serializers.twilio import TwilioFrameSerializer 
from pipecat.services.azure.llm import AzureLLMService 
from pipecat.services.azure.stt import AzureSTTService 
from pipecat.services.azure.tts import AzureTTSService 
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport
)

# Aggregators & Turns
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    UserTurnStoppedMessage,
    AssistantTurnStoppedMessage,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.turns.user_start import VADUserTurnStartStrategy, TranscriptionUserTurnStartStrategy
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.turn.smart_turn.base_smart_turn import SmartTurnParams
from pipecat.adapters.schemas.tools_schema import ToolsSchema # Tool calling

# Audio Processing
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.services.tts_service import TextAggregationMode

# App Imports
from app.agents.precall_agent.call_one import get_prompt as get_prompt_one
from app.agents.precall_agent.call_two import get_prompt as get_prompt_two
from app.caller_features.parameter import *
from app.caller_features.audit_manager import fire_and_forget_log
from app.caller_features.call_report import report_call_result
from app.caller_features.context_limit import ContextLimiterProcessor

from app.config.src import (
    AZURE_LLM_API_KEY, 
    AZURE_LLM_ENDPOINT, 
    AZURE_SPEECH_API_KEY, 
    AZURE_SPEECH_REGION, 
    blob_manager,
    account_sid,
    auth_token
)



async def handle_voice_agent(
    websocket_client: WebSocket,
    stream_sid: str,
    call_sid: str,
    user_data: dict = None
):
    """
    Configures and executes the Pipecat real-time voice pipeline.
    """
    if user_data is None: user_data = {}
    
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=TwilioFrameSerializer(
                stream_sid,
                call_sid=call_sid,
                account_sid=account_sid,
                auth_token=auth_token,
                # Here: We are using the autohangup
                params=TwilioFrameSerializer.InputParams(auto_hang_up=True)
            ),
        ),
    )

    llm = AzureLLMService(
        api_key=AZURE_LLM_API_KEY,
        model=AZURE_DEPLOYMENT,
        api_version=LLM_MODEL_VERSION,
        endpoint=AZURE_LLM_ENDPOINT,
        max_completion_tokens=200,
    )



    stt = AzureSTTService(
        api_key=AZURE_SPEECH_API_KEY, 
        region=AZURE_SPEECH_REGION, 
        language=STT_LANGUAGE,
    )

    turn_end_time = 0
    start_silence_time = 0

    @stt.event_handler("on_transcript")
    async def on_stt_transcript(service, transcription):
        nonlocal turn_end_time
        turn_end_time = time.time()
        print(f"[Latency] STT Result Segment received. Time since silence: {time.time() - start_silence_time:.3f}s")

    tts = AzureTTSService(
        api_key=AZURE_SPEECH_API_KEY,
        region=AZURE_SPEECH_REGION,
        voice=TTS_VOICE,
        text_aggregation_mode=TextAggregationMode.SENTENCE,
        settings=AzureTTSService.Settings(
            style=VOICE_STYLE,
            rate=VOICE_RATE
        )
    )

    call_type = user_data.get("call_type")
    try:
        system_prompt = get_prompt_one(user_data) if call_type == 1 else get_prompt_two(user_data)
        fire_and_forget_log(user_data, "Call Script Generation", "callhandler_e002", True)
    except Exception as e:
        fire_and_forget_log(user_data, "Call Script Generation", "callhandler_e002", False, "AI call script generation failed due to configuration or model error")
        raise
        
    context = OpenAILLMContext([{"role": "system", "content": system_prompt}])
    
    smart_turn = LocalSmartTurnAnalyzerV3(params=SmartTurnParams(stop_secs=0.5))
    vad_analyzer = SileroVADAnalyzer(
        params=VADParams(
            stop_secs=VAD_STOP_DURATION,
            min_speech_secs=VAD_MIN_SPEECH_DURATION,
        )
    )

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=vad_analyzer,
            user_turn_strategies=UserTurnStrategies(
                start=[VADUserTurnStartStrategy(), TranscriptionUserTurnStartStrategy()],
                stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=smart_turn)]
            )
        )
    )

    context_limiter = ContextLimiterProcessor(max_messages=MAX_CONTEXT_MESSAGES)
    record_id = user_data.get("call_id") or call_sid

    audiobuffer = AudioBufferProcessor(num_channels=NUM_CHANNELS, enable_turn_audio=False)
    @audiobuffer.event_handler("on_audio_data")
    async def on_audio_data(buffer, audio, sample_rate, num_channels):
        try:
            await blob_manager.upload_chunk(record_id, audio)
        except Exception as e:
            fire_and_forget_log(user_data, "Blob Audio Recording", "callhandler_e007", False, "Audio recording failed during upload chunk")
            raise

    @user_aggregator.event_handler("on_user_turn_stopped")
    async def on_user_turn_stopped(aggregator, strategy, message: UserTurnStoppedMessage):
        nonlocal start_silence_time
        start_silence_time = time.time()
        print(f"Conversation - User: {message.content}")

    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(aggregator, message: AssistantTurnStoppedMessage):
        if message.content:
            print(f"Conversation - Assistant: {message.content} | TTFT: {time.time() - turn_end_time:.3f}s")
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                print(f"Conversation - Assistant Tool Call: {tool_call['function']['name']}")

    
    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        context_limiter,
        llm,
        tts,
        transport.output(),
        audiobuffer,
        assistant_aggregator,
    ])


    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=SAMPLE_RATE,
            audio_out_sample_rate=SAMPLE_RATE,
            allow_interruptions=ALLOW_INTERRUPTIONS,
        ),
    )


    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await audiobuffer.start_recording()
        await task.queue_frames([OpenAILLMContextFrame(context)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await audiobuffer.stop_recording()
        await task.cancel()

    call_success = True
    failure_msg = None
    try:
        runner = PipelineRunner(handle_sigint=False, force_gc=FORCE_GC_ON_RUN)
        await runner.run(task)
    except Exception as e:
        print(f"Error during call: {e}")
        call_success = False
        failure_msg = f"Server crashed or error during call: {str(e)}"

    # Filter transcript to only include human-readable user and assistant messages
    full_transcript = [
        msg for msg in context.get_messages() 
        if msg.get("role") in ["user", "assistant"] and msg.get("content")
    ]
    try:
        recording_info = await blob_manager.finalize_recording(record_id, SAMPLE_RATE, NUM_CHANNELS)
        fire_and_forget_log(user_data, "Blob Audio Recording", "callhandler_e007", True)
    except Exception as e:
        fire_and_forget_log(user_data, "Blob Audio Recording", "callhandler_e007", False, "Audio recording failed during finalization")
        recording_info = None

    await report_call_result(call_sid, user_data, full_transcript, call_status=call_success, recording_info=recording_info, failure_message=failure_msg)