import { useEffect, useRef, useState } from "react";
import { Bell, RefreshCw } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function NotificationsBell({ role, employeeId }) {
  const [open, setOpen] = useState(false);
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasNew, setHasNew] = useState(false);
  const lastIdsRef = useRef([]);

  const fetchNotifications = async (manual = false) => {
    try {
      if (!manual) setLoading(true);
      const url =
        role === "hr"
          ? `${API_BASE}/api/notifications/0?role=HR`
          : `${API_BASE}/api/notifications/${employeeId}?role=EMPLOYEE`;

      const resp = await fetch(url);
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();

      // Compare IDs to detect new notifications
      const ids = data.map((n) => n.id);
      const lastIds = lastIdsRef.current;
      if (lastIds.length > 0 && ids.length > 0 && ids[0] && !lastIds.includes(ids[0])) {
        setHasNew(true);
      }
      lastIdsRef.current = ids;
      setList(data);
    } catch (err) {
      console.error("Notification fetch failed:", err);
    } finally {
      setLoading(false);
    }
  };

  // Allow external trigger from chat (global event bus)
  useEffect(() => {
    const handler = (e) => {
      if (e.detail === "refresh-notifications") fetchNotifications(true);
    };
    window.addEventListener("hrms-notify-refresh", handler);
    return () => window.removeEventListener("hrms-notify-refresh", handler);
  }, []);

  // Initial load + 30s polling
  useEffect(() => {
    fetchNotifications();
    const t = setInterval(fetchNotifications, 30000);
    return () => clearInterval(t);
  }, [role, employeeId]);

  const handleRefresh = () => {
    fetchNotifications(true);
    setHasNew(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => {
          setOpen((o) => !o);
          setHasNew(false);
        }}
        className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 text-white/90 relative"
        title="Notifications"
      >
        <Bell className={`w-4 h-4 inline ${hasNew ? "text-amber-300" : ""}`} />
        {hasNew && (
          <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-amber-400 animate-pulse" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-[320px] rounded-2xl bg-[#0b1626]/95 border border-white/10 shadow-xl z-50">
          <div className="p-3 border-b border-white/10 flex items-center justify-between">
            <div className="text-white font-medium">Notifications</div>
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="text-white/80 hover:text-white"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>

          <div className="max-h-[320px] overflow-y-auto p-2 space-y-2">
            {list.length === 0 && (
              <div className="text-white/60 text-sm px-2 py-3">
                No notifications yet
              </div>
            )}

            {list.map((n) => (
              <div
                key={n.id}
                className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm hover:bg-white/10 transition"
              >
                <div className="text-white/90 font-medium">{n.title}</div>
                <div className="text-white/75 whitespace-pre-wrap">{n.body}</div>
                <div className="text-white/50 text-xs mt-1">{n.created_at}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
