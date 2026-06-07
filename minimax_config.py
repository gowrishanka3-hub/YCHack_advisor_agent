"""MiniMax API URL and model resolution (aligned with reference app.py)."""

from __future__ import annotations

import os


def get_api_base_url() -> str:
    """Base host for MiniMax APIs.

    Reference app.py uses MINIMAX_API_BASE_URL (default https://minimax.io).
    Official global API host is https://api.minimax.io — both are supported.
    """
    return os.environ.get("MINIMAX_API_BASE_URL", "https://api.minimax.io").rstrip("/")


def get_llm_base_url() -> str:
    """OpenAI-compatible chat completions base URL."""
    override = os.environ.get("MINIMAX_BASE_URL")
    if override:
        return override.rstrip("/")

    base = get_api_base_url()
    if base.endswith("/v1"):
        return base

    region = (os.environ.get("MINIMAX_REGION") or "global").lower()
    if region in {"cn", "china"}:
        return "https://api.minimaxi.com/v1"
    return f"{base}/v1"


def get_tts_t2a_url() -> str:
    """MiniMax T2A v2 HTTP endpoint."""
    override = os.environ.get("MINIMAX_TTS_URL")
    if override:
        return override.rstrip("/")

    base = get_api_base_url()
    if base.endswith("/v1"):
        return f"{base}/t2a_v2"

    region = (os.environ.get("MINIMAX_REGION") or "global").lower()
    if region in {"cn", "china"}:
        return "https://api.minimaxi.com/v1/t2a_v2"
    return f"{base}/v1/t2a_v2"


def get_tts_speech_url() -> str:
    """OpenAI-compatible speech endpoint (may not be available on all regions)."""
    override = os.environ.get("MINIMAX_TTS_SPEECH_URL")
    if override:
        return override.rstrip("/")

    base = get_api_base_url()
    if base.endswith("/v1"):
        return f"{base}/audio/speech"
    return f"{base}/v1/audio/speech"
