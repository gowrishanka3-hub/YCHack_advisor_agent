import GraduationPlanTable from "./GraduationPlanTable";

export default function MessageList({ messages, historicalDate }) {
  if (!messages?.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-center text-sm text-zinc-500">
        No messages in this conversation.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {historicalDate && (
        <div className="flex justify-center">
          <span className="rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs text-zinc-500">
            Conversation from {historicalDate}
          </span>
        </div>
      )}
      {messages.map((msg) => {
        if (msg.kind === "graduation_plan") {
          return (
            <div key={msg.id} className="flex justify-start">
              <div className="max-w-[90%] rounded-2xl bg-zinc-800 px-4 py-3 text-sm text-zinc-200">
                <div className="mb-1 text-xs font-medium uppercase tracking-wider opacity-60">
                  Advisor
                </div>
                <p className="mb-2 text-zinc-300">
                  Here&apos;s your semester-by-semester graduation plan:
                </p>
                <GraduationPlanTable plan={msg.plan} />
              </div>
            </div>
          );
        }

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
    </div>
  );
}
