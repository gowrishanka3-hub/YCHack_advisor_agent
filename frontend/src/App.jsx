import { useCallback, useEffect, useMemo, useState } from "react";
import {
  SessionProvider,
  useSession,
  useSessionContext,
  useSessionMessages,
  RoomAudioRenderer,
  StartAudio,
} from "@livekit/components-react";
import { TokenSource, ConnectionState } from "livekit-client";
import LoginPage from "./components/LoginPage";
import StudentProfile from "./components/StudentProfile";
import ConversationView from "./components/ConversationView";
import ConversationHistory from "./components/ConversationHistory";
import VoiceButton from "./components/VoiceButton";
import DegreeAuditUpload from "./components/DegreeAuditUpload";
import {
  loadConversations,
  saveConversations,
  createConversationId,
  formatConversationDate,
  conversationTitle,
} from "./utils/conversationStorage";

const tokenSource = TokenSource.endpoint("/api/token");

function readStoredAuth() {
  try {
    const raw = sessionStorage.getItem("advisor_auth");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function AppContent({ auth, onLogout }) {
  const session = useSessionContext();
  const { send } = useSessionMessages();
  const isConnected = session.connectionState !== ConnectionState.Disconnected;

  const [conversations, setConversations] = useState(() =>
    loadConversations(auth?.email)
  );
  const [activeConversationId, setActiveConversationId] = useState(() =>
    createConversationId()
  );
  const [viewingConversationId, setViewingConversationId] = useState(null);
  const [conversationKey, setConversationKey] = useState(0);

  useEffect(() => {
    saveConversations(auth?.email, conversations);
  }, [conversations, auth?.email]);

  const viewingConversation = useMemo(
    () => conversations.find((c) => c.id === viewingConversationId) ?? null,
    [conversations, viewingConversationId]
  );

  const handleMessagesUpdate = useCallback(
    (messages) => {
      if (viewingConversationId) return;
      setConversations((prev) => {
        const idx = prev.findIndex((c) => c.id === activeConversationId);
        const now = new Date().toISOString();
        const record = {
          id: activeConversationId,
          date: idx >= 0 ? prev[idx].date : now,
          title: conversationTitle(messages),
          messages,
        };
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = record;
          return next;
        }
        return [record, ...prev];
      });
    },
    [activeConversationId, viewingConversationId]
  );

  const handleSelectConversation = (id) => {
    if (id === activeConversationId && viewingConversationId !== null) {
      setViewingConversationId(null);
      return;
    }
    if (id === activeConversationId) {
      setViewingConversationId(null);
      return;
    }
    setViewingConversationId(id);
  };

  const handleNewConversation = async () => {
    if (isConnected) {
      await session.end();
    }
    const newId = createConversationId();
    setActiveConversationId(newId);
    setViewingConversationId(null);
    setConversationKey((k) => k + 1);
  };

  const handleAskAdvisor = async (question) => {
    if (viewingConversationId) {
      setViewingConversationId(null);
    }
    if (session.connectionState === ConnectionState.Disconnected) {
      await session.start({ audio: true });
    }
    await send(question);
  };

  useEffect(() => {
    if (!isConnected && viewingConversationId === null) {
      setConversations((prev) => {
        const idx = prev.findIndex((c) => c.id === activeConversationId);
        if (idx < 0) return prev;
        const conv = prev[idx];
        if (!conv.messages?.length) return prev;
        const next = [...prev];
        next[idx] = { ...conv, date: new Date().toISOString() };
        return next;
      });
    }
  }, [isConnected, activeConversationId, viewingConversationId]);

  return (
    <div className="flex h-full flex-col">
      <RoomAudioRenderer room={session.room} />
      <StartAudio
        room={session.room}
        label="Click to enable audio (required to hear the advisor)"
        className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-full bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg ring-2 ring-emerald-300/50"
      />
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-sm font-medium text-zinc-300">Academic Advisor</span>
          </div>
          {auth?.university && (
            <span className="hidden text-xs text-zinc-600 sm:inline">
              · {auth.university}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <DegreeAuditUpload />
          <button
            type="button"
            onClick={onLogout}
            className="cursor-pointer text-xs text-zinc-500 transition-colors hover:text-zinc-300"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-72 shrink-0 border-r border-zinc-800 p-4 max-lg:hidden">
          <StudentProfile onAskAdvisor={handleAskAdvisor} />
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <ConversationView
            isConnected={isConnected}
            isViewingHistory={viewingConversationId !== null}
            historicalMessages={viewingConversation?.messages ?? []}
            historicalDate={
              viewingConversation
                ? formatConversationDate(viewingConversation.date)
                : null
            }
            conversationKey={conversationKey}
            onMessagesUpdate={handleMessagesUpdate}
          />
          {!viewingConversationId && <VoiceButton />}
        </main>

        <aside className="w-72 shrink-0 border-l border-zinc-800 p-4 max-md:hidden">
          <ConversationHistory
            conversations={conversations}
            activeId={activeConversationId}
            viewingId={viewingConversationId}
            onSelect={handleSelectConversation}
            onNewConversation={handleNewConversation}
          />
        </aside>
      </div>
    </div>
  );
}

export default function App() {
  const [auth, setAuth] = useState(readStoredAuth);
  const session = useSession(tokenSource, { agentName: "academic-advisor" });

  const handleLogout = () => {
    sessionStorage.removeItem("advisor_auth");
    setAuth(null);
  };

  if (!auth) {
    return <LoginPage onLogin={setAuth} />;
  }

  return (
    <SessionProvider session={session}>
      <AppContent auth={auth} onLogout={handleLogout} />
    </SessionProvider>
  );
}
