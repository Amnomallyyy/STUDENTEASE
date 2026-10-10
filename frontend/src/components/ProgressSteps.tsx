import { Check, Loader2 } from "lucide-react";

interface Props {
  steps: string[];
  /** Index of the active step; steps before it are done. steps.length means everything finished. */
  current: number;
  error?: string | null;
}

export default function ProgressSteps({ steps, current, error }: Props) {
  return (
    <ol className="space-y-2" aria-label="Progress">
      {steps.map((step, index) => {
        const done = index < current;
        const active = index === current && !error;
        const failed = index === current && !!error;
        return (
          <li key={step} className="flex items-center gap-3 text-sm">
            <span
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs ${
                done
                  ? "border-green-600 bg-green-600 text-white"
                  : active
                    ? "border-brand-600 text-brand-600"
                    : failed
                      ? "border-red-500 text-red-600"
                      : "border-slate-300 text-slate-400"
              }`}
            >
              {done ? (
                <Check className="h-3.5 w-3.5" aria-hidden />
              ) : active ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                index + 1
              )}
            </span>
            <span className={done || active ? "text-slate-800" : failed ? "text-red-700" : "text-slate-400"}>
              {step}
            </span>
          </li>
        );
      })}
      {error && <li className="pl-9 text-sm text-red-600">{error}</li>}
    </ol>
  );
}
