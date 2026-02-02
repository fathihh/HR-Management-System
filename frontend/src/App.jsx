import { useState } from "react";
import Chat from "./components/Chat";
import Login from "./components/Login";
import LeaveRequestForm from "./components/LeaveRequestForm";
import HRPendingApprovals from "./components/HRPendingApprovals";
import NotificationsBell from "./components/NotificationsBell";

function Header() {
  return (
    <header className="w-full border-b border-white/10 bg-white/5 backdrop-blur">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#7cc3ff] to-[#3ba3ff] grid place-items-center font-extrabold text-[#081120]">
            360
          </div>
          <div>
            <div className="text-white font-extrabold">AUREON 360</div>
            <div className="text-xs text-white/70 -mt-0.5">Smarter workflows. Happier teams.</div>
          </div>
        </div>
      </div>
    </header>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [tab, setTab] = useState("chat");   // default Chat visible

  const logout = () => {
    setUser(null);
    setTab("chat");
  };

  if (!user) {
    return (
      <div className="min-h-screen bg-[radial-gradient(1200px_600px_at_50%_-100px,#0b1b33_0%,#070f1c_60%,#060b13_100%)] text-white">
        <main className="max-w-6xl mx-auto px-4">
          <Login onLogin={setUser} />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(1200px_600px_at_50%_-100px,#0b1b33_0%,#070f1c_60%,#060b13_100%)] text-white">
      <Header />

      <main className="max-w-6xl mx-auto px-4 pt-4 pb-2 flex flex-col min-h-[calc(100vh-64px)]">
        {/* Tabs and actions */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex gap-2">
            <button
              onClick={() => setTab("chat")}
              className={`px-3 py-2 rounded-xl border ${tab === "chat" ? "bg-white/10 border-white/20" : "bg-white/5 border-white/10 hover:bg-white/10"}`}
            >
              Chat
            </button>

            {user.role === "employee" && (
              <button
                onClick={() => setTab("leave")}
                className={`px-3 py-2 rounded-xl border ${tab === "leave" ? "bg-white/10 border-white/20" : "bg-white/5 border-white/10 hover:bg-white/10"}`}
              >
                Leave
              </button>
            )}

            {user.role === "hr" && (
              <button
                onClick={() => setTab("approvals")}
                className={`px-3 py-2 rounded-xl border ${tab === "approvals" ? "bg-white/10 border-white/20" : "bg-white/5 border-white/10 hover:bg-white/10"}`}
              >
                Approvals
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <NotificationsBell role={user.role} employeeId={user.employeeId} />
            <button
              onClick={logout}
              className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10"
            >
              Logout
            </button>
          </div>
        </div>

        {/* Content area fills the remaining height so Chat is always visible */}
        <div className="flex-1 min-h-0">
          {tab === "chat" && <Chat user={user} onLogout={logout} />}
          {tab === "leave" && user.role === "employee" && <LeaveRequestForm employeeId={user.employeeId} />}
          {tab === "approvals" && user.role === "hr" && <HRPendingApprovals />}
        </div>
      </main>
    </div>
  );
}
