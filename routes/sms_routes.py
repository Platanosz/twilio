import uuid
import logging
from typing import Optional, Dict
from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from config import twilio_client, TWILIO_PHONE_NUMBER

logger = logging.getLogger(__name__)

# Simple in-memory storage for call data (in production, use a database)
call_data_store: Dict[str, Dict] = {}

router = APIRouter()


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
                # Store SMS data for use during the call
                call_id = str(uuid.uuid4())
                call_data_store[call_id] = {
                    "sms_body": Body,
                    "from_number": From,
                    "to_number": To,
                    "message_sid": MessageSid,
                }

                # Generate webhook URL for the call
                base_url = str(request.base_url).rstrip("/")
                webhook_url = f"{base_url}/webhook/voice/call/{call_id}"

                # Make the outbound call with webhook URL
                call = twilio_client.calls.create(
                    url=webhook_url,
                    to=From,  # Call the person who sent the SMS
                    from_=TWILIO_PHONE_NUMBER,  # Use your Twilio phone number
                )

                logger.info(
                    f"Outbound call initiated: {call.sid} to {From} with call_id: {call_id}"
                )

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
