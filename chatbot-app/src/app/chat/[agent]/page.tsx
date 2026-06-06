"use client";

import { useParams, useRouter } from "next/navigation";
import { useRef, useState, useCallback, useEffect } from "react";
import { Sidebar } from "@/components/chat/sidebar";
import { ChatHeader } from "@/components/chat/header";
import { MessageBubble } from "@/components/chat/message";
import { InputArea } from "@/components/chat/input-area";
import { Conversation, Message } from "@/types/chat";

// ── Storage (per agent) ────────────────────────────────────────────────────────

const ONE_WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function generateId() {
  return Math.random().toString(36).slice(2, 11);
}

// Display names for greeting text — keyed by agent ID
const AGENT_DISPLAY: Record<string, string> = {
  "ttu-online": "TTU Online",
  "k12": "K-12",
};

function freshConversation(agentId: string): Conversation {
  return {
    id: generateId(),
    title: "New conversation",
    lastMessage: "",
    updatedAt: new Date(),
    messages: [], // greeting is animated in via useEffect
  };
}

function storageKey(agentId: string) {
  return `ttu_chat_${agentId}`;
}

function loadFromStorage(agentId: string): { conversations: Conversation[]; activeId: string } | null {
  try {
    const raw = localStorage.getItem(storageKey(agentId));
    if (!raw) return null;
    const { conversations, activeId, savedAt } = JSON.parse(raw);
    if (Date.now() - savedAt > ONE_WEEK_MS) {
      localStorage.removeItem(storageKey(agentId));
      return null;
    }
    return {
      conversations: conversations.map((c: Conversation) => ({
        ...c,
        updatedAt: new Date(c.updatedAt),
        messages: c.messages.map((m: Message) => ({
          ...m,
          timestamp: new Date(m.timestamp),
          isStreaming: false,
        })),
      })),
      activeId,
    };
  } catch {
    return null;
  }
}

