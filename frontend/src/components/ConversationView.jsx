import { useCallback, useEffect, useRef, useState } from "react";
import {
  useDataChannel,
  useSessionContext,
  useSessionMessages,
} from "@livekit/components-react";
import { ConnectionState } from "livekit-client";
import GraduationPlanTable from "./GraduationPlanTable";

const EXAMPLE_QUESTIONS = [
  "What can I take next semester?",
  "Am I on track to graduate?",
  "What do I need before OS?",
  "Build me a graduation plan",
];

export default function ConversationView({ isConnected }) {
  const session = useSessionContext();
  const { messages, send } = useSessionMessages();
  const [planMessages, setPlanMessages] = useState([]);
  const [chatLog, setChatLog] = useState([]);
  const scrollRef = useRef(null);

  const handleGraduationPlan = useCallback((msg) => {
    try {
      const decoder = new TextDecoder();
      const payload = JSON.parse(decoder.decode(msg.payload));
      setPlanMessages((prev) => [
        ...prev,
        { id: `plan-${Date.now()}`, type: "graduation_plan", plan: payload },
      ]);
    } catch (e) {
      console.error("Failed to parse graduation plan:", e);
    }
  }, []);

  useDataChannel("graduation_plan", handleGraduationPlan);

  const handleChatLog = useCallback((msg) => {
    try {
      const decoder = new TextDecoder();
      const payload = JSON.parse(decoder.decode(msg.payload));
      if (!payload?.text) return;
      setChatLog((prev) => [
        ...prev,
        {
          id: `chat-${Date.now()}-${prev.length}`,
          role: payload.role || "assistant",
          text: payload.text,
        },
      ]);
    } catch (e) {
      console.error("Failed to parse chat log:", e);
    }
  }, []);

  useDataChannel("chat", handleChatLog);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, planMessages, chatLog]);

  const handleChipClick = async (question) => {
    if (session.connectionState === ConnectionState.Disconnected) {
      await session.start({ audio: true });
    }
    await send(question);
  };

  const transcriptMessages = messages.filter(
    (m) => m.type === "userTranscript" || m.type === "agentTranscript"
  );

  const transcriptDisplay = transcriptMessages.map((m) => ({
    id: m.id,
    role: m.type === "userTranscript" ? "user" : "assistant",
    text: m.message,
  }));
  const seen = new Set(transcriptDisplay.map((m) => `${m.role}:${m.text}`));
  const extraChat = chatLog.filter((m) => !seen.has(`${m.role}:${m.text}`));
  const displayMessages = [...transcriptDisplay, ...extraChat];

  const showIdle = !isConnected && displayMessages.length === 0;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
        {showIdle ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
              Talk to your AI academic advisor
            </h1>
            <p className="mt-2 max-w-md text-sm text-zinc-500">
              Press the mic to start a voice conversation. Your advisor searches your
              degree audit, course catalog, and major requirements in real time.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-2">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => handleChipClick(q)}
                  className="rounded-full border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-zinc-500 hover:bg-zinc-800 hover:text-zinc-100"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {displayMessages.map((msg) => {
              const isUser = msg.role === "user";
              return (
                <div
                  key={msg.id}
                  className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                      isUser
                        ? "bg-emerald-600/20 text-emerald-100"
                        : "bg-zinc-800 text-zinc-200"
                    }`}
                  >
                    <div className="mb-0.5 text-xs font-medium uppercase tracking-wider opacity-60">
                      {isUser ? "You" : "Advisor"}
                    </div>
                    {msg.text}
                  </div>
                </div>
              );
            })}

            {planMessages.map((item) => (
              <div key={item.id} className="flex justify-start">
                <div className="max-w-[90%] rounded-2xl bg-zinc-800 px-4 py-3 text-sm text-zinc-200">
                  <div className="mb-1 text-xs font-medium uppercase tracking-wider opacity-60">
                    Advisor
                  </div>
                  <p className="mb-2 text-zinc-300">
                    Here&apos;s your semester-by-semester graduation plan:
                  </p>
                  <GraduationPlanTable plan={item.plan} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
