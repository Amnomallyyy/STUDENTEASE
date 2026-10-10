// Right-zone body-language gauges: eye-contact ring, posture indicator, fidget bar, expression and,
// once an answer is recording, the running body-language score with its weights.

import type { AnswerAnalysis } from "../../vision/aggregate";
import { WEIGHTS } from "../../vision/thresholds";
import { DISTRACTING_ACTIONS, type ExpressionLabel, type GazeState, type HandAction, type LiveVisionState, type PostureFlag } from "../../vision/types";

interface Props {
  live: LiveVisionState;
  answer: AnswerAnalysis | null;
  recording: boolean;
}

const POSTURE_TEXT: Record<PostureFlag, string> = {
  slouching: "Slouching",
  leaning_out_of_frame: "Leaving the frame",
  shoulders_tilted: "Shoulders tilted",
};

const EXPRESSION_TEXT: Record<ExpressionLabel, string> = { engaged: "Engaged", neutral: "Neutral", tense: "Tense" };

export const HAND_ACTION_TEXT: Record<HandAction, string> = {
  covering_mouth: "Covering mouth",
  touching_face: "Touching face",
  touching_head: "Touching hair / head",
  fiddling: "Fiddling with fingers",
  restless: "Restless hands",
  fist: "Clenched fist",
  gesturing: "Open-hand gestures",
  resting: "Resting",
};

const GAZE_TEXT: Record<GazeState, string> = { contact: " · on screen", head_away: " · head turned", eyes_away: " · eyes away" };

const WEIGHT_ROWS = [
  ["Eye contact", WEIGHTS.eyeContact, "eyeContact"],
  ["Posture", WEIGHTS.posture, "posture"],
  ["Hands (no distracting habits)", WEIGHTS.fidget, "fidget"],
  ["Head stability", WEIGHTS.stability, "stability"],
  ["Expression", WEIGHTS.expression, "expression"],
] as const;

export default function NonVerbalGauges({ live, answer, recording }: Props) {
  return (
    <section className="flex flex-col gap-4 card p-4 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
      <h3 className="text-sm font-semibold">Body language</h3>

      <div className="flex items-center gap-4">
        <EyeContactRing pct={live.eyeContactRecentPct} now={live.gazeNow} />
        <div className="flex flex-1 flex-col gap-3">
          <PostureIndicator issue={live.postureIssue} known={live.eyeContactRecentPct !== null} />
          <HandActionRow action={live.handAction} hands={live.handsInView} />
          <FidgetBar pct={live.fidgetRecentPct} />
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500 dark:text-slate-400">Expression</span>
            <span className="font-medium">{live.expression ? EXPRESSION_TEXT[live.expression] : "–"}</span>
          </div>
        </div>
      </div>

      {answer && (
        <div className="border-t border-slate-200 pt-3 dark:border-slate-700">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {recording ? "This answer so far" : "Last answer"}
            </span>
            <span className="text-2xl font-semibold tabular-nums">
              {Math.round(answer.metrics.body_language_score)}
              <span className="text-sm font-normal text-slate-400">/100</span>
            </span>
          </div>
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer text-slate-500 dark:text-slate-400">How this score is weighted</summary>
            <HandActionSummary actions={answer.metrics.hand_actions} />
            <table className="mt-2 w-full tabular-nums">
              <tbody>
                {WEIGHT_ROWS.map(([label, weight, key]) => (
                  <tr key={key}>
                    <td className="py-0.5">{label}</td>
                    <td className="py-0.5 text-right text-slate-500">{Math.round(weight * 100)}%</td>
                    <td className="py-0.5 text-right font-medium">{Math.round(answer.subScores[key])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-slate-500 dark:text-slate-400">
              Measured from head and eye direction, face, shoulder and hand landmarks only. No emotion or identity is inferred.
              Body language is 30% of the readiness score.
            </p>
          </details>
        </div>
      )}
    </section>
  );
}

function EyeContactRing({ pct, now }: { pct: number | null; now: GazeState | null }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  const value = pct ?? 0;
  const color = pct === null ? "stroke-slate-300" : value >= 70 ? "stroke-emerald-500" : value >= 40 ? "stroke-amber-500" : "stroke-red-500";
  return (
    <div className="flex flex-col items-center gap-1">
      <svg viewBox="0 0 80 80" className="h-24 w-24 -rotate-90" role="img" aria-label={`Eye contact ${pct ?? "unknown"} percent`}>
        <circle cx="40" cy="40" r={r} className="fill-none stroke-slate-200 dark:stroke-slate-700" strokeWidth="8" />
        <circle
          cx="40"
          cy="40"
          r={r}
          className={`fill-none ${color} transition-[stroke-dashoffset] duration-500`}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - value / 100)}
        />
        <text x="40" y="40" className="fill-current text-[18px] font-semibold" textAnchor="middle" dominantBaseline="central" transform="rotate(90 40 40)">
          {pct === null ? "–" : `${pct}%`}
        </text>
      </svg>
      <span className="text-xs text-slate-500 dark:text-slate-400">
        Eye contact{now === null ? "" : GAZE_TEXT[now]}
      </span>
    </div>
  );
}

function PostureIndicator({ issue, known }: { issue: PostureFlag | null; known: boolean }) {
  const ok = known && !issue;
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-slate-500 dark:text-slate-400">Posture</span>
      <span
        className={`rounded-full px-2 py-0.5 font-medium ${
          !known
            ? "bg-slate-100 text-slate-500 dark:bg-slate-800"
            : ok
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300"
              : "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300"
        }`}
      >
        {!known ? "–" : issue ? POSTURE_TEXT[issue] : "Upright"}
      </span>
    </div>
  );
}

function FidgetBar({ pct }: { pct: number | null }) {
  const value = pct ?? 0;
  return (
    <div className="text-xs">
      <div className="flex justify-between">
        <span className="text-slate-500 dark:text-slate-400">Distracting hands</span>
        <span className="font-medium tabular-nums">{pct === null ? "–" : `${pct}%`}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${value > 40 ? "bg-amber-500" : "bg-sky-500"}`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function HandActionRow({ action, hands }: { action: HandAction | null; hands: number }) {
  const bad = action !== null && DISTRACTING_ACTIONS.includes(action);
  return (
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="text-slate-500 dark:text-slate-400">Hands</span>
      <span
        className={`rounded-full px-2 py-0.5 text-right font-medium ${
          action === null
            ? "bg-slate-100 text-slate-500 dark:bg-slate-800"
            : bad
              ? "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300"
              : "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300"
        }`}
      >
        {action === null ? (hands ? "–" : "Not in view") : HAND_ACTION_TEXT[action]}
      </span>
    </div>
  );
}

function HandActionSummary({ actions }: { actions: Partial<Record<HandAction, number>> }) {
  const rows = (Object.entries(actions) as [HandAction, number][]).filter(([, pct]) => pct > 0);
  if (!rows.length) return null;
  return (
    <ul className="mt-2 flex flex-wrap gap-1">
      {rows.map(([a, pct]) => (
        <li
          key={a}
          className={`rounded-full px-2 py-0.5 ${
            DISTRACTING_ACTIONS.includes(a) ? "bg-red-50 text-red-700 dark:bg-red-900/40 dark:text-red-300" : "bg-slate-100 dark:bg-slate-800"
          }`}
        >
          {HAND_ACTION_TEXT[a]} {Math.round(pct)}%
        </li>
      ))}
    </ul>
  );
}
