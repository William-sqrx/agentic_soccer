import { useState, useRef, useEffect, useCallback } from "react";

const API_URL = "http://127.0.0.1:8000/chat";

const genId = () => Math.random().toString(36).slice(2, 9);
const genUserId = () => "user-" + genId();

const formatTime = (iso) => {
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000)
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
};

const FieldIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
    <rect
      x="1"
      y="2"
      width="14"
      height="12"
      rx="1.5"
      stroke="currentColor"
      strokeWidth="1.2"
      fill="none"
    />
    <circle
      cx="8"
      cy="8"
      r="2.5"
      stroke="currentColor"
      strokeWidth="1.2"
      fill="none"
    />
    <line
      x1="8"
      y1="2"
      x2="8"
      y2="14"
      stroke="currentColor"
      strokeWidth="1.2"
    />
    <rect
      x="1"
      y="5.5"
      width="2.5"
      height="5"
      stroke="currentColor"
      strokeWidth="1"
      fill="none"
    />
    <rect
      x="12.5"
      y="5.5"
      width="2.5"
      height="5"
      stroke="currentColor"
      strokeWidth="1"
      fill="none"
    />
  </svg>
);

const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <line
      x1="7"
      y1="2"
      x2="7"
      y2="12"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
    <line
      x1="2"
      y1="7"
      x2="12"
      y2="7"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </svg>
);

const SendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <path
      d="M13.5 2.5L7 9M13.5 2.5L9 13.5L7 9M13.5 2.5L2.5 6.5L7 9"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const TrashIcon = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
    <path
      d="M1.5 3h9M4.5 3V2h3v1M2.5 3l.75 7.5h5.5L9.5 3"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const BotDot = () => (
  <div
    style={{
      width: 28,
      height: 28,
      borderRadius: "50%",
      flexShrink: 0,
      background: "linear-gradient(135deg, #16a34a 0%, #15803d 100%)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow: "0 0 0 2px rgba(22,163,74,0.2)",
    }}
  >
    <FieldIcon size={13} color="#fff" />
  </div>
);

const TypingDots = () => (
  <div
    style={{ display: "flex", gap: 4, alignItems: "center", padding: "4px 0" }}
  >
    {[0, 1, 2].map((i) => (
      <div
        key={i}
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: "#16a34a",
          animation: `td 1.2s ease-in-out ${i * 0.2}s infinite`,
        }}
      />
    ))}
  </div>
);

