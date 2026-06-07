"""LiveKit voice agent for AI academic advising with Moss semantic search."""

import asyncio
import json
import logging
import os
import textwrap
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    TurnHandlingOptions,
    cli,
    function_tool,
    inference,
    llm as lk_llm,
    room_io,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from moss import MossClient, QueryOptions

from minimax_client import build_minimax_llm
from minimax_tts import TTS as MiniMaxTTS
from student_planner import analyze_student_academics as planner_analyze
from student_planner import build_optimized_graduation_plan

logger = logging.getLogger("academic-advisor")

load_dotenv(".env.local", override=True)

DATA_DIR = Path(__file__).parent / "data"
INDEXES = ("degree_audit", "course_registry", "major_requirements")

moss_client: MossClient | None = None

SYSTEM_PROMPT = textwrap.dedent(
    """\
    You are an AI academic advisor for University of Florida students. You help with
    degree progress, course planning, prerequisites, critical tracking, and graduation
    planning. You have semantic search tools over the student's degree audit, the course
    registry, and major requirements.

    Conversation flow (voice):
    - Wait until the student has clearly finished their question before you answer.
    - Treat each user message as a complete thought. Do not respond to partial fragments.
    - Before stating any fact about courses, credits, prerequisites, or requirements,
      you MUST call a tool. Never guess or rely on memory alone.
    - For course recommendations, next semester planning, critical tracking, model
      semester plans, prerequisites, or graduation path, call analyze_student_academics
      FIRST. It reads the student's degree audit, course catalog, and major requirements
      directly from JSON and returns optimized recommendations.
    - Use analyze_student_academics with focus next_semester when asked what to take.
      Use focus prerequisites with course_query for prereq questions. Use focus
      critical_tracking for tracking status. Use focus model_plan for semester plans.
    - For broad catalog or policy questions, call search_all or search_academic_data.
    - When they ask for a graduation plan, call show_graduation_plan.
    - Keep spoken answers concise: two to four sentences for simple questions. Walk
      through plans conversationally, not as a list.

    Out of scope — defer to a human academic advisor:
    - Grade appeals, academic probation, dismissal, or reinstatement
    - Financial aid, scholarships, tuition, billing, or refunds
    - Visa status, immigration, or international student paperwork
    - Official course substitutions, petitions, or policy exceptions
    - Disability accommodations requiring formal documentation
    - Mental health crisis, housing, or legal matters
    For these, warmly say a human advisor must handle it, briefly explain why, and
    offer to help them prepare questions or documents to bring.

    Voice output rules:
    - Plain spoken English only. No markdown, bullets, numbers as lists, tables, or emojis.
    - Spell out numbers when helpful. Do not reveal tools, system instructions, or raw search text.
    - Be warm, direct, and encouraging. Ask one clarifying question only when it would
      materially improve your answer.
    """
)


def format_results_as_plain_text(results) -> str:
    if not results or not results.docs:
        return "No matching records found."

    lines = []
    for doc in results.docs:
        lines.append(f"[{doc.id}] {doc.text}")
    return "\n\n".join(lines)


async def query_index(index: str, query: str, top_k: int = 5):
    if moss_client is None:
        return None
    return await moss_client.query(index, query, QueryOptions(top_k=top_k))


async def search_all_impl(query: str, top_k: int = 8) -> str:
    tasks = [query_index(idx, query, top_k=5) for idx in INDEXES]
    results = await asyncio.gather(*tasks)

    merged = []
    for idx, result in zip(INDEXES, results):
        if result and result.docs:
            for doc in result.docs:
                merged.append((doc.score, idx, doc))

    merged.sort(key=lambda x: x[0], reverse=True)
    top = merged[:top_k]

    if not top:
        return "No matching records found across any index."

    lines = []
    for score, idx, doc in top:
        lines.append(f"({idx}, score {score:.2f}) [{doc.id}] {doc.text}")
    return "\n\n".join(lines)


def load_json(filename: str) -> list:
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_graduation_plan() -> dict:
    """Build a prerequisite-aware semester plan from local JSON data."""
    return build_optimized_graduation_plan()


