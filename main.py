from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
import logging
import os
from typing import Optional
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from dotenv import load_dotenv
import requests
import tempfile
import uuid

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Twilio SMS Webhook Server", version="1.0.0")

# Create audio directory if it doesn't exist
AUDIO_DIR = "audio_files"
os.makedirs(AUDIO_DIR, exist_ok=True)

# Mount static files for serving audio
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

# Twilio configuration - you'll need to set these environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# ElevenLabs configuration
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"
)  # Default to Rachel voice

# Initialize Twilio client if credentials are provided
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
else:
    logger.warning(
        "Twilio credentials not found. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER environment variables."
    )


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Twilio SMS Webhook Server is running!"}


@app.post("/webhook/sms", response_class=PlainTextResponse)
async def handle_sms_webhook(
    request: Request,
    MessageSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    AccountSid: Optional[str] = Form(None),
    NumMedia: Optional[str] = Form(None),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
):
    """
    Handle incoming SMS webhooks from Twilio

    This endpoint receives SMS messages and makes an outbound call
    to the sender using the SMS body as the spoken text.
    """
    try:
        # Log the incoming SMS details
        logger.info(f"Received SMS from {From} to {To}")
        logger.info(f"Message SID: {MessageSid}")
        logger.info(f"Message Body: {Body}")

        if NumMedia and int(NumMedia) > 0:
            logger.info(f"Media attached: {MediaUrl0} ({MediaContentType0})")

        # Make outbound call if Twilio client is available
        if twilio_client and TWILIO_PHONE_NUMBER:
            try:
                # Create TwiML for the call
                call_twiml = VoiceResponse()

                # Try to generate audio with ElevenLabs first
                audio_url = await generate_elevenlabs_audio(Body, request)

                if audio_url:
                    # Use ElevenLabs generated audio
                    call_twiml.play(audio_url)
                    call_twiml.pause(length=1)
                else:
                    # Fallback to Twilio TTS with improved voice
                    call_twiml.say(
                        f"<speak><prosody rate='medium' pitch='high' volume='medium'>{Body}</prosody></speak>",
                        voice="Polly.Emma",  # Cheerful British female voice
                    )
                    call_twiml.pause(length=1)
                    call_twiml.say(
                        "<speak><prosody rate='medium' pitch='high' volume='medium'>Thank you for your message. Goodbye!</prosody></speak>",
                        voice="Polly.Emma",
                    )

                # Make the outbound call
                call = twilio_client.calls.create(
                    twiml=str(call_twiml),
                    to=From,  # Call the person who sent the SMS
                    from_=TWILIO_PHONE_NUMBER,  # Use your Twilio phone number
                )

                logger.info(f"Outbound call initiated: {call.sid} to {From}")

                # Create SMS response confirming the call
                sms_response = MessagingResponse()
                sms_response.message(
                    f"Thanks for your message! I'm calling you now to read it back. Call SID: {call.sid}"
                )

            except Exception as call_error:
                logger.error(f"Error making outbound call: {str(call_error)}")
                # Fallback SMS response if call fails
                sms_response = MessagingResponse()
                sms_response.message(
                    f"Received your message: '{Body}'. Sorry, I couldn't call you back due to an error."
                )
        else:
            # Fallback if Twilio client is not configured
            logger.warning("Twilio client not configured. Cannot make outbound call.")
            sms_response = MessagingResponse()
            sms_response.message(
                f"Received your message: '{Body}'. Twilio calling is not configured."
            )

        # Return TwiML response
        return str(sms_response)

    except Exception as e:
        logger.error(f"Error processing SMS webhook: {str(e)}")
        # Return empty TwiML response on error
        return str(MessagingResponse())


@app.post("/webhook/sms/status", response_class=PlainTextResponse)
async def handle_sms_status_webhook(
    request: Request,
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    To: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    AccountSid: Optional[str] = Form(None),
):
    """
    Handle SMS delivery status webhooks from Twilio

    This endpoint receives status updates for SMS messages (delivered, failed, etc.)
    """
    try:
        logger.info(f"SMS Status Update - SID: {MessageSid}, Status: {MessageStatus}")
        if To and From:
            logger.info(f"Message from {From} to {To} status: {MessageStatus}")

        # You can add custom logic here to handle different status updates
        # For example, update a database, send notifications, etc.

        return ""  # Empty response for status webhooks

    except Exception as e:
        logger.error(f"Error processing SMS status webhook: {str(e)}")
        return ""


@app.post("/webhook/voice", response_class=PlainTextResponse)
async def handle_voice_webhook(request: Request):
    """
    Handle voice webhooks from Twilio (for outbound calls)

    This endpoint can be used as a fallback or for handling voice interactions
    """
    try:
        response = VoiceResponse()
        response.say("Hello! This is a voice webhook response.", voice="alice")
        return str(response)

    except Exception as e:
        logger.error(f"Error processing voice webhook: {str(e)}")
        return str(VoiceResponse())


async def generate_elevenlabs_audio(text: str, request: Request) -> Optional[str]:
    """
    Generate audio using ElevenLabs API and return a publicly accessible URL

    Returns the URL of the generated audio file, or None if generation fails
    """
    if not ELEVENLABS_API_KEY:
        logger.warning("ElevenLabs API key not found")
        return None

    try:
        # ElevenLabs API endpoint
        url = f"https://api.elevenlabs.io/v1/text-to-speech/N2lVS1w4EtoT3dr4eOWO"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY,
        }

        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5,
                "style": 0.5,  # More expressive
                "use_speaker_boost": True,
            },
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            # Generate unique filename
            filename = f"{uuid.uuid4()}.mp3"
            filepath = os.path.join(AUDIO_DIR, filename)

            # Save audio file
            with open(filepath, "wb") as f:
                f.write(response.content)

            # Return public URL
            base_url = str(request.base_url).rstrip("/")
            audio_url = f"{base_url}/audio/{filename}"

            logger.info(f"ElevenLabs audio generated: {audio_url}")
            return audio_url
        else:
            logger.error(
                f"ElevenLabs API error: {response.status_code} - {response.text}"
            )
            return None

    except Exception as e:
        logger.error(f"Error generating ElevenLabs audio: {str(e)}")
        return None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5002)