export default function App() {
  const [chats, setChats] = useState(() => {
    const welcome = {
      id: genId(),
      userId: genUserId(),
      title: "New analysis",
      createdAt: new Date().toISOString(),
      messages: [],
    };
    return [welcome];
  });
  const [activeChatId, setActiveChatId] = useState(() => null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const textareaRef = useRef(null);

  const activeChat = chats.find((c) => c.id === activeChatId) || chats[0];

  useEffect(() => {
    if (!activeChatId && chats.length > 0) setActiveChatId(chats[0].id);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat?.messages, loading]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + "px";
    }
  }, [input]);

  const newChat = () => {
    const chat = {
      id: genId(),
      userId: genUserId(),
      title: "New analysis",
      createdAt: new Date().toISOString(),
      messages: [],
    };
    setChats((prev) => [chat, ...prev]);
    setActiveChatId(chat.id);
    setInput("");
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const deleteChat = (e, id) => {
    e.stopPropagation();
    setChats((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (next.length === 0) {
        const fresh = {
          id: genId(),
          userId: genUserId(),
          title: "New analysis",
          createdAt: new Date().toISOString(),
          messages: [],
        };
        setActiveChatId(fresh.id);
        return [fresh];
      }
      if (id === activeChatId) setActiveChatId(next[0].id);
      return next;
    });
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = {
      id: genId(),
      role: "user",
      content: text,
      ts: new Date().toISOString(),
    };

    setChats((prev) =>
      prev.map((c) => {
        if (c.id !== activeChat.id) return c;
        const isFirst = c.messages.length === 0;
        return {
          ...c,
          title: isFirst
            ? text.slice(0, 42) + (text.length > 42 ? "…" : "")
            : c.title,
          messages: [...c.messages, userMsg],
        };
      }),
    );
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: activeChat.userId,
          state: { evaluation: text },
        }),
      });
      const data = await res.json();
      const aiMsg = {
        id: genId(),
        role: "ai",
        content: data.response || data.error || "No response.",
        ts: new Date().toISOString(),
      };
      setChats((prev) =>
        prev.map((c) =>
          c.id === activeChat.id
            ? { ...c, messages: [...c.messages, aiMsg] }
            : c,
        ),
      );
    } catch {
      setChats((prev) =>
        prev.map((c) =>
          c.id === activeChat.id
            ? {
                ...c,
                messages: [
                  ...c.messages,
                  {
                    id: genId(),
                    role: "ai",
                    content: "⚠ Could not reach server.",
                    ts: new Date().toISOString(),
                  },
                ],
              }
            : c,
        ),
      );
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const suggestedPrompts = [
    "Who will win the Champions League final?",
    "Predict Man City vs Arsenal this weekend",
    "Best bets for the El Clásico?",
    "Top scorer predictions for next month",
  ];

  return (
    <div style={s.root}>
      <style>{css}</style>

      {/* SIDEBAR */}
      <div
        style={{
          ...s.sidebar,
          transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
          transition: "transform 0.25s ease",
        }}
      >
        <div style={s.sidebarTop}>
          <div style={s.brand}>
            <div style={s.brandIcon}>
              <FieldIcon size={15} />
            </div>
            <span style={s.brandName}>
              Kickoff <span style={{ color: "#16a34a" }}>AI</span>
            </span>
          </div>
          <button
            onClick={newChat}
            style={s.newChatBtn}
            className="new-chat-btn"
            title="New chat"
          >
            <PlusIcon />
            <span>New analysis</span>
          </button>
        </div>

        <div style={s.historyLabel}>RECENT</div>
        <div style={s.historyList}>
          {chats.map((chat) => (
            <div
              key={chat.id}
              onClick={() => setActiveChatId(chat.id)}
              style={{
                ...s.historyItem,
                ...(chat.id === activeChat?.id ? s.historyItemActive : {}),
              }}
              className="history-item"
            >
              <div style={s.historyDot} />
              <div style={s.historyContent}>
                <div style={s.historyTitle}>{chat.title}</div>
                <div style={s.historyTime}>{formatTime(chat.createdAt)}</div>
              </div>
              <button
                onClick={(e) => deleteChat(e, chat.id)}
                style={s.deleteBtn}
                className="delete-btn"
                title="Delete"
              >
                <TrashIcon />
              </button>
            </div>
          ))}
        </div>

        <div style={s.sidebarFooter}>
          <div style={s.footerBadge}>
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "#16a34a",
              }}
            />
            <span>Live predictions</span>
          </div>
        </div>
      </div>

      {/* MAIN */}
      <div style={s.main}>
        {/* Header */}
        <div style={s.header}>
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            style={s.menuBtn}
            className="menu-btn"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <line
                x1="2"
                y1="4.5"
                x2="14"
                y2="4.5"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
              />
              <line
                x1="2"
                y1="8"
                x2="14"
                y2="8"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
              />
              <line
                x1="2"
                y1="11.5"
                x2="14"
                y2="11.5"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <div style={s.headerCenter}>
            <span style={s.headerTitle}>
              {activeChat?.title || "New analysis"}
            </span>
          </div>
          <div style={s.headerRight}>
            <div style={s.statusPill}>
              <div
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: loading ? "#f59e0b" : "#16a34a",
                  transition: "background 0.3s",
                }}
              />
              <span>{loading ? "Analysing…" : "Ready"}</span>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div style={s.messages}>
          {activeChat?.messages.length === 0 && !loading && (
            <div style={s.empty}>
              <div style={s.emptyFieldWrap}>
                <svg
                  width="72"
                  height="72"
                  viewBox="0 0 72 72"
                  fill="none"
                  style={{ opacity: 0.15 }}
                >
                  <rect
                    x="4"
                    y="10"
                    width="64"
                    height="52"
                    rx="6"
                    stroke="#16a34a"
                    strokeWidth="2.5"
                  />
                  <circle
                    cx="36"
                    cy="36"
                    r="12"
                    stroke="#16a34a"
                    strokeWidth="2"
                  />
                  <line
                    x1="36"
                    y1="10"
                    x2="36"
                    y2="62"
                    stroke="#16a34a"
                    strokeWidth="2"
                  />
                  <rect
                    x="4"
                    y="24"
                    width="12"
                    height="24"
                    stroke="#16a34a"
                    strokeWidth="1.5"
                  />
                  <rect
                    x="56"
                    y="24"
                    width="12"
                    height="24"
                    stroke="#16a34a"
                    strokeWidth="1.5"
                  />
                </svg>
              </div>
              <div style={s.emptyHeading}>Football Intelligence</div>
              <div style={s.emptySubtext}>
                Ask about match predictions, team form, or betting insights
              </div>
              <div style={s.promptGrid}>
                {suggestedPrompts.map((p, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setInput(p);
                      setTimeout(() => inputRef.current?.focus(), 50);
                    }}
                    style={s.promptChip}
                    className="prompt-chip"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeChat?.messages.map((m) => (
            <div
              key={m.id}
              style={{
                ...s.msgRow,
                justifyContent: m.role === "user" ? "flex-end" : "flex-start",
              }}
              className="msg-row"
            >
              {m.role === "ai" && <BotDot />}
              <div
                style={{
                  ...s.bubble,
                  ...(m.role === "user" ? s.userBubble : s.aiBubble),
                }}
              >
                <div style={s.bubbleContent}>{m.content}</div>
                <div style={s.bubbleTime}>{formatTime(m.ts)}</div>
              </div>
            </div>
          ))}

          {loading && (
            <div
              style={{ ...s.msgRow, justifyContent: "flex-start" }}
              className="msg-row"
            >
              <BotDot />
              <div style={{ ...s.bubble, ...s.aiBubble }}>
                <TypingDots />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={s.inputWrap}>
          <div style={s.inputBox}>
            <textarea
              ref={(el) => {
                inputRef.current = el;
                textareaRef.current = el;
              }}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about a match, team, or prediction…"
              rows={1}
              style={s.textarea}
              className="chat-textarea"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              style={{
                ...s.sendBtn,
                ...(loading || !input.trim() ? s.sendBtnDisabled : {}),
              }}
              className="send-btn"
            >
              <SendIcon />
            </button>
          </div>
          <div style={s.inputHint}>
            Press Enter to send · Shift+Enter for new line
          </div>
        </div>
      </div>
    </div>
  );
}

const s = {
  root: {
    display: "flex",
    height: "100vh",
    background: "#0a0f0a",
    fontFamily: "'Geist', 'Inter', system-ui, sans-serif",
    color: "#e8ede8",
    overflow: "hidden",
    position: "relative",
  },
  sidebar: {
    width: 240,
    background: "#0d140d",
    borderRight: "1px solid #1a2a1a",
    display: "flex",
    flexDirection: "column",
    flexShrink: 0,
    overflow: "hidden",
  },
  sidebarTop: {
    padding: "20px 14px 12px",
    borderBottom: "1px solid #1a2a1a",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "0 2px",
  },
  brandIcon: {
    width: 28,
    height: 28,
    borderRadius: 8,
    background: "#16a34a",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#fff",
    flexShrink: 0,
  },
  brandName: {
    fontSize: 15,
    fontWeight: 600,
    letterSpacing: "-0.3px",
    color: "#e8ede8",
  },
  newChatBtn: {
    display: "flex",
    alignItems: "center",
    gap: 7,
    background: "#16a34a22",
    border: "1px solid #16a34a55",
    color: "#4ade80",
    borderRadius: 8,
    padding: "8px 12px",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
    transition: "all 0.15s",
    width: "100%",
  },
  historyLabel: {
    fontSize: 10,
    letterSpacing: 1.5,
    color: "#3a5a3a",
    padding: "14px 16px 6px",
    fontWeight: 600,
  },
  historyList: {
    flex: 1,
    overflowY: "auto",
    padding: "4px 8px",
  },
  historyItem: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 8px",
    borderRadius: 8,
    cursor: "pointer",
    transition: "background 0.15s",
    position: "relative",
  },
  historyItemActive: {
    background: "#16a34a18",
    border: "1px solid #16a34a30",
  },
  historyDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#2a4a2a",
    flexShrink: 0,
  },
  historyContent: { flex: 1, minWidth: 0 },
  historyTitle: {
    fontSize: 12.5,
    color: "#b8d4b8",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    lineHeight: 1.4,
  },
  historyTime: { fontSize: 11, color: "#3a5a3a", marginTop: 2 },
  deleteBtn: {
    opacity: 0,
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "#5a4a4a",
    padding: 4,
    borderRadius: 4,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "opacity 0.15s",
    flexShrink: 0,
  },
  sidebarFooter: {
    padding: "12px 16px",
    borderTop: "1px solid #1a2a1a",
  },
  footerBadge: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 11,
    color: "#3a6a3a",
  },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "14px 20px",
    borderBottom: "1px solid #1a2a1a",
    background: "#0d140d",
    minHeight: 56,
  },
  menuBtn: {
    background: "none",
    border: "none",
    color: "#4a7a4a",
    cursor: "pointer",
    padding: 6,
    borderRadius: 6,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "color 0.15s",
    flexShrink: 0,
  },
  headerCenter: { flex: 1, minWidth: 0 },
  headerTitle: {
    fontSize: 13.5,
    fontWeight: 500,
    color: "#c8e0c8",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    display: "block",
  },
  headerRight: { display: "flex", alignItems: "center", gap: 8, flexShrink: 0 },
  statusPill: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    background: "#111a11",
    border: "1px solid #1e341e",
    borderRadius: 20,
    padding: "4px 10px",
    fontSize: 11,
    color: "#4a7a4a",
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "28px 24px",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  empty: {
    margin: "auto",
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 12,
    maxWidth: 400,
  },
  emptyFieldWrap: { marginBottom: 4 },
  emptyHeading: {
    fontSize: 20,
    fontWeight: 600,
    color: "#c8e0c8",
    letterSpacing: "-0.3px",
  },
  emptySubtext: { fontSize: 13.5, color: "#3a6a3a", lineHeight: 1.6 },
  promptGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
    marginTop: 8,
    width: "100%",
  },
  promptChip: {
    background: "#111a11",
    border: "1px solid #1e341e",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12.5,
    color: "#7ab87a",
    cursor: "pointer",
    textAlign: "left",
    transition: "all 0.15s",
    lineHeight: 1.4,
  },
  msgRow: {
    display: "flex",
    alignItems: "flex-end",
    gap: 10,
  },
  bubble: {
    maxWidth: "70%",
    borderRadius: 14,
    padding: "11px 15px",
    lineHeight: 1.65,
    fontSize: 14,
    wordBreak: "break-word",
    whiteSpace: "pre-wrap",
  },
  userBubble: {
    background: "#16a34a",
    color: "#f0fff4",
    borderBottomRightRadius: 3,
  },
  aiBubble: {
    background: "#111a11",
    border: "1px solid #1e341e",
    color: "#d4ead4",
    borderBottomLeftRadius: 3,
  },
  bubbleContent: {},
  bubbleTime: {
    fontSize: 10.5,
    color: "rgba(255,255,255,0.35)",
    marginTop: 5,
    textAlign: "right",
  },
  inputWrap: {
    padding: "12px 20px 16px",
    borderTop: "1px solid #1a2a1a",
    background: "#0d140d",
  },
  inputBox: {
    display: "flex",
    alignItems: "flex-end",
    gap: 10,
    background: "#111a11",
    border: "1px solid #1e341e",
    borderRadius: 14,
    padding: "8px 8px 8px 16px",
    transition: "border-color 0.15s",
  },
  textarea: {
    flex: 1,
    background: "transparent",
    border: "none",
    outline: "none",
    color: "#d4ead4",
    fontSize: 14,
    resize: "none",
    fontFamily: "inherit",
    lineHeight: 1.6,
    padding: 0,
    minHeight: 24,
  },
  sendBtn: {
    width: 36,
    height: 36,
    borderRadius: 10,
    flexShrink: 0,
    background: "#16a34a",
    border: "none",
    color: "#fff",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "all 0.15s",
  },
  sendBtnDisabled: {
    background: "#1a2a1a",
    color: "#3a5a3a",
    cursor: "default",
  },
  inputHint: {
    fontSize: 11,
    color: "#2a4a2a",
    marginTop: 7,
    textAlign: "center",
  },
};

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  ::-webkit-scrollbar { width: 3px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #1e341e; border-radius: 99px; }
  .msg-row { animation: msgIn 0.2s ease; }
  @keyframes msgIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; } }
  @keyframes td { 0%,80%,100% { opacity: 0.2; transform: scale(0.75); } 40% { opacity: 1; transform: scale(1); } }
  .new-chat-btn:hover { background: #16a34a33 !important; border-color: #16a34a99 !important; }
  .history-item:hover { background: #16a34a10 !important; }
  .history-item:hover .delete-btn { opacity: 1 !important; }
  .delete-btn:hover { background: #3a1a1a !important; color: #f87171 !important; }
  .prompt-chip:hover { background: #16a34a18 !important; border-color: #16a34a55 !important; color: #86efac !important; }
  .send-btn:hover:not(:disabled) { background: #15803d !important; transform: scale(1.05); }
  .menu-btn:hover { color: #86efac !important; }
  .chat-textarea::placeholder { color: #2a4a2a; }
  .chat-textarea:focus { outline: none; }
  .input-box-focused { border-color: #16a34a66 !important; }
`;
