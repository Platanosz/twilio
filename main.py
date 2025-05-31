from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import logging
from config import AUDIO_DIR
from routes import sms_routes, voice_routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Twilio SMS Webhook Server", version="1.0.0")

# Mount static files for serving audio
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

# Include route modules
app.include_router(sms_routes.router, tags=["SMS"])
app.include_router(voice_routes.router, tags=["Voice"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Twilio SMS Webhook Server is running!"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5002)
