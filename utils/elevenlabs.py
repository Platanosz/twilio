import os
import uuid
import requests
import logging
from typing import Optional
from fastapi import Request
from config import ELEVENLABS_API_KEY, AUDIO_DIR

logger = logging.getLogger(__name__)


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
