import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import agent


class TestAgentEntrypoint(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ.pop("MOSS_PROJECT_ID", None)
        os.environ.pop("MOSS_PROJECT_KEY", None)

    @patch("agent.AgentSession")
    async def test_entrypoint_uses_minimax_tts_and_starts_room(
        self,
        MockAgentSession,
    ):
        mock_ctx = MagicMock()
        mock_ctx.proc.userdata = {"vad": "vad-instance"}
        mock_ctx.room = MagicMock(name="room")
        mock_ctx.room.name = "test-room"
        mock_ctx.connect = AsyncMock()

        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.generate_reply = AsyncMock()
        MockAgentSession.return_value = mock_session

        await agent.entrypoint(mock_ctx)

        MockAgentSession.assert_called_once()
        _, kwargs = MockAgentSession.call_args
        self.assertEqual(kwargs["stt"], "cartesia/ink-2")
        self.assertIsInstance(kwargs["tts"], agent.minimax.TTS)
        self.assertEqual(kwargs["vad"], "vad-instance")

        mock_session.start.assert_awaited_once_with(
            agent=unittest.mock.ANY,
            room=mock_ctx.room,
            room_options=agent.room_io.RoomOptions(),
        )
        mock_session.generate_reply.assert_awaited_once()
