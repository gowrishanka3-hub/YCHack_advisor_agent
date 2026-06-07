import { formatConversationDate } from "../utils/conversationStorage";

export default function ConversationHistory({
  conversations,
  activeId,
  viewingId,
  onSelect,
  onNewConversation,
}) {
  const sorted = [...conversations].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-800 bg-zinc-900/50">
      <div className="border-b border-zinc-800 px-4 py-3">
        <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">
          Conversation history
        </div>
        <button
          type="button"
          onClick={onNewConversation}
          className="mt-2 w-full cursor-pointer rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-300 transition-colors hover:border-emerald-500/50 hover:bg-emerald-500/20"
        >
          + New conversation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {sorted.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-zinc-600">
            Past conversations will appear here after you chat with your advisor.
          </p>
        ) : (
          <ul className="space-y-1">
            {sorted.map((conv) => {
              const isLive = conv.id === activeId && viewingId === null;
              const isViewing = conv.id === viewingId;
              const isSelected = isLive || isViewing;

              return (
                <li key={conv.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(conv.id)}
                    className={`w-full cursor-pointer rounded-lg border px-3 py-2.5 text-left transition-colors ${
                      isSelected
                        ? "border-emerald-500/40 bg-emerald-500/10"
                        : "border-transparent bg-transparent hover:border-zinc-700 hover:bg-zinc-800/80"
                    }`}
                  >
                    <div className="truncate text-sm font-medium text-zinc-200">
                      {conv.title}
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {formatConversationDate(conv.date)}
                    </div>
                    {isLive && (
                      <div className="mt-1 text-xs text-emerald-400/80">Current session</div>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
