import logging
from typing import Optional
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from utils.elevenlabs import generate_elevenlabs_audio
from routes.sms_routes import get_call_data_store
from pydantic import BaseModel
from config import twilio_client, TWILIO_PHONE_NUMBER
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()


class CallRequest(BaseModel):
    message: str
    phone_number: str


@router.post("/call/send")
async def send_call_with_message(call_request: CallRequest, request: Request):
    """
    Send a call with a custom message to a phone number

    This endpoint receives a JSON payload with a message and phone number,
    then initiates an outbound call to deliver that message.
    """
    try:
        if not twilio_client or not TWILIO_PHONE_NUMBER:
            raise HTTPException(status_code=500, detail="Twilio client not configured")

        # Validate phone number format (basic validation)
        if not call_request.phone_number.startswith("+"):
            raise HTTPException(
                status_code=400,
                detail="Phone number must include country code (e.g., +1234567890)",
            )

        # Store message data for use during the call
        call_id = str(uuid.uuid4())
        call_data_store = get_call_data_store()
        call_data_store[call_id] = {
            "sms_body": call_request.message,
            "from_number": TWILIO_PHONE_NUMBER,
            "to_number": call_request.phone_number,
            "message_sid": f"api_call_{call_id}",
        }

        # Generate webhook URL for the call
        base_url = str(request.base_url).rstrip("/")
        webhook_url = f"{base_url}/webhook/voice/call/{call_id}"

        # Make the outbound call with webhook URL
        call = twilio_client.calls.create(
            url=webhook_url,
            to=call_request.phone_number,
            from_=TWILIO_PHONE_NUMBER,
        )

        logger.info(
            f"Outbound call initiated: {call.sid} to {call_request.phone_number} with call_id: {call_id}"
        )

        return {
            "success": True,
            "call_sid": call.sid,
            "call_id": call_id,
            "message": "Call initiated successfully",
            "phone_number": call_request.phone_number,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating call: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate call: {str(e)}"
        )


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
