import { AlertTriangle, Map as MapIcon, Mic, RotateCw, Target } from "lucide-react";
import { MiniMarkdown } from "../../lib/miniMarkdown";
import { useSessionStore } from "../../store/session";
import type { ChatAction, UIMessage } from "../../types/api";

interface Props {
  message: UIMessage;
  streaming?: boolean;
  /** Offered on the newest failed reply: asks the same question again. */
  onRetry?: () => void;
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

export default function ChatMessage({ message, streaming, onRetry }: Props) {
  const setPendingAction = useSessionStore((s) => s.setPendingAction);
  const mine = message.role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[90%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
          mine ? "btn-primary block rounded-2xl px-3 py-2 text-left font-normal" : "border border-white/10 bg-white/[0.06] text-slate-100"
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
                  className="chip border-brand-400/40 bg-brand-500/15 text-brand-200 hover:bg-brand-500/25"
                  onClick={() => setPendingAction(action)}
                >
                  <Icon className="h-3 w-3" aria-hidden />
                  {text}
                </button>
              );
            })}
          </div>
        )}
        {mine ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : message.error && !message.content ? null : (
          // The model answers in markdown (bold, bullets); render it instead of showing the asterisks.
          <div className="break-words">
            <MiniMarkdown text={message.content} />
            {streaming && !message.content && <span className="animate-pulse">…</span>}
            {streaming && message.content && <span className="ml-0.5 inline-block w-1.5 animate-pulse bg-slate-400">&nbsp;</span>}
          </div>
        )}
        {message.error && (
          <div role="alert" className={`flex items-start gap-2 text-xs text-amber-200 ${message.content ? "mt-2" : ""}`}>
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="break-words leading-relaxed">{message.error}</p>
              {onRetry && (
                <button type="button" className="chip mt-2 border-white/20 bg-white/10 text-slate-100 hover:bg-white/20" onClick={onRetry}>
                  <RotateCw className="h-3 w-3" aria-hidden />
                  Try again
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
