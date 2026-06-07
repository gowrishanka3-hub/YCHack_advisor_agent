"""Minimal FastAPI server to mint LiveKit tokens for the frontend."""

import os
import random
from datetime import timedelta

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants
from livekit.protocol.room import RoomConfiguration
from livekit.protocol.agent_dispatch import RoomAgentDispatch

load_dotenv(".env.local")

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")
AGENT_NAME = "academic-advisor"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_participant_token(identity: str, name: str, room_name: str) -> str:
    token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token.with_identity(identity).with_name(name).with_ttl(timedelta(minutes=15))
    token.with_grants(
        VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        )
    )
    token.with_room_config(
        RoomConfiguration(
            agents=[RoomAgentDispatch(agent_name=AGENT_NAME)],
        )
    )
    return token.to_jwt()


@app.post("/api/token")
async def get_token():
    if not LIVEKIT_URL or not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        return {"error": "LiveKit credentials not configured in .env.local"}

    room_name = f"advisor_room_{random.randint(1000, 9999)}"
    identity = f"student_{random.randint(1000, 9999)}"
    participant_name = "Student"

    participant_token = create_participant_token(identity, participant_name, room_name)

    return {
        "serverUrl": LIVEKIT_URL,
        "roomName": room_name,
        "participantToken": participant_token,
        "participantName": participant_name,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
