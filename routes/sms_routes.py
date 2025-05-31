import uuid
import logging
import httpx
from typing import Optional, Dict
from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from config import twilio_client, TWILIO_PHONE_NUMBER
from pydantic import BaseModel
from utils.elevenlabs import generate_elevenlabs_audio

logger = logging.getLogger(__name__)

# Simple in-memory storage for call data (in production, use a database)
call_data_store: Dict[str, Dict] = {}

router = APIRouter()

# Langflow webhook URL
LANGFLOW_WEBHOOK_URL = "https://e7ef-158-106-193-162.ngrok-free.app/api/v1/webhook/2cda71d5-0c31-4dbb-bce3-904dfb78b9f9"

# Default phone number to call for webhook test (CHANGE THIS TO YOUR ACTUAL PHONE NUMBER)
DEFAULT_TEST_PHONE_NUMBER = (
    "+2013905648"  # Replace with actual phone number you want to call
)


class WebhookPayload(BaseModel):
    number: str
    message: str


@router.post("/webhook/test", response_class=PlainTextResponse)
async def handle_sms_webhook(request: Request):
    """
    Test webhook endpoint that makes a call with ElevenLabs TTS

    Expects request body with text content and makes a call to a default number
    speaking the text using ElevenLabs text-to-speech.
    """
    try:
        # Read the request body
        body = await request.body()
        text_content = body.decode("utf-8")

        print(f"Raw request body: {text_content}", flush=True)

        # Try to parse as JSON first
        message_text = text_content
        phone_number = DEFAULT_TEST_PHONE_NUMBER

        try:
            import json

            json_data = json.loads(text_content)
            print(f"Parsed JSON: {json_data}", flush=True)

            # Extract message and phone number from JSON if available
            if isinstance(json_data, dict):
                message_text = json_data.get(
                    "message", json_data.get("text", text_content)
                )
                phone_number = json_data.get(
                    "phone_number", json_data.get("number", DEFAULT_TEST_PHONE_NUMBER)
                )
            else:
                message_text = str(json_data)

        except Exception as e:
            print(f"Could not parse as JSON, using raw text: {e}", flush=True)
            # Use the raw body as the message text
            message_text = text_content

        # Also try to parse as form data for debugging
        try:
            form_data = await request.form()
            print(f"Form data: {dict(form_data)}", flush=True)
        except Exception as e:
            print(f"Could not parse form data: {e}", flush=True)

        # Print headers for additional context
        print(f"Headers: {dict(request.headers)}", flush=True)
        print(f"Method: {request.method}", flush=True)
        print(f"URL: {request.url}", flush=True)

        # Validate that we have content to speak
        if not message_text or message_text.strip() == "":
            print("No message content found, using default message", flush=True)
            message_text = "Hello, this is a test call from the webhook endpoint."

        # Make the call if Twilio is configured
        if twilio_client and TWILIO_PHONE_NUMBER:
            try:
                # Store message data for use during the call
                call_id = str(uuid.uuid4())
                call_data_store[call_id] = {
                    "sms_body": message_text,
                    "from_number": TWILIO_PHONE_NUMBER,
                    "to_number": phone_number,
                    "message_sid": f"webhook_test_{call_id}",
                }

                # Generate webhook URL for the call
                base_url = str(request.base_url).rstrip("/")
                webhook_url = f"{base_url}/webhook/voice/call/{call_id}"

                # Make the outbound call with webhook URL
                call = twilio_client.calls.create(
                    url=webhook_url,
                    to=phone_number,
                    from_=TWILIO_PHONE_NUMBER,
                )

                logger.info(
                    f"Test webhook call initiated: {call.sid} to {phone_number}"
                )
                logger.info(f"Message to speak: {message_text}")

                print(f"Call initiated successfully! Call SID: {call.sid}", flush=True)
                print(
                    f"Calling {phone_number} with message: {message_text}", flush=True
                )

                return f"Call initiated successfully! Call SID: {call.sid}\nCalling {phone_number} with message: {message_text}"

            except Exception as call_error:
                logger.error(f"Error making test call: {str(call_error)}")
                print(f"Error making call: {str(call_error)}", flush=True)
                return f"Error making call: {str(call_error)}"
        else:
            logger.warning("Twilio not configured, cannot make call")
            print("Twilio not configured, cannot make call", flush=True)
            return f"Twilio not configured. Would have called {phone_number} with message: {message_text}"

    except Exception as e:
        logger.error(f"Error in webhook test: {str(e)}")
        print(f"Error in webhook test: {str(e)}", flush=True)
        return f"Error: {str(e)}"


@router.post("/webhook/sms", response_class=PlainTextResponse)
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

    This endpoint receives SMS messages and sends them to Langflow
    for processing.
    """
    try:
        # Log the incoming SMS details
        logger.info(f"Received SMS from {From} to {To}")
        logger.info(f"Message SID: {MessageSid}")
        logger.info(f"Message Body: {Body}")

        if NumMedia and int(NumMedia) > 0:
            logger.info(f"Media attached: {MediaUrl0} ({MediaContentType0})")

        # Send request to Langflow
        try:
            async with httpx.AsyncClient() as client:
                langflow_payload = {"text": Body, "phone_number": From}

                response = await client.post(
                    LANGFLOW_WEBHOOK_URL, json=langflow_payload, timeout=30.0
                )

                logger.info(
                    f"Langflow request sent successfully. Status: {response.status_code}"
                )
                logger.info(f"Langflow response: {response.text}")

                # Create SMS response confirming the message was processed
                sms_response = MessagingResponse()
                sms_response.message(
                    f"Thanks for your message! I've received and processed: '{Body}'"
                )

        except Exception as langflow_error:
            logger.error(f"Error sending request to Langflow: {str(langflow_error)}")
            # Fallback SMS response if Langflow request fails
            sms_response = MessagingResponse()
            sms_response.message(
                f"Received your message: '{Body}'. Sorry, there was an error processing it."
            )

        # Return TwiML response
        return str(sms_response)

    except Exception as e:
        logger.error(f"Error processing SMS webhook: {str(e)}")
        # Return empty TwiML response on error
        return str(MessagingResponse())


@router.post("/webhook/sms/status", response_class=PlainTextResponse)
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


# Export call_data_store for use in voice routes
def get_call_data_store():
    return call_data_store
