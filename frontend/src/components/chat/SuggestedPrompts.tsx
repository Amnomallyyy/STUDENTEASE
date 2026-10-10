import type { UserMode } from "../../types/profile";

interface Props {
  mode: UserMode;
  disabled?: boolean;
  onPick: (prompt: string) => void;
}

const COMMON = ["What should I do first?", "Which of these jobs should I apply to first?", "Why is my readiness score what it is?"];

const BY_MODE: Record<UserMode, string[]> = {
  student: ["Which project should I build next?", "Make me a plan to be ready in a month"],
  job_seeker: ["My CV says I know Docker, is that a problem?", "Show me data jobs within 10 km"],
};

export default function SuggestedPrompts({ mode, disabled, onPick }: Props) {
  const prompts = [...COMMON, ...BY_MODE[mode]];
  return (
    <div className="flex flex-wrap gap-1.5">
      {prompts.map((prompt) => (
        <button
          key={prompt}
          type="button"
          disabled={disabled}
          onClick={() => onPick(prompt)}
          className="chip border-slate-200 bg-white text-slate-600 hover:border-brand-300 hover:text-brand-700 disabled:opacity-50"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
