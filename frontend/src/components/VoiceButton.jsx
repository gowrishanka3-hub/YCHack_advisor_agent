import { useAgent, useSessionContext } from "@livekit/components-react";
import { ConnectionState } from "livekit-client";

const STATUS_MAP = {
  listening: { label: "Listening", color: "bg-emerald-500" },
  thinking: { label: "Thinking", color: "bg-amber-500" },
  speaking: { label: "Speaking", color: "bg-blue-500" },
  initializing: { label: "Connecting", color: "bg-zinc-500" },
  idle: { label: "Ready", color: "bg-zinc-500" },
  connecting: { label: "Connecting", color: "bg-zinc-500" },
  disconnected: { label: "Idle", color: "bg-zinc-600" },
};

function getStatus(agentState, connectionState) {
  if (connectionState === ConnectionState.Connecting) {
    return STATUS_MAP.connecting;
  }
  if (connectionState === ConnectionState.Disconnected) {
    return STATUS_MAP.disconnected;
  }
  return STATUS_MAP[agentState] ?? STATUS_MAP.idle;
}

export default function VoiceButton() {
  const session = useSessionContext();
  const agent = useAgent();
  const isConnected = session.isConnected;
  const isConnecting = session.connectionState === ConnectionState.Connecting;

  const status = getStatus(agent.state, session.connectionState);

  const handleToggle = async () => {
    if (isConnected || isConnecting) {
      await session.end();
    } else {
      await session.start({ audio: true });
    }
  };

  return (
    <div className="flex items-center justify-between border-t border-zinc-800 px-6 py-4">
      <div className="flex items-center gap-3">
        <span
          className={`h-2.5 w-2.5 rounded-full ${status.color} ${
            isConnected && agent.state === "listening" ? "animate-pulse-ring" : ""
          }`}
        />
        <span className="text-sm text-zinc-400">{status.label}</span>
      </div>

      <button
        type="button"
        onClick={handleToggle}
        disabled={isConnecting}
        className={`flex h-12 w-12 items-center justify-center rounded-full transition-all ${
          isConnected
            ? "bg-red-500/20 text-red-400 ring-2 ring-red-500/40 hover:bg-red-500/30"
            : "bg-emerald-500/20 text-emerald-400 ring-2 ring-emerald-500/40 hover:bg-emerald-500/30"
        } disabled:opacity-50`}
        aria-label={isConnected ? "End call" : "Start call"}
      >
        {isConnected ? (
          <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        )}
      </button>
    </div>
  );
}
