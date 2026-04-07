import { useState, useRef, useEffect } from "react";

const API_URL = "http://127.0.0.1:8000/chat";
const USER_ID = "user-" + Math.random().toString(36).slice(2, 9);

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: USER_ID,
          state: { evaluation: text },
        }),
      });
      const data = await res.json();
      const aiMsg = { role: "ai", content: data.response || data.error || "No response" };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "ai", content: "⚠️ Could not reach server." }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={styles.root}>
      <style>{css}</style>
      <div style={styles.sidebar}>
        <div style={styles.logo}>◈</div>
        <div style={styles.logoLabel}>ASTRA</div>
        <div style={styles.sidebarSpacer} />
        <div style={styles.sessionTag}>Session<br /><span style={styles.sessionId}>{USER_ID.slice(-6)}</span></div>
      </div>

      <div style={styles.main}>
        <div style={styles.header}>
          <span style={styles.headerTitle}>Chat Interface</span>
          <span style={styles.headerStatus}>
            <span style={{ ...styles.dot, background: loading ? "#f59e0b" : "#22d3ee" }} />
            {loading ? "Thinking…" : "Ready"}
          </span>
        </div>

        <div style={styles.messages}>
          {messages.length === 0 && (
            <div style={styles.empty}>
              <div style={styles.emptyIcon}>◈</div>
              <div style={styles.emptyText}>Send a message to begin</div>
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`msg-row ${m.role}`}
              style={{ ...styles.msgRow, justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}
            >
              {m.role === "ai" && <div style={styles.avatar}>◈</div>}
              <div style={{ ...styles.bubble, ...(m.role === "user" ? styles.userBubble : styles.aiBubble) }}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ ...styles.msgRow, justifyContent: "flex-start" }}>
              <div style={styles.avatar}>◈</div>
              <div style={{ ...styles.bubble, ...styles.aiBubble, ...styles.typingBubble }}>
                <span className="dot-1" style={styles.typingDot} />
                <span className="dot-2" style={styles.typingDot} />
                <span className="dot-3" style={styles.typingDot} />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div style={styles.inputRow}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Type a message…"
            rows={1}
            style={styles.textarea}
            className="chat-input"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            style={{ ...styles.sendBtn, opacity: loading || !input.trim() ? 0.4 : 1 }}
            className="send-btn"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  root: {
    display: "flex",
    height: "100vh",
    background: "#080c14",
    fontFamily: "'DM Mono', 'Courier New', monospace",
    color: "#e2e8f0",
    overflow: "hidden",
  },
  sidebar: {
    width: 64,
    background: "#0d1220",
    borderRight: "1px solid #1e2a3a",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    paddingTop: 24,
    paddingBottom: 24,
    gap: 4,
  },
  logo: { fontSize: 22, color: "#22d3ee", lineHeight: 1 },
  logoLabel: { fontSize: 9, letterSpacing: 3, color: "#334155", marginTop: 4 },
  sidebarSpacer: { flex: 1 },
  sessionTag: { fontSize: 8, color: "#334155", textAlign: "center", letterSpacing: 1, lineHeight: 1.8 },
  sessionId: { color: "#22d3ee", fontSize: 9 },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  header: {
    padding: "16px 28px",
    borderBottom: "1px solid #1e2a3a",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    background: "#0a1020",
  },
  headerTitle: { fontSize: 11, letterSpacing: 3, color: "#94a3b8", textTransform: "uppercase" },
  headerStatus: { display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "#64748b" },
  dot: { width: 7, height: 7, borderRadius: "50%", display: "inline-block", transition: "background 0.3s" },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "32px 28px",
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  empty: { margin: "auto", textAlign: "center", opacity: 0.3 },
  emptyIcon: { fontSize: 36, color: "#22d3ee", marginBottom: 12 },
  emptyText: { fontSize: 12, letterSpacing: 2, color: "#94a3b8" },
  msgRow: { display: "flex", alignItems: "flex-end", gap: 12 },
  avatar: {
    width: 30, height: 30, borderRadius: "50%",
    background: "#0d1e35", border: "1px solid #1e3a5a",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 12, color: "#22d3ee", flexShrink: 0,
  },
  bubble: {
    maxWidth: "68%", padding: "12px 16px",
    fontSize: 14, lineHeight: 1.65, borderRadius: 2,
    whiteSpace: "pre-wrap", wordBreak: "break-word",
  },
  userBubble: {
    background: "#0e2a4a",
    border: "1px solid #1e4a7a",
    color: "#bae6fd",
    borderBottomRightRadius: 0,
  },
  aiBubble: {
    background: "#0d1220",
    border: "1px solid #1e2a3a",
    color: "#e2e8f0",
    borderBottomLeftRadius: 0,
  },
  typingBubble: { display: "flex", gap: 6, alignItems: "center", padding: "14px 20px" },
  typingDot: {
    width: 6, height: 6, borderRadius: "50%",
    background: "#22d3ee", display: "inline-block",
  },
  inputRow: {
    padding: "16px 28px 20px",
    borderTop: "1px solid #1e2a3a",
    display: "flex",
    gap: 12,
    alignItems: "flex-end",
    background: "#0a1020",
  },
  textarea: {
    flex: 1, background: "#0d1728",
    border: "1px solid #1e2a3a",
    borderRadius: 2, color: "#e2e8f0",
    fontSize: 14, padding: "12px 16px",
    resize: "none", outline: "none",
    fontFamily: "inherit", lineHeight: 1.6,
    maxHeight: 120, overflowY: "auto",
  },
  sendBtn: {
    width: 44, height: 44, borderRadius: 2,
    background: "#22d3ee", border: "none",
    color: "#080c14", fontSize: 18,
    cursor: "pointer", fontWeight: "bold",
    display: "flex", alignItems: "center", justifyContent: "center",
    transition: "opacity 0.2s, transform 0.1s",
    flexShrink: 0,
  },
};

const css = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #080c14; }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #1e2a3a; border-radius: 2px; }
  .chat-input:focus { border-color: #22d3ee !important; box-shadow: 0 0 0 1px #22d3ee22; }
  .chat-input::placeholder { color: #334155; }
  .send-btn:hover:not(:disabled) { transform: translateY(-1px); }
  .send-btn:active:not(:disabled) { transform: translateY(0); }
  .msg-row { animation: fadeUp 0.25s ease; }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  .dot-1 { animation: pulse 1.2s infinite 0s; }
  .dot-2 { animation: pulse 1.2s infinite 0.2s; }
  .dot-3 { animation: pulse 1.2s infinite 0.4s; }
  @keyframes pulse { 0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1); } }
`;