function saveToStorage(agentId: string, conversations: Conversation[], activeId: string) {
  try {
    localStorage.setItem(
      storageKey(agentId),
      JSON.stringify({ conversations, activeId, savedAt: Date.now() })
    );
  } catch { /* full or disabled */ }
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function AgentChatPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.agent as string;

  const [displayName, setDisplayName] = useState(agentId);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const streamingRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const greetedRef = useRef<Set<string>>(new Set());

  // Fetch agent display name + validate agent exists
  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${apiUrl}/agents`)
      .then((r) => r.json())
      .then((agents: { id: string; display_name: string }[]) => {
        const found = agents.find((a) => a.id === agentId);
        if (!found) {
          router.replace("/");
          return;
        }
        setDisplayName(found.display_name);
      })
      .catch(() => { /* use agentId as fallback */ });
  }, [agentId, router]);

  // Hydrate from localStorage
  useEffect(() => {
    const saved = loadFromStorage(agentId);
    if (saved && saved.conversations.length > 0) {
      setConversations(saved.conversations);
      setActiveId(saved.activeId);
    } else {
      const conv = freshConversation(agentId);
      setConversations([conv]);
      setActiveId(conv.id);
    }
    setHydrated(true);
  }, [agentId]);

  // Persist on change
  useEffect(() => {
    if (hydrated && conversations.length > 0) {
      saveToStorage(agentId, conversations, activeId);
    }
  }, [agentId, conversations, activeId, hydrated]);

  // ── Animated greeting for every new empty conversation ──────────────────────
  const activeConvId = conversations.find((c) => c.id === activeId)?.id;
  const activeConvMsgCount = conversations.find((c) => c.id === activeId)?.messages.length ?? -1;

  useEffect(() => {
    if (!hydrated || !activeConvId) return;
    if (activeConvMsgCount !== 0) return;               // already has messages
    if (greetedRef.current.has(activeConvId)) return;   // already greeted this conv

    greetedRef.current.add(activeConvId);
    const convId = activeConvId;
    const name = AGENT_DISPLAY[agentId] ?? agentId;
    const msg1Id = generateId();
    const msg2Id = generateId();
    const fullText = `I'm your ChatBot and I contain information on ${name}. How can I help you today?`;

    let aborted = false;

    // Step 1 — first message appears after a short pause
    const t1 = setTimeout(() => {
      if (aborted) return;
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? {
                ...c,
                messages: [
                  { id: msg1Id, role: "assistant" as const, content: "Hi there! 👋", timestamp: new Date() },
                ],
              }
            : c
        )
      );

      // Step 2 — typing indicator appears
      const t2 = setTimeout(() => {
        if (aborted) return;
        setConversations((prev) =>
          prev.map((c) =>
            c.id !== convId
              ? c
              : {
                  ...c,
                  messages: [
                    ...c.messages,
                    { id: msg2Id, role: "assistant" as const, content: "", timestamp: new Date(), isStreaming: true },
                  ],
                }
          )
        );

        // Step 3 — type out the second message
        let i = 0;
        const interval = setInterval(() => {
          if (aborted) { clearInterval(interval); return; }
          i += 3;
          const done = i >= fullText.length;
          setConversations((prev) =>
            prev.map((c) =>
              c.id !== convId
                ? c
                : {
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === msg2Id
                        ? { ...m, content: fullText.slice(0, Math.min(i, fullText.length)), isStreaming: !done }
                        : m
                    ),
                  }
            )
          );
          if (done) clearInterval(interval);
        }, 28);
      }, 700);

      return () => clearTimeout(t2);
    }, 450);

    return () => {
      aborted = true;
      clearTimeout(t1);
    };
  }, [hydrated, activeConvId, agentId]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeConversation = conversations.find((c) => c.id === activeId);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [activeConversation?.messages.length, scrollToBottom]);

  const handleSend = useCallback(
    async (text: string) => {
      if (isStreaming) return;

      const userMsg: Message = {
        id: generateId(),
        role: "user",
        content: text,
        timestamp: new Date(),
      };
      const assistantMsgId = generateId();
      const assistantMsg: Message = {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isStreaming: true,
      };
      const currentId = activeId;

      setConversations((prev) =>
        prev.map((c) =>
          c.id === currentId
            ? {
                ...c,
                messages: [...c.messages, userMsg, assistantMsg],
                lastMessage: text,
                updatedAt: new Date(),
                title:
                  c.messages.filter((m) => m.role === "user").length === 0
                    ? text.slice(0, 40) + (text.length > 40 ? "..." : "")
                    : c.title,
              }
            : c
        )
      );

      setIsStreaming(true);
      streamingRef.current = true;

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const res = await fetch(`${apiUrl}/chat/${agentId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text }),
        });

        if (!res.ok || !res.body) throw new Error("API error");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let accumulated = "";
        const IMAGES_MARKER = "\n__IMAGES__:";

        while (streamingRef.current) {
          const { done, value } = await reader.read();
          if (done) break;
          accumulated += decoder.decode(value, { stream: true });

          // Hide the images marker from the displayed text while streaming
          const displayText = accumulated.includes(IMAGES_MARKER)
            ? accumulated.split(IMAGES_MARKER)[0].trim()
            : accumulated;

          setConversations((prev) =>
            prev.map((c) =>
              c.id === currentId
                ? {
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === assistantMsgId
                        ? { ...m, content: displayText, isStreaming: true }
                        : m
                    ),
                  }
                : c
            )
          );
        }

        // Parse final accumulated text for images marker
        let finalContent = accumulated;
        let imageIds: string[] = [];
        if (accumulated.includes(IMAGES_MARKER)) {
          const [textPart, imgPart] = accumulated.split(IMAGES_MARKER);
          finalContent = textPart.trim();
          imageIds = imgPart.trim().split(",").filter(Boolean);
        }

        setConversations((prev) =>
          prev.map((c) =>
            c.id === currentId
              ? {
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === assistantMsgId
                      ? { ...m, content: finalContent, imageIds, isStreaming: false }
                      : m
                  ),
                }
              : c
          )
        );
      } catch {
        setConversations((prev) =>
          prev.map((c) =>
            c.id === currentId
              ? {
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === assistantMsgId
                      ? {
                          ...m,
                          content: "Failed to reach the knowledge base. Please check your connection.",
                          isStreaming: false,
                        }
                      : m
                  ),
                }
              : c
          )
        );
      } finally {
        setIsStreaming(false);
        streamingRef.current = false;
      }
    },
    [agentId, activeId, isStreaming]
  );

  const handleStop = useCallback(() => {
    streamingRef.current = false;
    setIsStreaming(false);
    setConversations((prev) =>
      prev.map((c) =>
        c.id === activeId
          ? { ...c, messages: c.messages.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)) }
          : c
      )
    );
  }, [activeId]);

  const handleNew = useCallback(() => {
    const conv = freshConversation(agentId);
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
  }, []);

  const handleDelete = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        if (activeId === id) {
          if (next.length > 0) {
            setActiveId(next[0].id);
          } else {
            const conv = freshConversation(agentId);
            setActiveId(conv.id);
            return [conv];
          }
        }
        return next;
      });
    },
    [activeId]
  );

  const handleRegenerate = useCallback(() => {
    if (isStreaming || !activeConversation) return;
    const messages = activeConversation.messages;
    const lastAssistant = messages[messages.length - 1];
    if (lastAssistant?.role !== "assistant") return;
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    setConversations((prev) =>
      prev.map((c) =>
        c.id === activeId
          ? { ...c, messages: c.messages.filter((m) => m.id !== lastAssistant.id) }
          : c
      )
    );
    setTimeout(() => handleSend(lastUser.content), 50);
  }, [activeId, activeConversation, isStreaming, handleSend]);

  if (!hydrated) return null;

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={handleNew}
        onDelete={handleDelete}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((v) => !v)}
      />

      <div className="flex flex-col flex-1 min-w-0">
        <ChatHeader
          conversationTitle={activeConversation?.title ?? "New conversation"}
          agentTitle={displayName}
        />

        <div className="flex-1 overflow-y-auto scroll-smooth">
          <div className="max-w-3xl mx-auto py-4 pb-2">
            {activeConversation?.messages.map((msg, i) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onRegenerate={
                  i === (activeConversation?.messages.length ?? 0) - 1 &&
                  msg.role === "assistant" &&
                  !msg.isStreaming
                    ? handleRegenerate
                    : undefined
                }
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="max-w-3xl mx-auto w-full">
          <InputArea
            onSend={handleSend}
            disabled={isStreaming}
            isStreaming={isStreaming}
            onStop={handleStop}
          />
        </div>
      </div>
    </div>
  );
}
