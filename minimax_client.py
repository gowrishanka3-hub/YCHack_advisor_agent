"""MiniMax LLM client fixes for LiveKit Agents.

Fixes for the global MiniMax OpenAI endpoint:
- Omits ``stream_options`` (causes 500 on some accounts)
- Disables thinking mode for faster, reliable voice replies
- Falls back to non-streaming when streaming returns 500
- Strips ``<think>`` blocks from spoken output
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

import httpx
import openai
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessage
from openai.types.chat.chat_completion_chunk import Choice

from livekit.agents import APIConnectionError, APIStatusError, APITimeoutError, llm
from livekit.agents.llm import ToolChoice
from livekit.agents.llm.chat_context import ChatContext
from livekit.agents.llm.tool_context import FunctionTool
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)
from livekit.agents.utils import is_given
from livekit.plugins.minimax import llm as minimax_llm
from livekit.plugins.minimax.utils import to_chat_ctx, to_fnc_ctx

from minimax_config import get_llm_base_url

logger = logging.getLogger("academic-advisor")

_THINKING_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

_RETRYABLE_STATUS = {500, 502, 503, 529}


def _env_int(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name) or "").strip())
    except (TypeError, ValueError):
        return default


def _strip_thinking(text: str | None) -> str | None:
    if not text:
        return text
    cleaned = _THINKING_RE.sub("", text).strip()
    return cleaned or None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _prepare_request_kwargs(extra: dict) -> dict:
    """Build OpenAI SDK kwargs, passing MiniMax-only params via extra_body."""
    kwargs = dict(extra)
    kwargs.setdefault("max_completion_tokens", 1024)
    kwargs.pop("parallel_tool_calls", None)
    kwargs.pop("thinking", None)

    thinking_type = (os.environ.get("MINIMAX_THINKING") or "disabled").strip()
    if thinking_type:
        extra_body = dict(kwargs.pop("extra_body", {}) or {})
        extra_body["thinking"] = {"type": thinking_type}
        kwargs["extra_body"] = extra_body

    return kwargs


class FixedLLMStream(minimax_llm.LLMStream):
    async def _run(self) -> None:
        self._tool_call_id: str | None = None
        self._fnc_name: str | None = None
        self._fnc_raw_arguments: str | None = None
        self._tool_index: int | None = None
        retryable = True

        kwargs = _prepare_request_kwargs(dict(self._extra_kwargs))
        messages = to_chat_ctx(self._chat_ctx, id(self._llm))
        tools = to_fnc_ctx(self._tools) if self._tools else openai.NOT_GIVEN
        use_stream = _env_bool("MINIMAX_LLM_STREAM", False)

        try:
            if use_stream:
                try:
                    await self._run_stream(messages, tools, kwargs)
                    return
                except openai.APIStatusError as e:
                    if e.status_code not in {500, 502, 503, 529}:
                        raise
                    logger.warning(
                        "MiniMax stream failed (%s), falling back to non-stream",
                        e.status_code,
                    )
                except Exception as e:
                    logger.warning(
                        "MiniMax stream error (%s), falling back to non-stream",
                        e,
                    )
            await self._run_non_stream(messages, tools, kwargs)
            retryable = False
            logger.info("MiniMax llm end (non-stream)")

        except openai.APITimeoutError:
            raise APITimeoutError(retryable=retryable)  # noqa: B904
        except openai.APIStatusError as e:
            logger.error(
                "MiniMax LLM API error %s: messages=%s tools=%s stream=%s",
                e.status_code,
                len(messages),
                len(self._tools) if self._tools else 0,
                use_stream,
            )
            raise APIStatusError(  # noqa: B904
                e.message,
                status_code=e.status_code,
                request_id=e.request_id,
                body=e.body,
                retryable=retryable,
            )
        except Exception as e:
            raise APIConnectionError(retryable=retryable) from e

    async def _create_with_retry(self, **params):
        """Retry MiniMax's flaky 5xx ("unknown error (1000)") with backoff.

        MiniMax-M3's endpoint intermittently returns 500 on otherwise-valid
        requests. A few quick retries absorb most of these transient blips so a
        single bad turn doesn't kill the reply (important when no LLM fallback
        is configured). Tune with MINIMAX_MAX_RETRIES (default 3).
        """
        attempts = max(0, _env_int("MINIMAX_MAX_RETRIES", 3))
        delay = 0.5
        last_exc: openai.APIStatusError | None = None
        for i in range(attempts + 1):
            try:
                return await self._client.chat.completions.create(**params)
            except openai.APIStatusError as e:
                if e.status_code not in _RETRYABLE_STATUS:
                    raise
                last_exc = e
                if i < attempts:
                    logger.warning(
                        "MiniMax %s, retrying in %.1fs (attempt %d/%d)",
                        e.status_code,
                        delay,
                        i + 1,
                        attempts,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 4.0)
        assert last_exc is not None
        raise last_exc

    async def _run_stream(
        self,
        messages: list,
        tools,
        kwargs: dict,
    ) -> None:
        first_response = True
        stream: openai.AsyncStream[ChatCompletionChunk] = await self._create_with_retry(
            messages=messages,
            tools=tools,
            model=self._model,
            stream=True,
            **kwargs,
        )

        async with stream:
            async for chunk in stream:
                for choice in chunk.choices:
                    chat_chunk = self._parse_choice(chunk.id, choice)
                    if chat_chunk is not None:
                        self._event_ch.send_nowait(chat_chunk)
                    if first_response:
                        logger.info("MiniMax llm first response (stream)")
                        first_response = False

                if chunk.usage is not None:
                    self._event_ch.send_nowait(
                        llm.ChatChunk(
                            id=chunk.id,
                            usage=llm.CompletionUsage(
                                completion_tokens=chunk.usage.completion_tokens,
                                prompt_tokens=chunk.usage.prompt_tokens,
                                total_tokens=chunk.usage.total_tokens,
                            ),
                        )
                    )
        logger.info("MiniMax llm end (stream)")

    async def _run_non_stream(
        self,
        messages: list,
        tools,
        kwargs: dict,
    ) -> None:
        response = await self._create_with_retry(
            messages=messages,
            tools=tools,
            model=self._model,
            stream=False,
            **kwargs,
        )
        choice = response.choices[0]
        message: ChatCompletionMessage = choice.message
        chunk_id = response.id

        if message.tool_calls:
            for tool in message.tool_calls:
                if not tool.function:
                    continue
                self._event_ch.send_nowait(
                    llm.ChatChunk(
                        id=chunk_id,
                        delta=llm.ChoiceDelta(
                            role="assistant",
                            tool_calls=[
                                llm.FunctionToolCall(
                                    arguments=tool.function.arguments or "",
                                    name=tool.function.name or "",
                                    call_id=tool.id or "",
                                )
                            ],
                        ),
                    )
                )
            logger.info("MiniMax llm first response (non-stream, tools)")
            return

        content = _strip_thinking(message.content)
        if content:
            self._event_ch.send_nowait(
                llm.ChatChunk(
                    id=chunk_id,
                    delta=llm.ChoiceDelta(content=content, role="assistant"),
                )
            )
            logger.info("MiniMax llm first response (non-stream)")

        if response.usage is not None:
            self._event_ch.send_nowait(
                llm.ChatChunk(
                    id=chunk_id,
                    usage=llm.CompletionUsage(
                        completion_tokens=response.usage.completion_tokens,
                        prompt_tokens=response.usage.prompt_tokens,
                        total_tokens=response.usage.total_tokens,
                    ),
                )
            )

    def _parse_choice(self, id: str, choice: Choice) -> llm.ChatChunk | None:
        delta = choice.delta
        if delta is None:
            return None

        if delta.content:
            delta.content = _strip_thinking(delta.content)

        if delta.tool_calls:
            for tool in delta.tool_calls:
                if not tool.function:
                    continue

                call_chunk = None
                if self._tool_call_id and tool.id and tool.index != self._tool_index:
                    call_chunk = llm.ChatChunk(
                        id=id,
                        delta=llm.ChoiceDelta(
                            role="assistant",
                            content=delta.content,
                            tool_calls=[
                                llm.FunctionToolCall(
                                    arguments=self._fnc_raw_arguments or "",
                                    name=self._fnc_name or "",
                                    call_id=self._tool_call_id or "",
                                )
                            ],
                        ),
                    )
                    self._tool_call_id = self._fnc_name = self._fnc_raw_arguments = None

                if tool.function.name:
                    self._tool_index = tool.index
                    self._tool_call_id = tool.id
                    self._fnc_name = tool.function.name
                    self._fnc_raw_arguments = tool.function.arguments or ""
                elif tool.function.arguments:
                    self._fnc_raw_arguments += tool.function.arguments  # type: ignore

                if call_chunk is not None:
                    return call_chunk

        if choice.finish_reason in ("tool_calls", "stop") and self._tool_call_id:
            call_chunk = llm.ChatChunk(
                id=id,
                delta=llm.ChoiceDelta(
                    role="assistant",
                    content=delta.content,
                    tool_calls=[
                        llm.FunctionToolCall(
                            arguments=self._fnc_raw_arguments or "",
                            name=self._fnc_name or "",
                            call_id=self._tool_call_id or "",
                        )
                    ],
                ),
            )
            self._tool_call_id = self._fnc_name = self._fnc_raw_arguments = None
            return call_chunk

        if not delta.content:
            return None

        return llm.ChatChunk(
            id=id,
            delta=llm.ChoiceDelta(content=delta.content, role="assistant"),
        )


class FixedMiniMaxLLM(minimax_llm.LLM):
    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list[FunctionTool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict] = NOT_GIVEN,
    ) -> FixedLLMStream:
        extra: dict = {}
        if is_given(extra_kwargs):
            extra.update(extra_kwargs)

        if is_given(self._opts.metadata):
            extra["metadata"] = self._opts.metadata
        if is_given(self._opts.user):
            extra["user"] = self._opts.user

        tool_choice_val = (
            tool_choice if is_given(tool_choice) else self._opts.tool_choice  # type: ignore
        )
        if is_given(tool_choice_val):
            if isinstance(tool_choice_val, dict):
                extra["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tool_choice_val["function"]["name"]},
                }
            elif tool_choice_val in ("auto", "required", "none"):
                extra["tool_choice"] = tool_choice_val

        logger.info("MiniMax llm start", extra={"model": self._opts.model})
        return FixedLLMStream(
            self,
            model=self._opts.model,
            client=self._client,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            extra_kwargs=extra,
        )


def build_minimax_llm() -> FixedMiniMaxLLM:
    api_key = (os.environ.get("MINIMAX_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("MINIMAX_API_KEY is required in .env.local")

    base_url = get_llm_base_url()
    model = os.environ.get("MINIMAX_LLM_MODEL", "MiniMax-M3")
    logger.info("MiniMax LLM: model=%s base_url=%s", model, base_url)

    client = openai.AsyncClient(
        api_key=api_key,
        base_url=base_url,
        max_retries=0,
        http_client=httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=5.0),
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=50,
                keepalive_expiry=120,
            ),
        ),
    )
    return FixedMiniMaxLLM(model=model, client=client)
