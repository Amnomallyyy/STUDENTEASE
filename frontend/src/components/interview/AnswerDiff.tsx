// The user's answer and the STAR rewrite side by side. Bracketed parts of the rewrite are prompts
// for what the user still needs to add (never invented facts), so they are highlighted.

import { HighlightFillers } from "./LiveTranscript";

export default function AnswerDiff({ original, rewritten }: { original: string; rewritten: string }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
        <h4 className="mb-1.5 text-xs font-semibold text-slate-500 uppercase dark:text-slate-400">Your answer</h4>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          <HighlightFillers text={original} />
        </p>
      </div>
      <div className="rounded-lg bg-emerald-50 p-3 dark:bg-emerald-900/25">
        <h4 className="mb-1.5 text-xs font-semibold text-emerald-700 uppercase dark:text-emerald-300">Stronger STAR version</h4>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {rewritten.split(/(\[[^\]]+\])/).map((part, i) =>
            part.startsWith("[") ? (
              <span key={i} className="rounded bg-amber-100 px-1 text-amber-900 dark:bg-amber-500/30 dark:text-amber-100">
                {part}
              </span>
            ) : (
              part
            ),
          )}
        </p>
      </div>
    </div>
  );
}
