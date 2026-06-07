import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  useDataChannel,
  useSessionContext,
  useSessionMessages,
} from "@livekit/components-react";
import { ConnectionState } from "livekit-client";
import MessageList from "./MessageList";

const EXAMPLE_QUESTIONS = [
  "What can I take next semester?",
  "Am I on track to graduate?",
  "What do I need before OS?",
  "Build me a graduation plan",
];

function createOrderRegistry() {
  return { counter: 0, byId: new Map() };
}

function assignOrder(registry, id) {
  if (!registry.byId.has(id)) {
    registry.counter += 1;
    registry.byId.set(id, registry.counter);
  }
  return registry.byId.get(id);
}

function textsOverlap(a, b) {
  if (!a || !b) return false;
  const na = a.trim().toLowerCase();
  const nb = b.trim().toLowerCase();
  return na === nb || na.startsWith(nb) || nb.startsWith(na);
}

function mergeDisplayMessages(transcriptMessages, chatLog, planMessages, registry) {
  const items = new Map();

  for (const m of transcriptMessages) {
    const role = m.type === "userTranscript" ? "user" : "assistant";
    const id = m.id;
    const order = assignOrder(registry, id);
    const existing = items.get(id);
    if (existing) {
      existing.text = m.message;
    } else {
      items.set(id, {
        id,
        kind: "text",
        role,
        text: m.message,
        order,
      });
    }
  }

  for (const m of chatLog) {
    let matchedId = null;
    for (const [id, item] of items) {
      if (item.role === m.role && textsOverlap(item.text, m.text)) {
        matchedId = id;
        break;
      }
    }

    if (matchedId) {
      const existing = items.get(matchedId);
      if ((m.text?.length ?? 0) >= (existing.text?.length ?? 0)) {
        existing.text = m.text;
      }
      continue;
    }

    const order = assignOrder(registry, m.id);
    items.set(m.id, {
      id: m.id,
      kind: "text",
      role: m.role,
      text: m.text,
      order,
    });
  }

  for (const m of planMessages) {
    const order = assignOrder(registry, m.id);
    items.set(m.id, {
      id: m.id,
      kind: "graduation_plan",
      role: "assistant",
      plan: m.plan,
      order,
    });
  }

  return [...items.values()].sort((a, b) => a.order - b.order);
}

function serializeMessages(messages) {
  return messages.map((m) => ({ ...m }));
}

export default function ConversationView({
  isConnected,
  isViewingHistory,
  historicalMessages,
  historicalDate,
  conversationKey,
  onMessagesUpdate,
}) {
  const session = useSessionContext();
  const { messages, send } = useSessionMessages();
  const [planMessages, setPlanMessages] = useState([]);
  const [chatLog, setChatLog] = useState([]);
  const scrollRef = useRef(null);
  const messageSeq = useRef(0);
  const orderRegistry = useRef(createOrderRegistry());

  const nextMessageId = useCallback((prefix) => {
    messageSeq.current += 1;
    return `${prefix}-${messageSeq.current}`;
  }, []);

  useEffect(() => {
    setPlanMessages([]);
    setChatLog([]);
    messageSeq.current = 0;
    orderRegistry.current = createOrderRegistry();
  }, [conversationKey]);

  const handleGraduationPlan = useCallback(
    (msg) => {
      if (isViewingHistory) return;
      try {
        const decoder = new TextDecoder();
        const payload = JSON.parse(decoder.decode(msg.payload));
        setPlanMessages((prev) => [
          ...prev,
          {
            id: nextMessageId("plan"),
            type: "graduation_plan",
            plan: payload,
          },
        ]);
      } catch (e) {
        console.error("Failed to parse graduation plan:", e);
      }
    },
    [nextMessageId, isViewingHistory]
  );

  useDataChannel("graduation_plan", handleGraduationPlan);

  const handleChatLog = useCallback(
    (msg) => {
      if (isViewingHistory) return;
      try {
        const decoder = new TextDecoder();
        const payload = JSON.parse(decoder.decode(msg.payload));
        if (!payload?.text) return;
        setChatLog((prev) => [
          ...prev,
          {
            id: nextMessageId("chat"),
            role: payload.role || "assistant",
            text: payload.text,
          },
        ]);
      } catch (e) {
        console.error("Failed to parse chat log:", e);
      }
    },
    [nextMessageId, isViewingHistory]
  );

  useDataChannel("chat", handleChatLog);

  const transcriptMessages = useMemo(
    () =>
      isViewingHistory
        ? []
        : messages.filter(
            (m) => m.type === "userTranscript" || m.type === "agentTranscript"
          ),
    [messages, isViewingHistory]
  );

  const liveMessages = useMemo(
    () =>
      mergeDisplayMessages(
        transcriptMessages,
        chatLog,
        planMessages,
        orderRegistry.current
      ),
    [transcriptMessages, chatLog, planMessages]
  );

  const displayMessages = isViewingHistory ? historicalMessages : liveMessages;

  useEffect(() => {
    if (!isViewingHistory && onMessagesUpdate) {
      onMessagesUpdate(serializeMessages(liveMessages));
    }
  }, [liveMessages, isViewingHistory, onMessagesUpdate]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [displayMessages, isViewingHistory]);

  const handleChipClick = async (question) => {
    if (session.connectionState === ConnectionState.Disconnected) {
      await session.start({ audio: true });
    }
    await send(question);
  };

  const showIdle =
    !isViewingHistory && !isConnected && displayMessages.length === 0;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {isViewingHistory && (
        <div className="border-b border-zinc-800 bg-zinc-900/60 px-6 py-2 text-center text-xs text-zinc-500">
          Viewing archived conversation · read only
        </div>
      )}
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
                  className="cursor-pointer rounded-full border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-zinc-500 hover:bg-zinc-800 hover:text-zinc-100"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex min-h-full flex-col justify-end">
            <MessageList
              messages={displayMessages}
              historicalDate={isViewingHistory ? historicalDate : null}
            />
          </div>
        )}
      </div>
    </div>
  );
}
