import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Calendar } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function LeaveRequestForm({ employeeId }) {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [days, setDays] = useState("");
  const [reason, setReason] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const [myLeaves, setMyLeaves] = useState([]);
  const [loadingList, setLoadingList] = useState(false);

  const calcDaysPreview = useMemo(() => {
    try {
      if (!startDate || !endDate) return "";
      const s = new Date(startDate);
      const e = new Date(endDate);
      if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return "";
      const diff = Math.floor((e - s) / (24 * 3600 * 1000)) + 1;
      return diff > 0 ? String(diff) : "";
    } catch {
      return "";
    }
  }, [startDate, endDate]);

  const fetchMine = async () => {
    try {
      setLoadingList(true);
      const resp = await fetch(`${API_BASE}/api/leave/mine/${employeeId}`);
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      setMyLeaves(Array.isArray(data) ? data : []);
    } catch {
      // silent
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    if (employeeId) fetchMine();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employeeId]);

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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setOk("");

    if (!startDate || !endDate) {
      setError("Please select both start and end dates.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        employee_id: Number(employeeId),
        start_date: startDate, // backend accepts YYYY-MM-DD or DD-MM-YYYY
        end_date: endDate,
        days: days ? Number(days) : null, // backend will compute if null
        reason: reason || null,
      };

      const resp = await fetch(`${API_BASE}/api/leave/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const detail = await friendlyError(resp);
        throw new Error(detail);
      }

      const data = await resp.json();
      // Green success ribbon
      setOk(`✅ ${data.message || "Leave request submitted"}`);
      setError("");

      // reset form
      setStartDate("");
      setEndDate("");
      setDays("");
      setReason("");

      // refresh list
      fetchMine();
    } catch (e) {
      setOk("");
      setError(e.message || "Failed to submit leave");
    } finally {
      setSubmitting(false);
    }
  };

  const shownDays = days || calcDaysPreview || "";

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Request panel */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
        <h3 className="text-white font-semibold text-lg mb-4">Request Leave</h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-sm text-white/70 mb-1">Start date</label>
              <div className="relative">
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => {
                    setStartDate(e.target.value);
                    setOk(""); setError("");
                  }}
                  className="w-full px-3 py-2 rounded-md bg-white text-black placeholder-gray-500 border border-white/10"
                />
                <Calendar className="absolute right-3 top-2.5 w-4 h-4 text-gray-500 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-sm text-white/70 mb-1">End date</label>
              <div className="relative">
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => {
                    setEndDate(e.target.value);
                    setOk(""); setError("");
                  }}
                  className="w-full px-3 py-2 rounded-md bg-white text-black placeholder-gray-500 border border-white/10"
                />
                <Calendar className="absolute right-3 top-2.5 w-4 h-4 text-gray-500 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-sm text-white/70 mb-1">Days</label>
              <input
                type="number"
                min="1"
                value={shownDays}
                onChange={(e) => {
                  setDays(e.target.value);
                  setOk(""); setError("");
                }}
                placeholder="auto if empty"
                className="w-full px-3 py-2 rounded-md bg-white text-black placeholder-gray-500 border border-white/10"
              />
              <p className="text-xs text-white/50 mt-1">
                Leave empty to auto-calculate from dates.
              </p>
            </div>
          </div>

          <div>
            <label className="block text-sm text-white/70 mb-1">Reason (optional)</label>
            <input
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                setOk(""); setError("");
              }}
              placeholder="e.g., Medical appointment"
              className="w-full px-3 py-2 rounded-md bg-white text-black placeholder-gray-500 border border-white/10"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
            >
              Submit
            </button>

            {ok && <span className="text-emerald-300 text-sm">{ok}</span>}
            {error && <span className="text-red-400 text-sm">❌ {error}</span>}

            <span className="text-xs text-white/50">
              Tip: use 2025-10-26 or 26-10-2025. If “Days” is empty, we calculate it.
            </span>
          </div>
        </form>
      </div>

      {/* My requests */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-5 flex-1 min-h-0">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-white font-semibold text-lg">My Leave Requests</h3>
          <button
            onClick={fetchMine}
            disabled={loadingList}
            className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 text-white/90 disabled:opacity-50"
          >
            <RefreshCw className="w-4 h-4 inline mr-1" />
            Refresh
          </button>
        </div>

        <div className="space-y-3 overflow-y-auto max-h-[45vh] pr-1">
          {myLeaves.length === 0 && (
            <div className="text-white/60 text-sm">No leave requests yet.</div>
          )}

          {myLeaves.map((r) => (
            <div key={r.id} className="rounded-xl bg-white/5 border border-white/10 p-4">
              <div className="text-white/90">
                <div className="text-sm">
                  <span className="font-medium">Period:</span> {r.start_date} → {r.end_date}
                </div>
                <div className="text-sm">
                  <span className="font-medium">Days:</span> {r.days || "-"}
                </div>
                {r.reason && (
                  <div className="text-sm">
                    <span className="font-medium">Reason:</span> {r.reason}
                  </div>
                )}
              </div>

              <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-white/70">
                <div>Created: {r.created_at || "-"}</div>
                <div>Decided: {r.decided_at || "-"}</div>
                <div
                  className={`font-semibold ${
                    r.status === "APPROVED"
                      ? "text-emerald-300"
                      : r.status === "REJECTED"
                      ? "text-red-300"
                      : "text-yellow-300"
                  }`}
                >
                  Status: {r.status}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
