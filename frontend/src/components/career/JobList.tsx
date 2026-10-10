import { Pin } from "lucide-react";
import { BAND_CLASSES, km, matchBand, pct } from "../../lib/format";
import type { JobNearby } from "../../types/api";

export interface RankedJob extends JobNearby {
  score: number;
}

interface Props {
  jobs: RankedJob[];
  selectedId: string | null;
  pinnedId: string | null;
  onSelect: (id: string) => void;
}

export default function JobList({ jobs, selectedId, pinnedId, onSelect }: Props) {
  if (jobs.length === 0) {
    return <p className="p-4 text-sm text-slate-500">No jobs match these filters. Widen the radius or lower the minimum match.</p>;
  }
  return (
    <ol className="divide-y divide-slate-100">
      {jobs.map((job, index) => {
        const band = matchBand(job.match_pct);
        const selected = job.id === selectedId;
        return (
          <li key={job.id}>
            <button
              type="button"
              onClick={() => onSelect(job.id)}
              aria-current={selected}
              className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-slate-50 ${
                selected ? "bg-brand-50" : ""
              }`}
            >
              <span className="w-5 shrink-0 text-xs text-slate-400">{index + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1 truncate font-medium text-slate-900">
                  {job.title}
                  {job.id === pinnedId && <Pin className="h-3 w-3 text-brand-600" aria-label="Pinned" />}
                </span>
                <span className="block truncate text-xs text-slate-500">
                  {job.company} · {km(job.distance_km)}
                  {job.missing.length > 0 ? ` · missing ${job.missing.length}` : " · nothing missing"}
                  {job.synthetic ? " · sample listing" : job.source_name ? ` · on ${job.source_name}` : ""}
                  {job.posted_at ? ` · ${job.posted_at}` : ""}
                </span>
              </span>
              <span className={`chip ${BAND_CLASSES[band]}`}>{pct(job.match_pct)}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
