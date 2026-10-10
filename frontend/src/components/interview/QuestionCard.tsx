// Left zone: the interviewer's question, progress, and the record / type controls.

import type { InterviewQuestion } from "../../types/profile";

interface Props {
  question: InterviewQuestion;
  index: number;
  total: number;
  mode: "speak" | "type";
  speechSupported: boolean;
  recording: boolean;
  elapsedS: number;
  busy: boolean;
  onModeChange(mode: "speak" | "type"): void;
  onStart(): void;
  onStop(): void;
}

export default function QuestionCard(p: Props) {
  return (
    <section className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
        <span>
          Question {p.index + 1} of {p.total}
        </span>
        <span className="capitalize">{p.question.kind}</span>
      </div>
      <div className="flex gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-300">
          AI
        </div>
        <p className="text-base leading-relaxed font-medium">{p.question.text}</p>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Answer with a real example: the Situation, your Task, the Actions you took, and the Result. Aim for 1.5 to 3 minutes.
      </p>

      {p.mode === "speak" ? (
        p.recording ? (
          <button className="flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 font-medium text-white" onClick={p.onStop}>
            <span className="h-2.5 w-2.5 rounded-sm bg-white" /> Stop answer · {formatTime(p.elapsedS)}
          </button>
        ) : (
          <button
            className="flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 font-medium text-white disabled:opacity-40 dark:bg-white dark:text-slate-900"
            disabled={p.busy || !p.speechSupported}
            onClick={p.onStart}
          >
            <span className="h-2.5 w-2.5 rounded-full bg-red-500" /> Start answering
          </button>
        )
      ) : null}

      {!p.recording && (
        <div className="text-xs">
          {p.mode === "speak" ? (
            <button className="text-slate-500 underline dark:text-slate-400" disabled={p.busy} onClick={() => p.onModeChange("type")}>
              {p.speechSupported ? "Type your answer instead" : "Speech recognition isn't available in this browser – type your answer"}
            </button>
          ) : (
            p.speechSupported && (
              <button className="text-slate-500 underline dark:text-slate-400" disabled={p.busy} onClick={() => p.onModeChange("speak")}>
                Speak your answer instead
              </button>
            )
          )}
        </div>
      )}
    </section>
  );
}

export function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}
