import { useEffect, useState } from "react";
import { Check, ExternalLink, Pin, PinOff, X } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { BAND_CLASSES, km, matchBand, pct } from "../../lib/format";
import type { JobNearby } from "../../types/api";
import type { Job } from "../../types/profile";

interface Props {
  job: JobNearby;
  pinned: boolean;
  onPin: () => void;
  onUnpin: () => void;
  onClose: () => void;
}

type Status = "have" | "missing" | "partial";

/** A job's requirements with ticks and crosses, and "Prepare me for this job" (pins it for the roadmap). */
export default function JobDetail({ job, pinned, onPin, onUnpin, onClose }: Props) {
  const [full, setFull] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setFull(null);
    setError(null);
    api
      .job(job.id)
      .then((j) => !cancelled && setFull(j))
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [job.id]);

  const matched = new Set(job.matched.map((s) => s.toLowerCase()));
  const missing = new Set(job.missing.map((s) => s.toLowerCase()));
  const statusOf = (name: string): Status =>
    matched.has(name.toLowerCase()) ? "have" : missing.has(name.toLowerCase()) ? "missing" : "partial";

  const requirements = full?.required_skills ?? [
    ...job.matched.map((name) => ({ name, weight: 1 })),
    ...job.missing.map((name) => ({ name, weight: 1 })),
  ];

  return (
    <div className="card p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-slate-900">{job.title}</h3>
          <p className="text-sm text-slate-600">
            {job.company} · {job.city} · {km(job.distance_km)} away
          </p>
        </div>
        <span className={`chip ${BAND_CLASSES[matchBand(job.match_pct)]}`}>{pct(job.match_pct)} match</span>
        <button className="btn-ghost p-1" onClick={onClose} aria-label="Close job details">
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {full?.requirements_text && <p className="mt-3 text-sm leading-relaxed text-slate-700">{full.requirements_text}</p>}
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <p className="label mt-4">Requirements</p>
      <ul className="grid gap-1 sm:grid-cols-2">
        {requirements.map((skill) => {
          const status = statusOf(skill.name);
          return (
            <li key={skill.name} className="flex items-center gap-2 text-sm">
              {status === "have" ? (
                <Check className="h-4 w-4 shrink-0 text-green-600" aria-label="You have this" />
              ) : status === "missing" ? (
                <X className="h-4 w-4 shrink-0 text-red-600" aria-label="Missing" />
              ) : (
                <span className="w-4 shrink-0 text-center text-amber-600" aria-label="Partial match">
                  ~
                </span>
              )}
              <span className={status === "missing" ? "font-medium text-red-800" : "text-slate-700"}>{skill.name}</span>
              {"weight" in skill && skill.weight >= 2 && (
                <span className="text-[10px] uppercase text-slate-400">core</span>
              )}
            </li>
          );
        })}
      </ul>

      {job.missing.length > 0 && (
        <p className="mt-3 text-sm text-slate-700">
          <span className="font-medium">Exactly what is missing:</span> {job.missing.join(", ")}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {pinned ? (
          <button className="btn-secondary" onClick={onUnpin}>
            <PinOff className="h-4 w-4" aria-hidden /> Unpin from roadmap
          </button>
        ) : (
          <button className="btn-primary" onClick={onPin}>
            <Pin className="h-4 w-4" aria-hidden /> Prepare me for this job
          </button>
        )}
        {job.source_url && (
          <a className="btn-ghost text-xs" href={job.source_url} target="_blank" rel="noreferrer">
            <ExternalLink className="h-3 w-3" aria-hidden /> Source
          </a>
        )}
        {job.synthetic && (
          <span className="text-xs text-slate-400" title="Labelled synthetic listing from data/jobs.json">
            Synthetic listing
          </span>
        )}
      </div>
    </div>
  );
}
