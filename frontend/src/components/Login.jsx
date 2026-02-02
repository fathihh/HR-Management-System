import { useState } from "react";
import { Building2, User, LogIn, MailCheck } from "lucide-react";
import { authAPI } from "../services/api";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Login({ onLogin }) {
  const [role, setRole] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");

  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const requestOTP = async () => {
    setError("");
    setMsg("");

    if (!role) return setError("Please select a role");
    if (role === "employee" && !employeeId.trim()) {
      return setError("Please enter your employee ID");
    }
    setLoading(true);
    try {
      const payload =
        role === "employee"
          ? { role, employee_id: Number(employeeId) }
          : { role };
      const resp = await fetch(`${API_BASE}/api/auth/request-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        throw new Error(j.detail || "Failed to send OTP");
      }
      const data = await resp.json();
      setOtpSent(true);
      setMsg(data.message || "OTP sent. Please check your email.");
      // For dev mode only if EMAIL_DISABLE_SEND=true, backend returns dev_code
      if (data.dev_code) setMsg((m) => `${m} (Dev code: ${data.dev_code})`);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const verifyAndLogin = async (e) => {
    e.preventDefault();
    setError("");
    setMsg("");

    if (!otp.trim()) return setError("Please enter the OTP code");

    setLoading(true);
    try {
      const payload =
        role === "employee"
          ? { role, employee_id: Number(employeeId), code: otp.trim() }
          : { role, code: otp.trim() };

      const resp = await fetch(`${API_BASE}/api/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        throw new Error(j.detail || "OTP verification failed");
      }
      // After OTP success, call your existing /api/login to set context
      const loginResp = await authAPI.login(role, role === "employee" ? employeeId : null);
      if (loginResp?.success) {
        onLogin({
          role,
          employeeId: role === "employee" ? employeeId : null,
        });
      } else {
        throw new Error(loginResp?.message || "Login failed");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full overflow-hidden flex items-center justify-center">
      {/* Centered card */}
      <div className="card animate-fadeIn w-full max-w-xl">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-blue-500/15 border border-white/10 flex items-center justify-center mb-4">
            <Building2 className="w-7 h-7 text-blue-400" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight">AUREON 360</h1>
          <p className="text-white/70 mt-1">Smarter workflows. Happier teams.</p>
        </div>

        <form onSubmit={verifyAndLogin} className="space-y-5">
          {/* Role select */}
          <div>
            <label className="block text-sm text-white/70 mb-2">Select Role</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => { setRole("employee"); setOtpSent(false); setOtp(""); setMsg(""); setError(""); }}
                className={`flex flex-col items-center justify-center h-20 rounded-xl border transition ${
                  role === "employee"
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-white/10 bg-white/5 hover:bg-white/10"
                }`}
              >
                <User className="w-6 h-6 mb-1" />
                <span className="font-medium">Employee</span>
              </button>
              <button
                type="button"
                onClick={() => { setRole("hr"); setOtpSent(false); setOtp(""); setMsg(""); setError(""); }}
                className={`flex flex-col items-center justify-center h-20 rounded-xl border transition ${
                  role === "hr"
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-white/10 bg-white/5 hover:bg-white/10"
                }`}
              >
                <Building2 className="w-6 h-6 mb-1" />
                <span className="font-medium">HR</span>
              </button>
            </div>
          </div>

          {/* Employee ID input */}
          {role === "employee" && (
            <div>
              <label className="block text-sm text-white/70 mb-2">Employee ID</label>
              <input
                className="input-field bg-white text-black placeholder-gray-500"
                placeholder="Enter your employee ID"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
              />
            </div>
          )}

          {/* OTP Step */}
          {!otpSent ? (
            <button
              type="button"
              onClick={requestOTP}
              disabled={loading || !role || (role === "employee" && !employeeId.trim())}
              className="btn-secondary flex items-center justify-center gap-2"
            >
              <MailCheck className="w-5 h-5" />
              {loading ? "Sending OTP..." : "Send OTP"}
            </button>
          ) : (
            <>
              <div>
                <label className="block text-sm text-white/70 mb-2">Enter OTP</label>
                <input
                  className="input-field bg-white text-black placeholder-gray-500"
                  placeholder="6-digit code"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                />
              </div>

              <button
                type="submit"
                disabled={loading || !otp.trim()}
                className="btn-primary flex items-center justify-center gap-2"
              >
                <LogIn className="w-5 h-5" />
                {loading ? "Verifying..." : "Verify & Login"}
              </button>
            </>
          )}

          {/* Messages */}
          {msg && (
            <div className="text-sm text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-3 py-2">
              {msg}
            </div>
          )}
          {error && (
            <div className="text-sm text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-xl px-3 py-2">
              {error}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
