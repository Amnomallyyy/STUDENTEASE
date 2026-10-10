// Feedback for one answer: scores, the transcript with the STAR quotes the model found, what to fix
// in the content, body-language coaching notes, and the rewritten answer.

import { STAR_KEYS, type StarKey } from "../../lib/starCues";
import type { AnswerResult } from "../../types/profile";
import AnswerDiff from "./AnswerDiff";

const STAR_COLORS: Record<StarKey, string> = {
  situation: "bg-sky-100 text-sky-950 dark:bg-sky-500/30 dark:text-sky-50",
  task: "bg-violet-100 text-violet-950 dark:bg-violet-500/30 dark:text-violet-50",
  action: "bg-emerald-100 text-emerald-950 dark:bg-emerald-500/30 dark:text-emerald-50",
  result: "bg-amber-100 text-amber-950 dark:bg-amber-500/30 dark:text-amber-50",
};

const COMPONENTS: [string, string, number][] = [
  ["star", "STAR structure", 40],
  ["conciseness", "Length", 20],
  ["fillers", "Few fillers", 15],
  ["relevance", "On the question", 15],
  ["pace", "Pace", 10],
];

export default function AnswerFeedback({ result }: { result: AnswerResult }) {
  const v = result.verbal;
  const nv = result.non_verbal;
  const readiness = nv ? 0.7 * result.verbal_score + 0.3 * nv.body_language_score : result.verbal_score;
  return (
    <section className="flex flex-col gap-5 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
      <div className="flex flex-wrap items-end gap-6">
        <Score label="This answer" value={readiness} big />
        <Score label="Verbal · 70%" value={result.verbal_score} />
        <Score label="Body language · 30%" value={nv ? nv.body_language_score : null} />
        {v.star.source === "rules" && (
          <span className="ml-auto rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500 dark:bg-slate-800">
            Offline scoring (AI unavailable)
          </span>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_260px]">
        <div>
          <h4 className="mb-1.5 text-xs font-semibold text-slate-500 uppercase dark:text-slate-400">What the model found in your answer</h4>
          <p className="text-sm leading-relaxed">
            <StarHighlights result={result} />
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
            {STAR_KEYS.map((k) => (
              <span key={k} className={`rounded px-1.5 py-0.5 capitalize ${STAR_COLORS[k]} ${v.star[k].present ? "" : "line-through opacity-50"}`}>
                {k}
              </span>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-2 text-xs">
          {COMPONENTS.filter(([k]) => k in v.component_scores).map(([k, label, weight]) => (
            <Bar key={k} label={`${label} · ${weight}%`} value={v.component_scores[k]} />
          ))}
          <p className="mt-1 text-[11px] text-slate-400">
            {v.word_count} words{v.duration_s ? ` · ${Math.round(v.duration_s)} s · ${Math.round(v.wpm)} wpm` : ""} ·{" "}
            {v.fillers_per_100_words} fillers / 100 words
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {result.content_feedback.length > 0 && (
          <Notes title="Fix in your answer" items={result.content_feedback} tone="amber" />
        )}
        {result.coaching_notes.length > 0 && <Notes title="Body language" items={result.coaching_notes} tone="sky" />}
      </div>

      {result.rewritten_answer && <AnswerDiff original={result.transcript} rewritten={result.rewritten_answer} />}
    </section>
  );
}

function StarHighlights({ result }: { result: AnswerResult }) {
  const text = result.transcript;
  const spans = STAR_KEYS.map((k) => ({ k, s: result.verbal.star[k] }))
    .filter(({ s }) => s.present && s.evidence_span)
    .map(({ k, s }) => ({ k, start: text.indexOf(s.evidence_span), len: s.evidence_span.length }))
    .filter((x) => x.start >= 0)
    .sort((a, b) => a.start - b.start);
  const out: React.ReactNode[] = [];
  let pos = 0;
  for (const { k, start, len } of spans) {
    if (start < pos) continue;
    out.push(text.slice(pos, start));
    out.push(
      <mark key={k} className={`rounded px-0.5 ${STAR_COLORS[k]}`} title={k}>
        {text.slice(start, start + len)}
      </mark>,
    );
    pos = start + len;
  }
  out.push(text.slice(pos));
  return <>{out}</>;
}

function Score({ label, value, big = false }: { label: string; value: number | null; big?: boolean }) {
  return (
    <div>
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`font-semibold tabular-nums ${big ? "text-4xl" : "text-2xl"}`}>
        {value === null ? "–" : Math.round(value)}
        {value !== null && <span className="text-sm font-normal text-slate-400">/100</span>}
      </div>
    </div>
  );
}

function Bar({ label, value }: { label: string; value: number }) {
  const tone = value >= 75 ? "bg-emerald-500" : value >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div>
      <div className="flex justify-between">
        <span className="text-slate-500 dark:text-slate-400">{label}</span>
        <span className="font-medium tabular-nums">{Math.round(value)}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function Notes({ title, items, tone }: { title: string; items: string[]; tone: "amber" | "sky" }) {
  const box = tone === "amber" ? "bg-amber-50 dark:bg-amber-900/20" : "bg-sky-50 dark:bg-sky-900/20";
  return (
    <div className={`rounded-lg p-3 ${box}`}>
      <h4 className="mb-1.5 text-xs font-semibold uppercase">{title}</h4>
      <ul className="flex list-disc flex-col gap-1 pl-4 text-sm">
        {items.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </div>
  );
}
