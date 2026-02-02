import { useEffect, useState } from "react";
import { Check, X, RefreshCw } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function HRPendingApprovals() {
  const [items, setItems] = useState([]);
  const [loadingList, setLoadingList] = useState(false);
  const [actionMsg, setActionMsg] = useState("");
  const [actionErr, setActionErr] = useState("");

  const fetchPending = async () => {
    try {
      setLoadingList(true);
      const resp = await fetch(`${API_BASE}/api/leave/pending`, { headers: { Accept: "application/json" }});
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      setItems(Array.isArray(data) ? data : []);
    } catch {
      setActionErr("Failed to load pending requests");
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    fetchPending();
  }, []);

  const friendlyError = async (resp) => {
    let detail = "";
    try {
      const j = await resp.json();
      detail = j.detail || j.error || JSON.stringify(j);
    } catch {
      try {
        detail = await resp.text();
      } catch {
        detail = "Unknown error";
      }
    }
    return detail;
  };

  const decide = async (id, decision) => {
    setActionErr("");
    setActionMsg("");
    try {
      const resp = await fetch(`${API_BASE}/api/leave/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ request_id: id, decision, hr_actor: "HR Portal" }),
      });

      if (!resp.ok) {
        const detail = await friendlyError(resp);
        throw new Error(detail);
      }

      const data = await resp.json();
      // Green success banner
      setActionMsg(`✅ ${data.message || `${decision} successfully`}`);
      setActionErr("");
      fetchPending();
    } catch (e) {
      setActionMsg("");
      setActionErr(`Failed to ${decision.toLowerCase()}: ${e.message}`);
    }
  };

  return (
    <div className="h-full flex flex-col rounded-2xl bg-white/5 border border-white/10 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-semibold text-lg">Pending Leave Approvals</h3>
        <button
          onClick={fetchPending}
          disabled={loadingList}
          className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 text-white/90 disabled:opacity-50"
        >
          <RefreshCw className="w-4 h-4 inline mr-1" />
          Refresh
        </button>
      </div>

      {actionMsg && <div className="text-emerald-300 text-sm mb-2">{actionMsg}</div>}
      {actionErr && <div className="text-red-300 text-sm mb-2">❌ {actionErr}</div>}

      <div className="space-y-3 overflow-y-auto">
        {items.length === 0 && (
          <div className="text-white/60 text-sm">No pending requests.</div>
        )}

        {items.map((r) => (
          <div
            key={r.id}
            className="rounded-xl bg-white/5 border border-white/10 p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3"
          >
            <div className="text-white/90">
              <div className="font-semibold">
                {r.Name || `Emp ${r.employee_id}`}{" "}
                <span className="text-white/60">• ID {r.employee_id}</span>
              </div>
              <div className="text-sm text-white/80">
                Dept: {r.Department || "-"} • Days: {r.days || "-"} • {r.start_date} → {r.end_date}
              </div>
              {r.reason && <div className="text-sm text-white/75">Reason: {r.reason}</div>}
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => decide(r.id, "APPROVED")}
                className="px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white"
              >
                <Check className="w-4 h-4 inline mr-1" /> Approve
              </button>
              <button
                onClick={() => decide(r.id, "REJECTED")}
                className="px-3 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white"
              >
                <X className="w-4 h-4 inline mr-1" /> Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
