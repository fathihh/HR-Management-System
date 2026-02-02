import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, LogOut, Upload } from "lucide-react";
import { queryAPI, uploadAPI } from "../services/api";
import NotificationsBell from "./NotificationsBell";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const Chat = ({ user, onLogout }) => {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: `Welcome ${
        user.role === "hr" ? "HR" : `Employee ${user.employeeId}`
      }! How can I assist you today?`,
      status: "info",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const pushMessage = (msg) => setMessages((m) => [...m, msg]);

  // Detect simple leave-related intents
  const detectIntent = (text) => {
    const lower = text.toLowerCase();
    if (
      lower.includes("how many leaves") ||
      lower.includes("leaves left") ||
      lower.includes("leave balance")
    )
      return { intent: "LEAVES_LEFT" };

    const regex =
      /apply\s+leave\s+(?:from\s*)?([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}-[0-9]{2}-[0-9]{4})\s*(?:to|-)\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}-[0-9]{2}-[0-9]{4})(?:\s+for\s+(.*))?/i;
    const match = text.match(regex);
    if (match)
      return {
        intent: "APPLY_LEAVE",
        start: match[1],
        end: match[2],
        reason: match[3] || "Requested via chat",
      };
    return { intent: "UNKNOWN" };
  };

  const send = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    pushMessage({ role: "user", content: text, status: "sent" });
    setLoading(true);

    try {
      const intent = detectIntent(text);
      if (intent.intent === "LEAVES_LEFT" || intent.intent === "APPLY_LEAVE") {
        const payload = {
          role: user.role,
          employee_id: user.employeeId,
          text,
        };

        const resp = await fetch(`${API_BASE}/api/chat/message`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const result = await resp.json();
        if (result.success) {
          pushMessage({
            role: "assistant",
            content: result.message,
            status: "success",
          });

          // ✅ Trigger HR notification refresh when employee applies leave
          if (intent.intent === "APPLY_LEAVE") {
            window.dispatchEvent(
              new CustomEvent("hrms-notify-refresh", {
                detail: "refresh-notifications",
              })
            );
          }
        } else {
          pushMessage({
            role: "assistant",
            content: `❌ ${result.message || "Failed"}`,
            status: "error",
          });
        }
      } else {
        // fallback: LLM / HR Q&A query
        const resp = await queryAPI.sendQuery(text);
        if (resp.success) {
          let ans = resp.response || "";
          if (ans.includes("Source:")) ans = ans.split("Source:")[0].trim();
          pushMessage({ role: "assistant", content: ans, status: "success" });
        } else {
          pushMessage({
            role: "assistant",
            content: `❌ ${resp.error || "Request failed"}`,
            status: "error",
          });
        }
      }
    } catch (err) {
      pushMessage({
        role: "assistant",
        content: `❌ ${err.message || "Something went wrong"}`,
        status: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  const keyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const onUpload = async (e, type) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const resp =
        type === "csv"
          ? await uploadAPI.uploadCSV(file)
          : await uploadAPI.uploadPDF(file);
      pushMessage({
        role: "assistant",
        content: `✅ ${resp.message}`,
        status: "success",
      });
      setShowUpload(false);
    } catch (err) {
      pushMessage({
        role: "assistant",
        content: `❌ Upload failed: ${err.message}`,
        status: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col rounded-xl overflow-hidden bg-white/5 border border-white/10">
      {/* Controls */}
      <div className="px-4 py-3 border-b border-white/10 bg-white/5 flex items-center justify-end gap-2">
        {user.role === "hr" && (
          <button
            onClick={() => setShowUpload((s) => !s)}
            className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10"
          >
            <Upload className="w-4 h-4 inline mr-1" /> Upload
          </button>
        )}
        <NotificationsBell role={user.role} employeeId={user.employeeId} />
        <button
          onClick={onLogout}
          className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10"
        >
          <LogOut className="w-4 h-4 inline mr-1" /> Logout
        </button>
      </div>

      {/* Upload section for HR */}
      {showUpload && user.role === "hr" && (
        <div className="px-4 py-3 border-b border-white/10 bg-white/5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-white/70 mb-1">
                Upload Employee CSV
              </label>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => onUpload(e, "csv")}
                className="w-full bg-white text-black rounded-md px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-white/70 mb-1">
                Upload Policy PDF
              </label>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => onUpload(e, "pdf")}
                className="w-full bg-white text-black rounded-md px-3 py-2"
              />
            </div>
          </div>
        </div>
      )}

      {/* Chat messages */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-3">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex gap-3 ${
              m.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {m.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-blue-400/20 border border-white/10 grid place-items-center">
                <Bot className="w-5 h-5 text-blue-300" />
              </div>
            )}
            <div
              className={`max-w-2xl px-4 py-3 rounded-lg ${
                m.role === "user"
                  ? "bg-blue-600 text-white"
                  : m.status === "error"
                  ? "bg-rose-700/20 border border-rose-400/20 text-rose-200"
                  : "bg-white/8 border border-white/10 text-white"
              }`}
            >
              <pre className="whitespace-pre-wrap text-sm">{m.content}</pre>
            </div>
            {m.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-white/10 border border-white/10 grid place-items-center">
                <User className="w-5 h-5 text-white/80" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-2 items-center text-white/70 text-sm">
            <div className="w-2 h-2 rounded-full bg-white/60 animate-bounce" />
            <div className="w-2 h-2 rounded-full bg-white/60 animate-bounce delay-100" />
            <div className="w-2 h-2 rounded-full bg-white/60 animate-bounce delay-200" />
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-white/10 bg-white/5">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={keyDown}
            rows={2}
            placeholder="Ask me anything… (Try 'How many leaves left?' or 'Apply leave from 2025-11-10 to 2025-11-12 for medical')"
            className="w-full px-4 py-3 rounded-lg bg-white text-black placeholder-gray-500 border border-white/10 focus:ring-2 focus:ring-blue-500/60"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="px-6 rounded-lg bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Chat;
