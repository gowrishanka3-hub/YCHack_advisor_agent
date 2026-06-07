import { SessionProvider, useSession, useSessionContext } from "@livekit/components-react";
import { TokenSource, ConnectionState } from "livekit-client";
import StudentProfile from "./components/StudentProfile";
import ConversationView from "./components/ConversationView";
import VoiceButton from "./components/VoiceButton";

const tokenSource = TokenSource.endpoint("/api/token");

function AppContent() {
  const session = useSessionContext();
  const isConnected = session.connectionState !== ConnectionState.Disconnected;

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-emerald-500" />
          <span className="text-sm font-medium text-zinc-300">Academic Advisor</span>
        </div>
        <span className="text-xs text-zinc-600">Voice-first · Moss-powered</span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-80 shrink-0 border-r border-zinc-800 p-4 max-md:hidden">
          <StudentProfile />
        </aside>

        <main className="flex flex-1 flex-col overflow-hidden">
          <ConversationView isConnected={isConnected} />
          <VoiceButton />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const session = useSession(tokenSource, { agentName: "academic-advisor" });

  return (
    <SessionProvider session={session}>
      <AppContent />
    </SessionProvider>
  );
}
