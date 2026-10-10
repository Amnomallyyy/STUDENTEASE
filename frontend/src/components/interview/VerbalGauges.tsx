// Right-zone speaking gauges: fillers, words, time and pace. Live while the user answers (fillers come
// from Whisper clips, as the browser's own recognition drops "um"/"uh"); the scored values afterwards.

interface Props {
  words: number;
  fillers: number;
  elapsedS: number;
  /** false for typed answers: no time or pace. */
  spoken: boolean;
  /** true once the backend has scored the answer (numbers come from the final Whisper transcript). */
  scored?: boolean;
}

export default function VerbalGauges({ words, fillers, elapsedS, spoken, scored = false }: Props) {
  const per100 = words ? (100 * fillers) / words : 0;
  const wpm = spoken && elapsedS >= 5 ? Math.round((words / elapsedS) * 60) : null;
  const paceTone = wpm === null ? "" : wpm < 120 || wpm > 160 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400";
  const fillerTone = per100 > 2 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400";
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      <h3 className="mb-3 text-sm font-semibold">Speaking · {scored ? "scored" : "live"}</h3>
      <dl className="grid grid-cols-2 gap-3 text-xs">
        <Stat label="Filler words" value={`${fillers}`} sub={words ? `${per100.toFixed(1)} / 100 words` : ""} tone={words ? fillerTone : ""} />
        <Stat label="Words" value={`${words}`} sub="target 150–300" />
        {spoken && <Stat label="Time" value={formatTime(elapsedS)} sub="target 1:30–3:00" />}
        {spoken && <Stat label="Pace" value={wpm === null ? "–" : `${wpm}`} sub="words/min · 120–160" tone={paceTone} />}
      </dl>
    </section>
  );
}

function Stat({ label, value, sub, tone = "" }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div>
      <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className={`text-xl font-semibold tabular-nums ${tone}`}>{value}</dd>
      {sub && <dd className="text-[11px] text-slate-400">{sub}</dd>}
    </div>
  );
}

function formatTime(s: number): string {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}
