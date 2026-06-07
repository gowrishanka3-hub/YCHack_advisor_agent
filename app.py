import base64
import os
import subprocess
import tempfile
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="Minimax TTS API",
    description="Convert text to voice using the Minimax API key and play audio locally.",
)

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
# Fix 1: Ensure default fallback points to the valid .io address
MINIMAX_API_BASE_URL = os.getenv("MINIMAX_API_BASE_URL", "https://minimax.io")
# Fix 2: Change OpenAI "alloy" to an official MiniMax voice
DEFAULT_VOICE = os.getenv("MINIMAX_VOICE", "male-qn-reading") 
DEFAULT_AUDIO_FORMAT = os.getenv("MINIMAX_AUDIO_FORMAT", "mp3")


class TTSRequest(BaseModel):
    text: str = "hello world"
    voice: Optional[str] = None
    audio_format: Optional[str] = None


def _get_minimax_url() -> str:
    return MINIMAX_API_BASE_URL.rstrip("/") + "/audio/speech"


def _decode_audio_from_response(response: requests.Response) -> bytes:
    content_type = response.headers.get("content-type", "")

    if content_type.startswith("audio/"):
        return response.content

    # If the API returns JSON, extract base64 encoded strings safely
    data = response.json()
    if isinstance(data, dict):
        for key in ("audio", "audio_content", "audio_data", "audio_base64", "output_audio"):
            if key in data and data[key]:
                return base64.b64decode(data[key])

    raise ValueError("Minimax response did not include audio data.")


def minimax_tts(text: str, voice: str, audio_format: str) -> bytes:
    if not MINIMAX_API_KEY:
        raise RuntimeError("Missing MINIMAX_API_KEY in environment.")

    url = _get_minimax_url()
    
    # Fix 3: Alter payload parameters to match MiniMax API definitions
    payload = {
        "model": "speech-01-turbo",  # Replaced invalid gpt-4o-mini-tts model name
        "voice": voice,
        "text": text,                # Changed from "input" to "text"
    }
    
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(
            f"Minimax API request failed {response.status_code}: {response.text}"
        )

    return _decode_audio_from_response(response)


def save_audio_to_file(audio_bytes: bytes, audio_format: str) -> str:
    suffix = f".{audio_format.lstrip('.') or 'mp3'}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(audio_bytes)
        return tmp_file.name


def play_audio_file(audio_path: str) -> None:
    if os.name == "posix":
        subprocess.run(["afplay", audio_path], check=False)
    else:
        raise RuntimeError("Audio playback is supported only on macOS using afplay.")


def fallback_mac_say(text: str) -> None:
    subprocess.run(["say", text], check=False)


def generate_and_play(text: str, voice: str, audio_format: str) -> dict:
    try:
        audio_bytes = minimax_tts(text, voice, audio_format)
        audio_path = save_audio_to_file(audio_bytes, audio_format)
        play_audio_file(audio_path)
        return {
            "text": text,
            "source": "minimax",
            "audio_file": audio_path,
            "status": "played",
        }
    except Exception as exc:
        import traceback
        traceback.print_exc() #
        fallback_mac_say(text)
        return {
            "text": text,
            "source": "fallback",
            "error": str(exc),
            "status": "played_with_local_say",
        }


@app.get("/hello")
def hello_world(
    text: str = "hello world",
    voice: str = DEFAULT_VOICE,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
) -> dict:
    """Generate and play any text using Minimax TTS."""
    return generate_and_play(text, voice, audio_format)


@app.post("/speak")
def speak(request: TTSRequest) -> dict:
    voice = request.voice or DEFAULT_VOICE
    audio_format = request.audio_format or DEFAULT_AUDIO_FORMAT
    return generate_and_play(request.text, voice, audio_format)
