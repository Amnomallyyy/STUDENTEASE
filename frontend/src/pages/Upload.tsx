// Upload screen: CV dropzone, target role, mode, location. POST /profile/cv then straight to the Career Map.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import CVDropzone from "../components/CVDropzone";
import LocationPicker from "../components/LocationPicker";
import ProgressSteps from "../components/ProgressSteps";
import { api, ApiError, errorMessage } from "../lib/api";
import { useProfileStore } from "../store/profile";
import { useSessionStore } from "../store/session";
import type { Location, Role, UserMode } from "../types/profile";

const STEPS = ["Reading your CV", "Extracting skills, projects and experience (LLM)", "Matching the target role", "Finding nearby jobs"];

export default function Upload() {
  const navigate = useNavigate();
  const existing = useProfileStore((s) => s.profile);
  const setProfile = useProfileStore((s) => s.setProfile);
  const setRole = useSessionStore((s) => s.setRole);
  const setServerExpired = useSessionStore((s) => s.setServerExpired);
  const resetProgress = useSessionStore((s) => s.resetProgress);

  const [file, setFile] = useState<File | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [rolesError, setRolesError] = useState<string | null>(null);
  const [role, setRoleName] = useState(existing?.target_role ?? "Data Analyst");
  const [mode, setMode] = useState<UserMode>(existing?.mode ?? "student");
  const [location, setLocation] = useState<Location | null>(existing?.location ?? null);
  const [step, setStep] = useState(-1);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    api
      .roles()
      .then((list) => {
        setRoles(list);
        if (list.length && !list.some((r) => r.name === role)) setRoleName(list[0].name);
      })
      .catch((err) => setRolesError(errorMessage(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => () => {
    if (timer.current) window.clearInterval(timer.current);
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setError(null);
    setStep(0);
    // One request does all four stages; advance the indicator on a timer so the wait is legible.
    timer.current = window.setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 2500);
    try {
      const profile = await api.uploadCV(file, {
        target_role: role || null,
        mode,
        lat: location?.lat ?? null,
        lng: location?.lng ?? null,
        city: location?.city ?? "",
      });
      setProfile(profile);
      setRole(profile.target_role);
      setServerExpired(false);
      resetProgress();
      setStep(STEPS.length);
      navigate(profile.target_role ? "/career" : "/dashboard");
    } catch (err) {
      const message = err instanceof ApiError && err.status === 422 ? `Could not read the CV: ${err.detail}` : errorMessage(err);
      setError(message);
    } finally {
      if (timer.current) window.clearInterval(timer.current);
      timer.current = null;
    }
  }

  const busy = step >= 0 && step < STEPS.length && !error;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-2xl font-bold tracking-tight">Upload your CV</h1>
      <p className="mt-1 text-slate-600">
        In two minutes, know exactly what to fix, where to apply, and how to answer. One upload feeds every module.
      </p>

      <form onSubmit={submit} className="mt-6 grid gap-6 md:grid-cols-[1fr_280px]">
        <div className="space-y-5">
          <CVDropzone file={file} onFile={setFile} disabled={busy} />

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="role">
                Target role
              </label>
              {roles.length > 0 ? (
                <select id="role" className="input" value={role} onChange={(e) => setRoleName(e.target.value)} disabled={busy}>
                  {roles.map((r) => (
                    <option key={r.id} value={r.name}>
                      {r.name}
                    </option>
                  ))}
                </select>
              ) : (
                <input id="role" className="input" value={role} onChange={(e) => setRoleName(e.target.value)} disabled={busy} />
              )}
              {rolesError && <p className="mt-1 text-xs text-amber-700">Role list unavailable ({rolesError}); type a role name.</p>}
            </div>
            <div>
              <p className="label">I am a</p>
              <div className="flex gap-1 rounded-lg bg-slate-100 p-1" role="radiogroup" aria-label="Mode">
                {(["student", "job_seeker"] as UserMode[]).map((m) => (
                  <button
                    key={m}
                    type="button"
                    role="radio"
                    aria-checked={mode === m}
                    disabled={busy}
                    onClick={() => setMode(m)}
                    className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium ${
                      mode === m ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"
                    }`}
                  >
                    {m === "student" ? "Student" : "Job seeker"}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <p className="label">Location (for nearby jobs)</p>
            <LocationPicker value={location} onChange={setLocation} />
          </div>

          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

          <button type="submit" className="btn-primary w-full sm:w-auto" disabled={!file || busy}>
            {busy ? "Analysing…" : "Analyse my CV"}
          </button>
        </div>

        <aside className="space-y-4">
          <div className="card p-4">
            <p className="text-sm font-semibold">What happens</p>
            <div className="mt-3">
              <ProgressSteps steps={STEPS} current={step} error={error} />
            </div>
          </div>
          <div className="card flex gap-3 p-4 text-xs text-slate-600">
            <ShieldCheck className="h-5 w-5 shrink-0 text-green-600" aria-hidden />
            <p>
              Only your own data, only with your action. Email, phone, address, date of birth and photo are stripped
              before any AI call; only skills, projects and experience leave the browser. No account, no database:
              "Delete my data" clears everything.
            </p>
          </div>
        </aside>
      </form>
    </div>
  );
}
