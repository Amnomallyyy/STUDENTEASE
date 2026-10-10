import { ExternalLink, Loader2, Pin, PinOff, RefreshCw } from "lucide-react";
import { taskKey, useSessionStore } from "../../store/session";
import type { JobNearby } from "../../types/api";
import type { Roadmap } from "../../types/profile";

interface Props {
  roadmap: Roadmap | null;
  role: string | null;
  loading: boolean;
  error: string | null;
  pinnedJob: JobNearby | null;
  onRegenerate: () => void;
  onUnpin: () => void;
}

/** 4-week plan with tick-off progress stored in the browser; re-prioritised when a job is pinned. */
export default function RoadmapTimeline({ roadmap, role, loading, error, pinnedJob, onRegenerate, onUnpin }: Props) {
  const done = useSessionStore((s) => s.roadmapDone);
  const toggleTask = useSessionStore((s) => s.toggleTask);
  const resetProgress = useSessionStore((s) => s.resetProgress);

  const tasks = roadmap?.weeks.flatMap((w) => w.tasks.map((t) => taskKey(role, w.week, t.title))) ?? [];
  const completed = tasks.filter((k) => done[k]).length;
  const progress = tasks.length ? Math.round((100 * completed) / tasks.length) : 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">4-week roadmap</h2>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-brand-600" aria-label="Loading" />}
        <button className="btn-ghost ml-auto p-1 text-xs" onClick={onRegenerate} title="Regenerate the plan" disabled={loading}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      {pinnedJob && (
        <div className="mt-2 flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs text-brand-800">
          <Pin className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="min-w-0 flex-1 truncate">
            Prioritised for <strong>{pinnedJob.title}</strong> at {pinnedJob.company}
          </span>
          <button className="btn-ghost p-0.5" onClick={onUnpin} title="Unpin" aria-label="Unpin job">
            <PinOff className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      )}

      {tasks.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>
              {completed} of {tasks.length} tasks done
            </span>
            <button className="hover:text-slate-700" onClick={resetProgress}>
              reset
            </button>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-green-500 transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {!loading && roadmap && roadmap.weeks.length === 0 && (
        <p className="mt-3 text-sm text-slate-500">No missing skills for this role within the radius, so there is nothing to plan.</p>
      )}
      {!roadmap && !loading && !error && <p className="mt-3 text-sm text-slate-500">Pick a target role to generate a plan.</p>}

      <ol className="scroll-thin mt-3 flex-1 space-y-4 overflow-y-auto pr-1">
        {roadmap?.weeks.map((week) => (
          <li key={week.week} className="relative pl-5">
            <span className="absolute left-0 top-1 h-3 w-3 rounded-full border-2 border-brand-500 bg-white" aria-hidden />
            <span className="absolute left-[5px] top-4 h-[calc(100%-0.5rem)] w-px bg-slate-200" aria-hidden />
            <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">Week {week.week}</p>
            <p className="text-sm font-medium text-slate-900">{week.focus}</p>
            <ul className="mt-1.5 space-y-1.5">
              {week.tasks.map((task) => {
                const key = taskKey(role, week.week, task.title);
                const checked = !!done[key];
                return (
                  <li key={key} className="flex items-start gap-2 text-sm">
                    <input
                      id={key}
                      type="checkbox"
                      className="mt-1 h-4 w-4 accent-green-600"
                      checked={checked}
                      onChange={() => toggleTask(key)}
                    />
                    <label htmlFor={key} className={`flex-1 cursor-pointer ${checked ? "text-slate-400 line-through" : "text-slate-700"}`}>
                      {task.title}
                      <span className="ml-1 text-xs text-slate-400">
                        · {task.skill} · {task.hours} h
                      </span>
                      {task.resource_url && (
                        <a
                          href={task.resource_url}
                          target="_blank"
                          rel="noreferrer"
                          className="ml-1 inline-flex items-center gap-0.5 text-xs text-brand-600 hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          resource <ExternalLink className="h-3 w-3" aria-hidden />
                        </a>
                      )}
                    </label>
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[11px] text-slate-400">Resources come from a whitelist of free sources; progress is saved in this browser only.</p>
    </div>
  );
}
