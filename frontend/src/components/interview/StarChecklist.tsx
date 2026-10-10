// STAR checklist: ticks on live as cue phrases are heard; after scoring it shows the backend's
// result with a 0-3 strength per element.

import { STAR_KEYS, type StarKey } from "../../lib/starCues";
import type { StarScore } from "../../types/profile";

const LABEL: Record<StarKey, [string, string]> = {
  situation: ["Situation", "Where and when"],
  task: ["Task", "What you had to do"],
  action: ["Action", "What you did"],
  result: ["Result", "What changed, with a number"],
};

interface Props {
  live: Record<StarKey, boolean>;
  /** Scored result for the last answer; replaces the live ticks when present. */
  scored?: StarScore | null;
}

export default function StarChecklist({ live, scored }: Props) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      <h3 className="mb-3 text-sm font-semibold">STAR structure {scored ? "· scored" : "· live"}</h3>
      <ul className="flex flex-col gap-2">
        {STAR_KEYS.map((k) => {
          const el = scored?.[k];
          const done = el ? el.present : live[k];
          return (
            <li key={k} className="flex items-center gap-2.5 text-sm">
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  done ? "bg-emerald-500 text-white" : "border border-slate-300 text-transparent dark:border-slate-600"
                }`}
                aria-hidden="true"
              >
                ✓
              </span>
              <span className="flex-1">
                <span className="font-medium">{LABEL[k][0]}</span>{" "}
                <span className="text-xs text-slate-500 dark:text-slate-400">{LABEL[k][1]}</span>
              </span>
              {el && <Strength value={el.strength} />}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Strength({ value }: { value: number }) {
  return (
    <span className="flex gap-0.5" title={`Strength ${value} of 3`} aria-label={`Strength ${value} of 3`}>
      {[1, 2, 3].map((i) => (
        <span key={i} className={`h-2 w-3 rounded-sm ${i <= value ? "bg-emerald-500" : "bg-slate-200 dark:bg-slate-700"}`} />
      ))}
    </span>
  );
}
