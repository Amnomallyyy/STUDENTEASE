import { Map as MapIcon, Mic, Target } from "lucide-react";
import { useSessionStore } from "../../store/session";
import type { ChatAction, UIMessage } from "../../types/api";

interface Props {
  message: UIMessage;
  streaming?: boolean;
}

function actionLabel(action: ChatAction): { text: string; Icon: typeof MapIcon } {
  switch (action.type) {
    case "open_map":
      return {
        text: `Open map · ${Math.round(action.radius_km)} km${action.keyword ? ` · "${action.keyword}"` : ""}`,
        Icon: MapIcon,
      };
    case "open_career_map":
      return { text: `Open Career Map · ${action.role}`, Icon: Target };
    case "open_interview":
      return { text: `Start interview · ${action.role}`, Icon: Mic };
  }
}

export default function ChatMessage({ message, streaming }: Props) {
  const setPendingAction = useSessionStore((s) => s.setPendingAction);
  const mine = message.role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[90%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
          mine ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-900"
        }`}
      >
        {message.actions && message.actions.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1">
            {message.actions.map((action, i) => {
              const { text, Icon } = actionLabel(action);
              return (
                <button
                  key={i}
                  type="button"
                  className="chip border-brand-300 bg-white text-brand-700 hover:bg-brand-50"
                  onClick={() => setPendingAction(action)}
                >
                  <Icon className="h-3 w-3" aria-hidden />
                  {text}
                </button>
              );
            })}
          </div>
        )}
        <p className="whitespace-pre-wrap break-words">
          {message.content}
          {streaming && !message.content && <span className="animate-pulse">…</span>}
          {streaming && message.content && <span className="ml-0.5 inline-block w-1.5 animate-pulse bg-slate-400">&nbsp;</span>}
        </p>
        {message.error && <p className="mt-1 text-xs text-red-600">{message.error}</p>}
      </div>
    </div>
  );
}
