// Final screen: readiness dial split verbal / non-verbal (70/30, stated), per-question breakdown,
// and the single thing to fix first.

import type { InterviewReport } from "../../types/profile";

export default function ReportView({ report, onRestart }: { report: InterviewReport; onRestart(): void }) {
  const hasVideo = report.non_verbal_score !== null;
  return (
    <section className="flex flex-col gap-6 rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
      <div className="flex flex-wrap items-center gap-8">
        <Dial value={report.readiness} />
        <div className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">Interview readiness · {report.role}</h2>
          <div className="flex gap-6">
            <Part label={`Verbal · ${Math.round(report.verbal_weight * 100)}%`} value={report.verbal_score} />
            <Part label={`Body language · ${Math.round(report.non_verbal_weight * 100)}%`} value={report.non_verbal_score} />
          </div>
          <p className="max-w-md text-xs text-slate-500 dark:text-slate-400">
            Readiness = {Math.round(report.verbal_weight * 100)}% verbal (STAR structure, length, fillers, relevance, pace) +{" "}
            {Math.round(report.non_verbal_weight * 100)}% body language.
            {!hasVideo && " The camera was off, so readiness is the verbal score."}
          </p>
        </div>
      </div>

      {report.fix_first && (
        <div className="rounded-lg border-l-4 border-indigo-500 bg-indigo-50 p-4 dark:bg-indigo-900/25">
          <div className="text-xs font-semibold text-indigo-700 uppercase dark:text-indigo-300">What to fix first</div>
          <p className="mt-1 text-sm">{report.fix_first}</p>
        </div>
      )}

      <table className="w-full text-sm tabular-nums">
        <thead className="text-left text-xs text-slate-500 dark:text-slate-400">
          <tr>
            <th className="pb-2 font-normal">Question</th>
            <th className="pb-2 text-right font-normal">Verbal</th>
            <th className="pb-2 text-right font-normal">Body</th>
            <th className="pb-2 text-right font-normal">Result</th>
          </tr>
        </thead>
        <tbody>
          {report.answers.map((a) => {
            const body = a.non_verbal?.body_language_score ?? null;
            const total = body === null ? a.verbal_score : report.verbal_weight * a.verbal_score + report.non_verbal_weight * body;
            return (
              <tr key={a.question.id} className="border-t border-slate-100 dark:border-slate-800">
                <td className="py-2 pr-4">{a.question.text}</td>
                <td className="py-2 text-right">{Math.round(a.verbal_score)}</td>
                <td className="py-2 text-right">{body === null ? "–" : Math.round(body)}</td>
                <td className="py-2 text-right font-semibold">{Math.round(total)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <button className="self-start rounded-lg bg-slate-900 px-4 py-2 font-medium text-white dark:bg-white dark:text-slate-900" onClick={onRestart}>
        Practise again
      </button>
    </section>
  );
}

function Dial({ value }: { value: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const tone = value >= 75 ? "stroke-emerald-500" : value >= 50 ? "stroke-amber-500" : "stroke-red-500";
  return (
    <svg viewBox="0 0 120 120" className="h-36 w-36" role="img" aria-label={`Readiness ${Math.round(value)} out of 100`}>
      <circle cx="60" cy="60" r={r} className="fill-none stroke-slate-200 dark:stroke-slate-700" strokeWidth="10" />
      <circle
        cx="60"
        cy="60"
        r={r}
        className={`fill-none ${tone}`}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - value / 100)}
        transform="rotate(-90 60 60)"
      />
      <text x="60" y="56" textAnchor="middle" className="fill-current text-[30px] font-semibold">
        {Math.round(value)}
      </text>
      <text x="60" y="78" textAnchor="middle" className="fill-slate-400 text-[11px]">
        out of 100
      </text>
    </svg>
  );
}

function Part({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value === null ? "–" : Math.round(value)}</div>
    </div>
  );
}