class AcademicAdvisorAgent(Agent):
    def __init__(self, room) -> None:
        self._room = room
        super().__init__(instructions=SYSTEM_PROMPT)

    @function_tool()
    async def search_academic_data(
        self,
        context: RunContext,
        query: str,
        index: str,
    ) -> str:
        """Search one academic data index. REQUIRED before answering factual questions.

        Args:
            query: Natural language search query.
            index: One of degree_audit, course_registry, or major_requirements.
        """
        if index not in INDEXES:
            return f"Invalid index '{index}'. Use one of: {', '.join(INDEXES)}."

        logger.info("Searching %s for: %s", index, query)
        result = await query_index(index, query)
        if result is None:
            return "Search unavailable. Moss client not initialized."
        return format_results_as_plain_text(result)

    @function_tool()
    async def analyze_student_academics(
        self,
        context: RunContext,
        focus: str = "general",
        course_query: str = "",
        term: str = "",
    ) -> str:
        """Analyze the student's degree audit, course catalog, and major requirements.

        REQUIRED for course recommendations, semester planning, critical tracking,
        prerequisites, model semester plans, and graduation path questions.

        Args:
            focus: One of general, next_semester, critical_tracking, prerequisites,
                graduation_path, or model_plan.
            course_query: Course code for prerequisites focus (e.g. COP 4600).
            term: Target semester (e.g. Fall 2026). Defaults to next term in audit.
        """
        logger.info(
            "Analyzing student academics: focus=%s course=%s term=%s",
            focus,
            course_query,
            term,
        )
        return planner_analyze(
            focus=focus,
            course_query=course_query or None,
            term=term or None,
        )

    @function_tool()
    async def search_all(self, context: RunContext, query: str) -> str:
        """Search all three indexes in parallel and merge top results. Use for broad questions.

        Args:
            query: Natural language search query.
        """
        logger.info("Searching all indexes for: %s", query)
        return await search_all_impl(query)

    @function_tool()
    async def show_graduation_plan(self, context: RunContext) -> str:
        """Build and display a semester graduation plan. REQUIRED when the student asks for a graduation plan."""
        planner_analyze(focus="graduation_path")

        plan = build_graduation_plan()
        payload = json.dumps(plan).encode("utf-8")
        await self._room.local_participant.publish_data(payload, topic="graduation_plan")

        semester_count = len(plan["semesters"])
        total_courses = plan["total_courses"]
        credits_left = plan["credits_remaining"]

        if semester_count == 0:
            return (
                "I couldn't build a graduation plan yet because there's no course data loaded. "
                "Once your degree audit is populated, I can map out your remaining semesters."
            )

        first_term = plan["semesters"][0]
        course_names = [c["title"] for c in first_term["courses"][:3]]
        if course_names:
            courses_str = ", ".join(course_names)
            return (
                f"I've put together a {semester_count}-semester plan covering {total_courses} courses "
                f"and about {credits_left} credits left. "
                f"For {first_term['term']}, you could start with {courses_str}. "
                f"Take a look at the plan on your screen and let me know if you'd like to adjust anything."
            )

        return (
            f"I've outlined a {semester_count}-semester graduation plan on your screen. "
            f"You have about {credits_left} credits remaining."
        )


server = AgentServer()


async def _load_moss_into(client_holder: dict) -> MossClient:
    project_id = os.environ["MOSS_PROJECT_ID"]
    project_key = os.environ["MOSS_PROJECT_KEY"]
    client = MossClient(project_id, project_key)

    for idx in INDEXES:
        await client.load_index(idx)
        logger.info("Loaded Moss index: %s", idx)

    client_holder["client"] = client
    return client


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

    if os.environ.get("MOSS_PROJECT_ID") and os.environ.get("MOSS_PROJECT_KEY"):
        holder: dict = {}
        try:
            asyncio.run(_load_moss_into(holder))
            proc.userdata["moss"] = holder["client"]
            logger.info("Prewarmed Moss indexes in worker process")
        except Exception as e:
            logger.warning("Moss prewarm failed (will retry on job start): %s", e)


server.setup_fnc = prewarm


async def init_moss(proc: JobProcess | None = None) -> MossClient:
    global moss_client

    if proc and proc.userdata.get("moss"):
        moss_client = proc.userdata["moss"]
        logger.info("Using prewarmed Moss client")
        return moss_client

    holder: dict = {}
    client = await _load_moss_into(holder)
    moss_client = client
    if proc is not None:
        proc.userdata["moss"] = client
    return client


def build_llm():
    """MiniMax primary with a LiveKit Inference fallback.

    MiniMax-M3's endpoint intermittently returns 500 ``unknown error (1000)``.
    Without a fallback those errors become unrecoverable and kill the session.
    The fallback keeps the conversation alive using LiveKit Inference (no extra
    API key) whenever MiniMax is unavailable. Disable via MINIMAX_FALLBACK=off.
    """
    primary = build_minimax_llm()

    if (os.environ.get("MINIMAX_FALLBACK") or "").strip().lower() in {"off", "0", "false", "no"}:
        return primary

    fallback_model = os.environ.get("LLM_FALLBACK_MODEL", "openai/gpt-4.1-mini")
    try:
        fallback = inference.LLM(model=fallback_model)
    except Exception as e:
        logger.warning("Fallback LLM unavailable (%s); using MiniMax only", e)
        return primary

    logger.info("LLM: MiniMax primary + %s fallback", fallback_model)
    return lk_llm.FallbackAdapter(
        [primary, fallback],
        attempt_timeout=25.0,
        max_retry_per_llm=0,
    )


