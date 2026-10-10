// App shell: left nav, top bar (target role, mode, "Delete my data"), the page outlet and the persistent chat
// panel on the right edge. Also executes the chatbot's UI actions (open_map / open_career_map / open_interview).
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BarChart3,
  Info,
  LayoutDashboard,
  Map as MapIcon,
  MessageSquare,
  Mic,
  ShieldCheck,
  Trash2,
  Upload as UploadIcon,
} from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { hasCV, useProfileStore } from "../../store/profile";
import { useSessionStore } from "../../store/session";
import ChatPanel from "../chat/ChatPanel";
import type { UserMode } from "../../types/profile";

const NAV = [
  { to: "/upload", label: "Upload CV", icon: UploadIcon },
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/career", label: "Career Map", icon: MapIcon },
  { to: "/analyzer", label: "CV Analyzer", icon: ShieldCheck },
  { to: "/interview", label: "Mock Interview", icon: Mic },
  { to: "/built-with", label: "Built with", icon: Info },
];

export default function Shell() {
  const navigate = useNavigate();
  const profile = useProfileStore((s) => s.profile);
  const setProfile = useProfileStore((s) => s.setProfile);
  const clearProfile = useProfileStore((s) => s.clear);
  const chatOpen = useSessionStore((s) => s.chatOpen);
  const setChatOpen = useSessionStore((s) => s.setChatOpen);
  const pendingAction = useSessionStore((s) => s.pendingAction);
  const setPendingAction = useSessionStore((s) => s.setPendingAction);
  const serverExpired = useSessionStore((s) => s.serverExpired);
  const setServerExpired = useSessionStore((s) => s.setServerExpired);
  const setRole = useSessionStore((s) => s.setRole);
  const setRadiusKm = useSessionStore((s) => s.setRadiusKm);
  const setKeyword = useSessionStore((s) => s.setKeyword);
  const resetSession = useSessionStore((s) => s.reset);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // The chatbot's tool calls open the other screens ("show me data jobs within 25 km" opens the map filtered).
  useEffect(() => {
    if (!pendingAction) return;
    switch (pendingAction.type) {
      case "open_map":
        setRadiusKm(Math.max(1, Math.min(200, Math.round(pendingAction.radius_km))));
        setKeyword(pendingAction.keyword ?? "");
        navigate("/career");
        break;
      case "open_career_map":
        setRole(pendingAction.role);
        navigate("/career");
        break;
      case "open_interview":
        navigate(`/interview?role=${encodeURIComponent(pendingAction.role)}`);
        break;
    }
    setPendingAction(null);
  }, [pendingAction, navigate, setKeyword, setPendingAction, setRadiusKm, setRole]);

  // On load, check the server still has the session: an in-memory restart means the CV must be re-uploaded.
  useEffect(() => {
    if (!hasCV(profile)) return;
    let cancelled = false;
    api
      .getProfile()
      .then((server) => {
        if (cancelled) return;
        if (server.skills.length === 0) setServerExpired(true);
        else {
          setServerExpired(false);
          setProfile(server);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // Only on mount: later uploads set the profile themselves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function changeMode(mode: UserMode) {
    if (!profile) return;
    try {
      setProfile(await api.patchProfile({ mode }));
    } catch (err) {
      setNotice(errorMessage(err));
    }
  }

  // First click arms the button for 6 s, second click deletes. (window.confirm can be suppressed by the browser.)
  const [confirmDelete, setConfirmDelete] = useState(false);
  useEffect(() => {
    if (!confirmDelete) return;
    const id = window.setTimeout(() => setConfirmDelete(false), 6000);
    return () => window.clearTimeout(id);
  }, [confirmDelete]);

  async function deleteMyData() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setConfirmDelete(false);
    setBusy(true);
    try {
      await api.deleteProfile();
    } catch (err) {
      setNotice(`Server: ${errorMessage(err)} (browser data was still cleared)`);
    } finally {
      clearProfile();
      resetSession();
      try {
        window.localStorage.removeItem("careerlens-profile");
        window.localStorage.removeItem("careerlens-session");
      } catch {
        /* storage unavailable */
      }
      setBusy(false);
      navigate("/upload");
    }
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex items-center gap-2 px-5 py-5">
          <BarChart3 className="h-6 w-6 text-brand-600" aria-hidden />
          <span className="text-lg font-bold tracking-tight">CareerLens</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <p className="px-5 py-4 text-[11px] leading-snug text-slate-400">
          Skills-only matching: no name, gender, age, university or photo reaches the model. Video never leaves your
          browser.
        </p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
          <div className="flex items-center gap-2 lg:hidden">
            <BarChart3 className="h-5 w-5 text-brand-600" aria-hidden />
            <span className="font-bold">CareerLens</span>
          </div>
          <nav className="-mx-1 flex gap-1 overflow-x-auto lg:hidden">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-md px-2 py-1 text-xs font-medium ${
                    isActive ? "bg-brand-50 text-brand-700" : "text-slate-600"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {profile && (
              <>
                {profile.target_role && (
                  <span className="hidden rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600 sm:inline">
                    Target: <strong>{profile.target_role}</strong>
                  </span>
                )}
                <select
                  aria-label="Mode"
                  className="input w-auto py-1 text-xs"
                  value={profile.mode}
                  onChange={(e) => changeMode(e.target.value as UserMode)}
                >
                  <option value="student">Student</option>
                  <option value="job_seeker">Job seeker</option>
                </select>
                <button
                  className={`text-xs ${confirmDelete ? "btn-primary bg-red-600 hover:bg-red-700" : "btn-ghost"}`}
                  onClick={deleteMyData}
                  disabled={busy}
                  title={confirmDelete ? "Deletes your CV, profile, reports and chat from this browser and the server" : "DELETE /profile"}
                  aria-live="polite"
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                  <span className={confirmDelete ? "inline" : "hidden sm:inline"}>
                    {confirmDelete ? "Click again to delete everything" : "Delete my data"}
                  </span>
                </button>
              </>
            )}
            <button
              className="btn-secondary text-xs"
              onClick={() => setChatOpen(!chatOpen)}
              aria-pressed={chatOpen}
              title="Career assistant"
            >
              <MessageSquare className="h-4 w-4" aria-hidden />
              <span className="hidden sm:inline">Assistant</span>
            </button>
          </div>
        </header>

        {serverExpired && (
          <div className="flex flex-wrap items-center gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
            The server session was reset (it keeps the profile in memory only). Re-upload your CV to continue.
            <button className="btn-primary py-1 text-xs" onClick={() => navigate("/upload")}>
              Upload again
            </button>
            <button className="btn-ghost py-1 text-xs" onClick={() => setServerExpired(false)}>
              Dismiss
            </button>
          </div>
        )}
        {notice && (
          <div className="flex items-center gap-3 border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
            {notice}
            <button className="btn-ghost py-1 text-xs" onClick={() => setNotice(null)}>
              Dismiss
            </button>
          </div>
        )}

        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>

      {chatOpen && (
        <div className="fixed inset-0 z-[1100] flex flex-col bg-white lg:static lg:z-auto lg:w-96 lg:shrink-0 lg:border-l lg:border-slate-200">
          <ChatPanel onClose={() => setChatOpen(false)} />
        </div>
      )}
    </div>
  );
}
