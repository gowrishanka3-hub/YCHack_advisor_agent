"""MiniMax TTS for LiveKit Agents.

Uses the global MiniMax API (api.minimax.io) with MINIMAX_API_KEY only.
Defaults: speech-2.8-hd + English_expressive_narrator (api.minimax.io t2a_v2).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from dataclasses import dataclass

import aiohttp

from livekit.agents import APIConnectOptions, tts, utils
from livekit.agents.tokenize import basic
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

from minimax_config import get_tts_speech_url, get_tts_t2a_url

logger = logging.getLogger("minimax-tts")


@dataclass
class _TTSOptions:
    api_key: str
    model: str
    voice_id: str
    language_boost: str
    sample_rate: int
    speed: float
    volume: float
    pitch: int
    base_url: str

    def build_payload(self, text: str) -> dict:
        return {
            "model": self.model,
            "text": text,
            "stream": False,
            "language_boost": self.language_boost,
            "voice_setting": {
                "voice_id": self.voice_id,
                # MiniMax T2A requires integers for speed/vol/pitch (not floats).
                "speed": int(round(self.speed)),
                "vol": int(round(self.volume)),
                "pitch": int(round(self.pitch)),
            },
            "audio_setting": {
                "sample_rate": self.sample_rate,
                "bitrate": 128000,
                "format": "pcm",
                "channel": 1,
            },
        }

    def build_speech_payload(self, text: str) -> dict:
        """OpenAI-compatible /audio/speech payload (reference app.py)."""
        return {
            "model": self.model,
            "voice": self.voice_id,
            "text": text,
        }

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


class TTS(tts.TTS):
    """MiniMax text-to-speech via the global platform API (API key only)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        voice_id: str | None = None,
        language_boost: str = "English",
        sample_rate: int = 24000,
        speed: float = 1.0,
        volume: float = 1.0,
        pitch: int = 0,
        base_url: str | None = None,
        mode: str | None = None,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=sample_rate,
            num_channels=1,
        )
        api_key = (api_key or os.environ.get("MINIMAX_API_KEY") or "").strip()
        if not api_key:
            raise ValueError("MINIMAX_API_KEY is required")

        resolved_model = model or os.environ.get("MINIMAX_TTS_MODEL", "speech-2.8-hd")
        resolved_voice = voice_id or os.environ.get(
            "MINIMAX_VOICE", "English_expressive_narrator"
        )
        resolved_mode = (mode or os.environ.get("MINIMAX_TTS_MODE", "t2a")).lower()
        if resolved_mode == "speech":
            resolved_url = base_url or get_tts_speech_url()
        else:
            resolved_url = base_url or get_tts_t2a_url()

        self._mode = resolved_mode
        self._opts = _TTSOptions(
            api_key=api_key,
            model=resolved_model,
            voice_id=resolved_voice,
            language_boost=language_boost,
            sample_rate=sample_rate,
            speed=speed,
            volume=volume,
            pitch=pitch,
            base_url=resolved_url,
        )
        logger.info(
            "MiniMax TTS: model=%s voice=%s mode=%s url=%s",
            resolved_model,
            resolved_voice,
            resolved_mode,
            resolved_url,
        )
        self._session = http_session
        self._sentence_tokenizer = basic.SentenceTokenizer()

    @property
    def model(self) -> str:
        return self._opts.model

    @property
    def provider(self) -> str:
        return "MiniMax"

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = utils.http_context.http_session()
        return self._session

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ):
        raise NotImplementedError("Use stream() for MiniMax TTS")

    def stream(self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS):
        return _SynthesizeStream(
            tts=self,
            opts=self._opts,
            mode=self._mode,
            session=self._ensure_session(),
            conn_options=conn_options,
            sentence_tokenizer=self._sentence_tokenizer,
        )


class _SynthesizeStream(tts.SynthesizeStream):
    def __init__(
        self,
        *,
        tts: TTS,
        opts: _TTSOptions,
        mode: str,
        session: aiohttp.ClientSession,
        conn_options: APIConnectOptions,
        sentence_tokenizer,
    ) -> None:
        super().__init__(tts=tts, conn_options=conn_options)
        self._opts = opts
        self._mode = mode
        self._session = session
        self._sentence_tokenizer = sentence_tokenizer

    async def _synthesize_sentence(self, sentence: str) -> bytes:
        if self._mode == "speech":
            return await self._synthesize_speech_endpoint(sentence)
        return await self._synthesize_t2a(sentence)

    async def _synthesize_t2a(self, sentence: str) -> bytes:
        payload = self._opts.build_payload(sentence)
        async with self._session.post(
            self._opts.base_url,
            json=payload,
            headers=self._opts.headers(),
            timeout=aiohttp.ClientTimeout(
                total=60,
                sock_connect=self._conn_options.timeout,
            ),
        ) as resp:
            resp.raise_for_status()
            body = await resp.json()

        base_resp = body.get("base_resp", {})
        if base_resp.get("status_code", 0) != 0:
            msg = base_resp.get("status_msg", "unknown")
            logger.error(
                "MiniMax TTS failed: %s (voice=%s, model=%s)",
                msg,
                self._opts.voice_id,
                self._opts.model,
            )
            raise RuntimeError(f"MiniMax TTS error: {msg}")

        audio_hex = body.get("data", {}).get("audio", "")
        if not audio_hex:
            raise RuntimeError("MiniMax TTS returned no audio data")

        return bytes.fromhex(audio_hex)

    async def _synthesize_speech_endpoint(self, sentence: str) -> bytes:
        """Reference app.py: POST {base}/audio/speech with model, voice, text."""
        payload = self._opts.build_speech_payload(sentence)
        async with self._session.post(
            self._opts.base_url,
            json=payload,
            headers=self._opts.headers(),
            timeout=aiohttp.ClientTimeout(
                total=60,
                sock_connect=self._conn_options.timeout,
            ),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"MiniMax speech API failed {resp.status}: {text}")

            content_type = resp.headers.get("content-type", "")
            if content_type.startswith("audio/"):
                return await resp.read()

            body = await resp.json()
            for key in ("audio", "audio_content", "audio_data", "audio_base64", "output_audio"):
                if key in body and body[key]:
                    return base64.b64decode(body[key])

        raise RuntimeError("MiniMax speech API returned no audio data")

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        request_id = utils.shortuuid()
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._opts.sample_rate,
            num_channels=1,
            mime_type="audio/pcm",
            stream=True,
        )

        sent_stream = self._sentence_tokenizer.stream()

        # A SynthesizeStream maps to exactly ONE logical segment in LiveKit's TTS
        # contract. We sentence-split only to stream audio out incrementally, but
        # all sentences must be pushed inside a single start/end_segment pair —
        # otherwise the framework raises "number of segments mismatch".
        output_emitter.start_segment(segment_id=request_id)

        async def _input_task() -> None:
            async for data in self._input_ch:
                if isinstance(data, self._FlushSentinel):
                    sent_stream.flush()
                    continue
                sent_stream.push_text(data)
            sent_stream.end_input()

        async def _sentence_task() -> None:
            try:
                async for ev in sent_stream:
                    sentence = ev.token.strip()
                    if not sentence:
                        continue

                    logger.info("MiniMax TTS synthesizing (%d chars)", len(sentence))
                    audio = await self._synthesize_sentence(sentence)
                    output_emitter.push(audio)
            except Exception:
                logger.exception("MiniMax TTS stream failed")
                raise

        await asyncio.gather(_input_task(), _sentence_task())
        output_emitter.end_segment()
