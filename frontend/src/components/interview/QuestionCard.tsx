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
    <section className="glass-dark flex flex-col gap-4 rounded-3xl p-5">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>
          Question {p.index + 1} of {p.total}
        </span>
        <span className="capitalize">{p.question.kind}</span>
      </div>
      <div className="flex gap-3">
        <div className="btn-primary h-9 w-9 shrink-0 rounded-full p-0 text-xs font-semibold">
          AI
        </div>
        <p className="font-serif text-xl leading-snug text-white">{p.question.text}</p>
      </div>
      <p className="text-xs text-slate-400">
        Answer with a real example: the Situation, your Task, the Actions you took, and the Result. Aim for 1.5 to 3 minutes.
      </p>

      {p.mode === "speak" ? (
        p.recording ? (
          <button className="btn-danger px-4 py-2.5" onClick={p.onStop}>
            <span className="h-2.5 w-2.5 rounded-sm bg-white" /> Stop answer · {formatTime(p.elapsedS)}
          </button>
        ) : (
          <button
            className="flex items-center justify-center gap-2 btn-primary px-4 py-2.5"
            disabled={p.busy || !p.speechSupported}
            onClick={p.onStart}
	            title={p.speechSupported ? undefined : "Voice recognition isn't supported in this browser. Try Chrome or Edge, or type your answer."}
          >
            <span className="h-2.5 w-2.5 rounded-full bg-red-500" /> Start answering
          </button>
		
        )
      ) : null}

      {!p.recording && (
        <div className="text-xs">
          {p.mode === "speak" ? (
            <button className="text-slate-300 underline hover:text-white" disabled={p.busy} onClick={() => p.onModeChange("type")}>
              {p.speechSupported ? "Type your answer instead" : "Speech recognition isn't available in this browser – type your answer"}
            </button>
          ) : (
            p.speechSupported && (
              <button className="text-slate-300 underline hover:text-white" disabled={p.busy} onClick={() => p.onModeChange("speak")}>
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
