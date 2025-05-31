import logging
from typing import Optional
from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from utils.elevenlabs import generate_elevenlabs_audio
from routes.sms_routes import get_call_data_store

logger = logging.getLogger(__name__)

router = APIRouter()


@router.api_route(
    "/webhook/voice/call/{call_id}",
    methods=["GET", "POST"],
    response_class=PlainTextResponse,
)
async def handle_voice_call_webhook(call_id: str, request: Request):
    """
    Handle voice webhooks for outbound calls with IVR functionality

    This endpoint handles the initial call and presents options to the user
    """
    try:
        # Get call data from storage
        call_data_store = get_call_data_store()
        if call_id not in call_data_store:
            logger.error(f"Call data not found for call_id: {call_id}")
            response = VoiceResponse()
            response.say(
                "Sorry, there was an error processing your call.", voice="Polly.Emma"
            )
            response.hangup()
            return str(response)

        call_data = call_data_store[call_id]
        sms_body = call_data["sms_body"]

        response = VoiceResponse()

        # Try to generate audio with ElevenLabs first
        audio_url = await generate_elevenlabs_audio(sms_body, request)

        if audio_url:
            # Use ElevenLabs generated audio
            response.play(audio_url)
            response.pause(length=1)
        else:
            # Fallback to Twilio TTS with improved voice
            response.say(
                f"<speak><prosody rate='medium' pitch='high' volume='medium'>{sms_body}</prosody></speak>",
                voice="Polly.Emma",  # Cheerful British female voice
            )
            response.pause(length=1)

        # Add IVR options
        gather = Gather(
            num_digits=1,
            timeout=10,
            action=f"/webhook/voice/input/{call_id}",
            method="POST",
        )

        gather.say(
            "<speak><prosody rate='medium' pitch='high' volume='medium'>Press 1 to end the call, or press 2 for a special message.</prosody></speak>",
            voice="Polly.Emma",
        )

        response.append(gather)

        # If no input is received, repeat the options
        response.say(
            "<speak><prosody rate='medium' pitch='high' volume='medium'>I didn't receive any input. Goodbye!</prosody></speak>",
            voice="Polly.Emma",
        )
        response.hangup()

        return str(response)

    except Exception as e:
        logger.error(f"Error processing voice call webhook: {str(e)}")
        response = VoiceResponse()
        response.say("Sorry, there was an error. Goodbye!", voice="Polly.Emma")
        response.hangup()
        return str(response)


@router.api_route(
    "/webhook/voice/input/{call_id}",
    methods=["GET", "POST"],
    response_class=PlainTextResponse,
)
async def handle_voice_input_webhook(
    call_id: str, request: Request, Digits: Optional[str] = Form(None)
):
    """
    Handle user input from the IVR system

    This endpoint processes the user's keypress and responds accordingly
    """
    try:
        # Handle both GET and POST requests
        if request.method == "GET":
            # For GET requests, digits come as query parameters
            query_params = dict(request.query_params)
            digits = query_params.get("Digits", "")
        else:
            # For POST requests, digits come from form data
            digits = Digits or ""

        logger.info(f"Received input '{digits}' for call_id: {call_id}")

        response = VoiceResponse()

        if digits == "1":
            # User pressed 1 - end the call
            response.say(
                "<speak><prosody rate='medium' pitch='high' volume='medium'>Goodbye!</prosody></speak>",
                voice="Polly.Emma",
            )
            response.hangup()
        elif digits == "2":
            # User pressed 2 - special message
            response.say(
                "<speak><prosody rate='medium' pitch='high' volume='medium'>Thanks for picking up the phone dude!</prosody></speak>",
                voice="Polly.Emma",
            )
            response.pause(length=1)
            response.say(
                "<speak><prosody rate='medium' pitch='high' volume='medium'>Have a great day!</prosody></speak>",
                voice="Polly.Emma",
            )
            response.hangup()
        else:
            # Invalid input or no input
            response.say(
                "<speak><prosody rate='medium' pitch='high' volume='medium'>Invalid option. Goodbye!</prosody></speak>",
                voice="Polly.Emma",
            )
            response.hangup()

        # Clean up call data after processing
        call_data_store = get_call_data_store()
        if call_id in call_data_store:
            del call_data_store[call_id]

        return str(response)

    except Exception as e:
        logger.error(f"Error processing voice input webhook: {str(e)}")
        response = VoiceResponse()
        response.say("Sorry, there was an error. Goodbye!", voice="Polly.Emma")
        response.hangup()
        return str(response)


@router.post("/webhook/voice", response_class=PlainTextResponse)
async def handle_voice_webhook(request: Request):
    """
    Handle general voice webhooks from Twilio (fallback)

    This endpoint can be used as a fallback or for handling other voice interactions
    """
    try:
        response = VoiceResponse()
        response.say("Hello! This is a voice webhook response.", voice="alice")
        return str(response)

    except Exception as e:
        logger.error(f"Error processing voice webhook: {str(e)}")
        return str(VoiceResponse())
