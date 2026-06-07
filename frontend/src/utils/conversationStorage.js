const STORAGE_PREFIX = "advisor_conversations_";

export function loadConversations(email) {
  if (!email) return [];
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${email}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveConversations(email, conversations) {
  if (!email) return;
  localStorage.setItem(`${STORAGE_PREFIX}${email}`, JSON.stringify(conversations));
}

export function createConversationId() {
  return `conv-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function formatConversationDate(isoDate) {
  if (!isoDate) return "Unknown date";
  const d = new Date(isoDate);
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function conversationTitle(messages) {
  const firstUser = messages?.find((m) => m.role === "user" && m.text?.trim());
  if (!firstUser) return "New conversation";
  const text = firstUser.text.trim();
  return text.length > 48 ? `${text.slice(0, 48)}…` : text;
}
