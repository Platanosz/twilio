import uuid
import logging
import httpx
from typing import Optional, Dict
from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from config import twilio_client, TWILIO_PHONE_NUMBER

logger = logging.getLogger(__name__)

# Simple in-memory storage for call data (in production, use a database)
call_data_store: Dict[str, Dict] = {}

router = APIRouter()

# Langflow webhook URL
LANGFLOW_WEBHOOK_URL = "https://e7ef-158-106-193-162.ngrok-free.app/api/v1/webhook/2cda71d5-0c31-4dbb-bce3-904dfb78b9f9"


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
