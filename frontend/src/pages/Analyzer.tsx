// CV Analyzer: GitHub username + LinkedIn export (file or pasted text) -> POST /analyzer/run.
// Three-column evidence board (CV / LinkedIn / GitHub) with chips coloured by how many sources back them,
// anomaly cards grouped by rule, and the integrity score.
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { FileText, Github, Loader2, ShieldCheck, Target } from "lucide-react";
import AnomalyCard, { kindInfo } from "../components/analyzer/AnomalyCard";
import CVDropzone from "../components/CVDropzone";
import MatchMeter from "../components/career/MatchMeter";
import { api, ApiError, errorMessage } from "../lib/api";
import { roleImpact, unverifiedMatches } from "../lib/roleImpact";
import { hasCV, useProfileStore } from "../store/profile";
import { useSessionStore } from "../store/session";
import type { AnalyzerReport, SkillCluster, SkillSource } from "../types/api";
import type { Role } from "../types/profile";

const SOURCE_LABELS: Record<SkillSource, string> = { cv: "CV", linkedin: "LinkedIn", github: "GitHub" };
const SOURCE_ORDER: SkillSource[] = ["cv", "linkedin", "github"];
const STEPS = ["Fetching GitHub repos, languages and READMEs", "Extracting LinkedIn skills (LLM)", "Reconciling sources", "Applying the five anomaly rules"];

type ChipTone = "green" | "amber" | "blue";

/** Green: in every provided source. Amber: in exactly one. Blue: in some but not all. */
export function chipTone(cluster: SkillCluster, provided: number): ChipTone {
  const n = new Set(cluster.sources).size;
  if (provided > 1 && n >= provided) return "green";
  if (n <= 1) return "amber";
  return "blue";
}

const TONE_CLASSES: Record<ChipTone, string> = {
  green: "border-green-300 bg-green-50 text-green-800",
  amber: "border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100",
  blue: "border-blue-300 bg-blue-50 text-blue-800",
};

function anomalyFor(report: AnalyzerReport, cluster: SkillCluster) {
  const names = [cluster.name, ...cluster.members].map((n) => n.toLowerCase());
  return report.anomalies.find((a) => names.some((n) => a.claim.toLowerCase().includes(n)));
}

