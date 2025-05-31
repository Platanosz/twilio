# Twilio SMS Webhook Server

A FastAPI server that handles SMS webhooks from Twilio and automatically calls back the sender to read their message aloud.

## Features

- ✅ Receive SMS messages via Twilio webhooks
- ✅ **Automatic callback calls** - Calls the sender and reads their SMS message aloud
- ✅ TwiML response generation for both SMS and voice
- ✅ SMS delivery status tracking
- ✅ Comprehensive logging
- ✅ Health check endpoint
- ✅ Docker support for easy deployment
- ✅ Environment variable configuration

## How It Works

1. Someone sends an SMS to your Twilio phone number
2. The webhook receives the SMS
3. The server automatically calls the sender back
4. During the call, it reads their SMS message aloud using text-to-speech
5. The sender receives an SMS confirmation with the call SID

## Setup

### Environment Variables

First, copy the example environment file and configure your Twilio credentials:

```bash
cp .env.example .env
```

Edit `.env` with your Twilio credentials:
```bash
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
```

Get these values from your [Twilio Console](https://console.twilio.com/).

### Option 1: Docker (Recommended)

The easiest way to run the server is using Docker:

```bash
# Build and run with docker-compose
docker-compose build && docker-compose up

# Or run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

The server will be available at `http://localhost:5002`

#### Production Docker Setup

For production deployment, use the production compose file:

```bash
# Production build and run
docker-compose -f docker-compose.prod.yml build && docker-compose -f docker-compose.prod.yml up -d

# View production logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Option 2: Local Development

#### 1. Install Dependencies

```bash
# Activate your virtual environment
source .venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

#### 2. Run the Server

```bash
# Development server
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 5002
```

### 3. Expose Your Local Server (for development)

Since Twilio needs to reach your webhook endpoint, you'll need to expose your local server to the internet. You can use ngrok:

```bash
# Install ngrok if you haven't already
# Then expose your local server
ngrok http 5002
```

This will give you a public URL like `https://abc123.ngrok.io`

## Docker Commands

```bash
# Build the image
docker-compose build

# Run the container
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f twilio-webhook

# Stop the container
docker-compose down

# Rebuild and restart
docker-compose down && docker-compose build && docker-compose up

# Access container shell for debugging
docker-compose exec twilio-webhook /bin/bash
```

## Twilio Configuration

### 1. Set up your Twilio Phone Number

1. Log into your [Twilio Console](https://console.twilio.com/)
2. Go to Phone Numbers > Manage > Active numbers
3. Click on your Twilio phone number
4. In the Messaging section, set the webhook URL to:
   ```
   https://your-ngrok-url.ngrok.io/webhook/sms
   ```
5. Set the HTTP method to `POST`
6. Optionally, set the status callback URL to:
   ```
   https://your-ngrok-url.ngrok.io/webhook/sms/status
   ```

### 2. Test Your Setup

Send an SMS to your Twilio phone number. You should:
- Receive an SMS confirmation
- Get a phone call where your message is read back to you
- See logs in your server console

## API Endpoints

### `GET /`
Health check endpoint that returns server status.

### `POST /webhook/sms`
Main webhook endpoint for receiving SMS messages from Twilio.

**What it does:**
1. Receives the SMS message
2. Makes an outbound call to the sender
3. Reads the SMS message aloud during the call
4. Sends an SMS confirmation with the call SID

**Expected Form Data:**
- `MessageSid`: Unique identifier for the message
- `From`: Sender's phone number
- `To`: Recipient's phone number (your Twilio number)
- `Body`: Message content
- `AccountSid`: Your Twilio Account SID
- `NumMedia`: Number of media attachments (optional)
- `MediaUrl0`: URL of first media attachment (optional)

**Response:** TwiML XML for SMS confirmation

### `POST /webhook/sms/status`
Webhook endpoint for SMS delivery status updates.

### `POST /webhook/voice`
Voice webhook endpoint for handling voice interactions (optional).

## Example Flow

1. **User sends SMS**: "Hello, this is a test message!"
2. **Server receives SMS**: Logs the message and sender info
3. **Server makes call**: Calls the sender's phone number
4. **Call content**: "Hello! You sent the following message: Hello, this is a test message! Thank you for your message. Goodbye!"
5. **SMS confirmation**: "Thanks for your message! I'm calling you now to read it back. Call SID: CA1234567890abcdef"

## Bot Commands

The sample bot responds to these commands:
- `hello` - Returns a greeting message
- `help` - Shows available commands
- `echo [message]` - Echoes back your message
- Any other text - Returns a generic response with the original message

## Customization

### Adding Custom Logic

Modify the `handle_sms_webhook` function in `main.py` to add your own message processing logic:

```python
# Example: Add a weather command
elif Body.lower().startswith("weather "):
    city = Body[8:]  # Remove "weather " prefix
    # Add your weather API logic here
    response.message(f"Weather for {city}: [Your weather data]")
```

### Database Integration

You can add database functionality to store messages, user preferences, etc.:

```python
# Example with SQLAlchemy
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Add your database models and logic
```

### Environment Variables

For production, consider using environment variables for configuration:

```python
import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
```

## Security Considerations

For production use, consider adding:
- Twilio request signature validation
- Rate limiting
- Input sanitization
- HTTPS enforcement
- Environment-based configuration

## Troubleshooting

### Common Issues

1. **Webhook not receiving messages:**
   - Check that your ngrok tunnel is active
   - Verify the webhook URL in Twilio console
   - Check server logs for errors

2. **TwiML errors:**
   - Ensure your response returns valid TwiML XML
   - Check for proper Content-Type headers

3. **Server not starting:**
   - Verify all dependencies are installed
   - Check for port conflicts

### Logs

The server logs all incoming messages and errors. Check the console output for debugging information.

## Next Steps

- Add database persistence for messages
- Implement user sessions and context
- Add support for MMS (multimedia messages)
- Integrate with external APIs (weather, news, etc.)
- Add authentication and user management
- Deploy to a cloud platform (Heroku, AWS, etc.) 