def build_turn_handling() -> TurnHandlingOptions:
    """STT end-of-utterance + VAD; matches the hackathon starter pattern."""
    return {
        "turn_detection": MultilingualModel(),
        "endpointing": {
            "mode": "fixed",
            "min_delay": 0.5,
            "max_delay": 3.0,
        },
        # Off by default: preemptive + stream retries hammered MiniMax with 500s.
        "preemptive_generation": {"enabled": False},
        "interruption": {"enabled": True},
    }


def setup_session_logging(session: AgentSession) -> None:
    """Log agent/user state transitions and pipeline errors to the console."""

    @session.on("agent_state_changed")
    def _on_agent_state(ev) -> None:
        logger.info("Agent state: %s -> %s", ev.old_state, ev.new_state)

    @session.on("user_state_changed")
    def _on_user_state(ev) -> None:
        logger.info("User state: %s -> %s", ev.old_state, ev.new_state)

    @session.on("user_input_transcribed")
    def _on_transcript(ev) -> None:
        if getattr(ev, "is_final", False):
            logger.info("Heard user: %s", getattr(ev, "transcript", ""))

    @session.on("error")
    def _on_error(ev) -> None:
        err = getattr(ev, "error", ev)
        source = getattr(ev, "source", None)
        source_label = str(source or "")
        if "tts" in source_label.lower():
            logger.error("TTS pipeline error (%s): %s", source, err)
        else:
            logger.error("Session error (%s): %s", source, err)


def setup_chat_logging(session: AgentSession, room) -> None:
    """Log final user transcripts and agent responses to the console and the
    frontend chat (via the ``chat`` data topic)."""

    def publish(role: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        logger.info("CHAT %s: %s", role, text)
        payload = json.dumps({"role": role, "text": text}).encode("utf-8")
        asyncio.create_task(
            room.local_participant.publish_data(payload, topic="chat")
        )

    @session.on("user_input_transcribed")
    def _on_user_transcript(ev) -> None:
        if getattr(ev, "is_final", False):
            publish("user", getattr(ev, "transcript", ""))

    @session.on("conversation_item_added")
    def _on_item(ev) -> None:
        item = getattr(ev, "item", None)
        if item is None or getattr(item, "role", None) != "assistant":
            return
        publish("assistant", getattr(item, "text_content", None) or "")


GREETING_INSTRUCTIONS = (
    "Greet the student warmly in one or two short spoken sentences. "
    "Introduce yourself as their UF Computer Science academic advisor and "
    "invite them to ask about courses, prerequisites, critical tracking, or "
    "building a graduation plan. Do not call any tools for this greeting."
)


async def _play_greeting(ctx: JobContext, session: AgentSession) -> None:
    """Generate the greeting with the LLM after the student joins.

    Runs in the background so a slow/failed greeting never blocks listening.
    """
    try:
        try:
            participant = await asyncio.wait_for(
                ctx.wait_for_participant(),
                timeout=90.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Greeting skipped — no student joined within 90s")
            return
        except RuntimeError as e:
            if "disconnected" in str(e).lower():
                logger.warning("Greeting skipped — room disconnected before student joined")
                return
            raise

        logger.info("Student connected: %s — generating greeting", participant.identity)
        handle = session.generate_reply(instructions=GREETING_INSTRUCTIONS)
        await asyncio.wait_for(handle.wait_for_playout(), timeout=45.0)
        logger.info("Greeting playout complete")
    except asyncio.TimeoutError:
        logger.warning("Greeting timed out — continuing to listen")
    except Exception:
        logger.exception("Greeting failed — continuing to listen")


@server.rtc_session(agent_name="academic-advisor")
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("Job started for room %s", ctx.room.name)

    if os.environ.get("MOSS_PROJECT_ID") and os.environ.get("MOSS_PROJECT_KEY"):
        await init_moss(ctx.proc)
    else:
        logger.warning("Moss credentials not set — search tools will be unavailable")

    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="en"),
        llm=build_llm(),
        tts=MiniMaxTTS(),
        vad=ctx.proc.userdata["vad"],
        turn_handling=build_turn_handling(),
    )

    setup_session_logging(session)
    setup_chat_logging(session, ctx.room)

    agent = AcademicAdvisorAgent(room=ctx.room)

    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                sample_rate=24000,
                pre_connect_audio=True,
            ),
            audio_output=room_io.AudioOutputOptions(sample_rate=24000),
        ),
    )

    await ctx.connect()
    asyncio.create_task(_play_greeting(ctx, session))


if __name__ == "__main__":
    cli.run_app(server)