export default function Analyzer() {
  const profile = useProfileStore((s) => s.profile);
  const setProfile = useProfileStore((s) => s.setProfile);
  const merge = useProfileStore((s) => s.merge);
  const setServerExpired = useSessionStore((s) => s.setServerExpired);
  const [searchParams, setSearchParams] = useSearchParams();

  const [github, setGithub] = useState("");
  const [linkedinMode, setLinkedinMode] = useState<"file" | "text">("file");
  const [linkedinFile, setLinkedinFile] = useState<File | null>(null);
  const [linkedinText, setLinkedinText] = useState("");
  const [report, setReport] = useState<AnalyzerReport | null>(null);
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [cvBusy, setCvBusy] = useState(false);
  const [cvError, setCvError] = useState<string | null>(null);

  // A report from earlier in the session (the server keeps the latest one).
  useEffect(() => {
    if (!hasCV(profile)) return;
    api
      .analyzerReport()
      .then(setReport)
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    api.roles().then(setRoles).catch(() => setRoles([]));
  }, []);

  // Deep link from the Career Map: /analyzer?claim=SQL highlights that skill's anomaly.
  useEffect(() => {
    const claim = searchParams.get("claim");
    if (!claim || !report) return;
    const wanted = claim.trim().toLowerCase();
    const anomaly = report.anomalies.find((a) => a.claim.toLowerCase() === wanted) ?? report.anomalies.find((a) => a.claim.toLowerCase().includes(wanted));
    if (anomaly) {
      setHighlighted(anomaly.id);
      window.setTimeout(() => document.getElementById(`anomaly-${anomaly.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 50);
    }
    setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report, searchParams]);

  useEffect(() => {
    if (!running) return;
    setStep(0);
    const id = window.setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 2000);
    return () => window.clearInterval(id);
  }, [running]);

  async function run(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setRunning(true);
    try {
      const result = await api.runAnalyzer({
        github_username: github,
        linkedin_text: linkedinMode === "text" ? linkedinText : undefined,
        linkedin_export: linkedinMode === "file" ? linkedinFile : null,
      });
      setReport(result);
      setHighlighted(null);
      // The run also rewrote the shared profile (skills tagged with sources, refreshed gap): reload it whole.
      try {
        setProfile(await api.getProfile());
      } catch {
        merge({ anomalies: result.anomalies, integrity_score: result.integrity_score });
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setServerExpired(true);
      setError(errorMessage(err));
    } finally {
      setRunning(false);
    }
  }

  const provided = useMemo(() => SOURCE_ORDER.filter((s) => report && s in report.sources), [report]);
  const targetRole = useMemo(() => roles.find((r) => r.name === report?.target_role) ?? null, [roles, report]);
  const unverified = useMemo(() => unverifiedMatches(report?.match ?? null), [report]);
  const grouped = useMemo(() => {
    const groups = new Map<string, AnalyzerReport["anomalies"]>();
    for (const anomaly of report?.anomalies ?? []) {
      const group = kindInfo(anomaly.kind).group;
      groups.set(group, [...(groups.get(group) ?? []), anomaly]);
    }
    return [...groups.entries()];
  }, [report]);

  function focusAnomaly(cluster: SkillCluster) {
    if (!report) return;
    const anomaly = anomalyFor(report, cluster);
    if (!anomaly) return;
    setHighlighted(anomaly.id);
    document.getElementById(`anomaly-${anomaly.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // The Analyzer works on its own: a CV can be read here, with no target role or location.
  async function readCV(event: FormEvent) {
    event.preventDefault();
    if (!cvFile) return;
    setCvError(null);
    setCvBusy(true);
    try {
      setProfile(await api.uploadCV(cvFile));
      setServerExpired(false);
      setReport(null);
    } catch (err) {
      const message = err instanceof ApiError && err.status === 422 ? `Could not read the CV: ${err.detail}` : errorMessage(err);
      setCvError(message);
    } finally {
      setCvBusy(false);
    }
  }

  if (!hasCV(profile)) {
    return (
      <div className="mx-auto max-w-xl px-4 py-12">
        <h1 className="text-2xl font-bold">CV Analyzer</h1>
        <p className="mt-2 text-slate-600">
          Read your CV here, then check its claims against your GitHub and LinkedIn. No target role or location is needed;
          the Career Map can use the same CV later.
        </p>
        <form onSubmit={readCV} className="card mt-6 space-y-4 p-5" aria-label="Read a CV">
          <CVDropzone file={cvFile} onFile={setCvFile} disabled={cvBusy} />
          {cvError && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{cvError}</p>}
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" className="btn-primary" disabled={!cvFile || cvBusy}>
              {cvBusy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <FileText className="h-4 w-4" aria-hidden />}
              {cvBusy ? "Reading your CV…" : "Read my CV"}
            </button>
            <Link to="/upload" className="text-xs text-slate-500 underline">
              or upload with a target role and location
            </Link>
          </div>
        </form>
      </div>
    );
  }

  const canRun = !!github.trim() || (linkedinMode === "file" ? !!linkedinFile : !!linkedinText.trim());

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">CV Analyzer</h1>
          <p className="mt-1 text-slate-600">
            Claims on your CV that GitHub or LinkedIn do not back up, strengths your CV misses, and a fix for each.
          </p>
        </div>
        <Link to="/upload" className="btn-secondary text-xs">
          Upload a different CV
        </Link>
      </div>

      <form onSubmit={run} className="card mt-6 grid gap-5 p-5 md:grid-cols-2">
        <div>
          <label className="label" htmlFor="github">
            GitHub username
          </label>
          <div className="relative">
            <Github className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden />
            <input
              id="github"
              className="input pl-9"
              placeholder="your-username"
              value={github}
              onChange={(e) => setGithub(e.target.value)}
              disabled={running}
              autoComplete="off"
            />
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Official REST API only: repos, languages, READMEs, commit counts. Your own account only.
          </p>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <p className="label">LinkedIn</p>
            <div className="flex gap-1 rounded-md bg-slate-100 p-0.5 text-xs">
              {(["file", "text"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setLinkedinMode(m)}
                  className={`rounded px-2 py-0.5 ${linkedinMode === m ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"}`}
                >
                  {m === "file" ? "Export file" : "Paste text"}
                </button>
              ))}
            </div>
          </div>
          {linkedinMode === "file" ? (
            <CVDropzone
              file={linkedinFile}
              onFile={setLinkedinFile}
              accept={[".pdf", ".txt"]}
              disabled={running}
              label="Drop your LinkedIn 'Download your data' export (PDF or TXT)"
            />
          ) : (
            <textarea
              className="input min-h-[120px]"
              placeholder="Paste your LinkedIn profile text (skills, experience, projects)…"
              value={linkedinText}
              onChange={(e) => setLinkedinText(e.target.value)}
              disabled={running}
            />
          )}
          <p className="mt-1 text-xs text-slate-500">Never scraped: LinkedIn's terms prohibit it. Use your own export.</p>
        </div>

        <div className="md:col-span-2 flex flex-wrap items-center gap-3">
          <button type="submit" className="btn-primary" disabled={!canRun || running}>
            {running ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <ShieldCheck className="h-4 w-4" aria-hidden />}
            {running ? STEPS[step] : "Run the evidence check"}
          </button>
          {!canRun && <span className="text-xs text-slate-500">Give a GitHub username, a LinkedIn export, or both.</span>}
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </form>

      {report && (
        <>
          <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_220px]">
            <div className="card p-4">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-sm font-semibold">Evidence board</h2>
                <span className="text-xs text-slate-500">
                  <span className="chip border-green-300 bg-green-50 text-green-800">green</span> in every source ·{" "}
                  <span className="chip border-blue-300 bg-blue-50 text-blue-800">blue</span> in some ·{" "}
                  <span className="chip border-amber-300 bg-amber-50 text-amber-900">amber</span> in one only (click for the fix)
                </span>
              </div>
              <div className={`mt-4 grid gap-4 ${provided.length === 3 ? "md:grid-cols-3" : provided.length === 2 ? "md:grid-cols-2" : ""}`}>
                {provided.map((source) => (
                  <div key={source} className="rounded-lg border border-slate-200 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {SOURCE_LABELS[source]} <span className="font-normal normal-case">· {report.sources[source]} skills</span>
                    </p>
                    <ul className="mt-2 flex flex-wrap gap-1.5">
                      {report.clusters
                        .filter((c) => c.sources.includes(source))
                        .map((cluster) => {
                          const tone = chipTone(cluster, provided.length);
                          const linked = tone !== "green" && !!anomalyFor(report, cluster);
                          return (
                            <li key={cluster.name}>
                              <button
                                type="button"
                                className={`chip ${TONE_CLASSES[tone]} ${linked ? "cursor-pointer" : "cursor-default"}`}
                                title={`Sources: ${cluster.sources.map((s) => SOURCE_LABELS[s]).join(", ")} · ${cluster.mention_count} mention${
                                  cluster.mention_count === 1 ? "" : "s"
                                }`}
                                onClick={() => linked && focusAnomaly(cluster)}
                              >
                                {cluster.name}
                              </button>
                            </li>
                          );
                        })}
                    </ul>
                  </div>
                ))}
              </div>
            </div>

            <div className="card flex flex-col items-center justify-center p-4">
              {report.integrity_score === null ? (
                <p className="text-center text-sm text-slate-500">Integrity needs at least one external source.</p>
              ) : (
                <MatchMeter value={report.integrity_score} label="CV integrity" size={150} />
              )}
              <p className="mt-2 text-center text-xs text-slate-500">
                Share of CV claims with at least one external evidence source.
              </p>
            </div>
          </div>

          {report.match && report.target_role && (
            <div className="card mt-4 flex flex-wrap items-center gap-4 border-brand-200 bg-brand-50 p-4" data-testid="role-impact-card">
              <Target className="h-6 w-6 shrink-0 text-brand-700" aria-hidden />
              <p className="flex-1 text-sm text-brand-900">
                <strong>{report.target_role}</strong> match is now <strong>{report.match.match_pct.toFixed(0)}%</strong>
                {report.match.evidenced_pct !== null && (
                  <>
                    , of which <strong>{report.match.evidenced_pct.toFixed(0)}%</strong> is backed by {provided.filter((s) => s !== "cv").map((s) => SOURCE_LABELS[s]).join(" and ")}
                  </>
                )}
                .
                {unverified.length > 0 && (
                  <span className="text-brand-800">
                    {" "}
                    Counted on the CV's word alone: {unverified.map((m) => m.matched_to).join(", ")}.
                  </span>
                )}
                {unverified.length === 0 && report.match.matched.length > 0 && (
                  <span className="text-brand-800"> Every matched skill has external evidence.</span>
                )}
              </p>
              <Link to="/career" className="btn-primary text-xs">
                Open the Career Map
              </Link>
            </div>
          )}

          <div className="mt-6">
            <h2 className="text-sm font-semibold">
              Anomalies ({report.anomalies.length})
              {report.github_username && <span className="ml-2 font-normal text-slate-500">GitHub: {report.github_username}</span>}
            </h2>
            {report.anomalies.length === 0 ? (
              <p className="card mt-3 p-4 text-sm text-slate-600">Every CV claim is backed by at least one source. Nothing to fix.</p>
            ) : (
              <div className="mt-3 space-y-5">
                {grouped.map(([group, items]) => (
                  <div key={group}>
                    <p className="label">{group}</p>
                    <div className="grid gap-3 md:grid-cols-2">
                      {items.map((anomaly) => (
                        <AnomalyCard
                          key={anomaly.id}
                          anomaly={anomaly}
                          domId={`anomaly-${anomaly.id}`}
                          highlighted={highlighted === anomaly.id}
                          impact={roleImpact(anomaly, targetRole, report.match)}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
