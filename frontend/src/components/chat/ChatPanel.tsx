// Persistent career assistant panel: streams POST /chat, shows suggested prompts, and renders
// "open in module" chips for the tool-call actions the backend emits.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Eraser, Send, Square, X } from "lucide-react";
import { useChatStream } from "../../hooks/useChatStream";
import { hasCV, useProfileStore } from "../../store/profile";
import { useSessionStore } from "../../store/session";
import ChatMessage from "./ChatMessage";
import SuggestedPrompts from "./SuggestedPrompts";

interface Props {
  onClose: () => void;
}

export default function ChatPanel({ onClose }: Props) {
  const profile = useProfileStore((s) => s.profile);
  const clearChat = useSessionStore((s) => s.clearChat);
  const { messages, send, stop, retry, streaming } = useChatStream();
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, streaming]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    void send(text);
  }

  const ready = hasCV(profile);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-white/10 px-5 py-4">
        <div className="min-w-0 flex-1">
          <p className="font-serif text-lg font-medium leading-tight text-white">Career assistant</p>
          <p className="truncate text-xs text-slate-400">
            Answers only from your profile, gaps, jobs and interview results.
          </p>
        </div>
        <button className="btn-ghost-dark p-1.5" onClick={clearChat} title="Clear conversation" aria-label="Clear">
          <Eraser className="h-4 w-4" aria-hidden />
        </button>
        <button className="btn-ghost-dark p-1.5" onClick={onClose} title="Close" aria-label="Close">
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>

      <div className="scroll-thin flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-xs leading-relaxed text-slate-300">
            {ready ? (
              <>
                Ask about your gap, which jobs to apply to first, a CV claim, or your readiness score. The assistant
                can open the Career Map and the interview for you.
              </>
            ) : (
              <>Upload a CV first so the assistant has something to ground its answers in.</>
            )}
          </div>
        )}
        {messages.map((message, index) => (
          <ChatMessage
            key={index}
            message={message}
            streaming={streaming && index === messages.length - 1 && message.role === "assistant"}
            onRetry={index === messages.length - 1 && !streaming ? retry : undefined}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-white/10 px-5 py-4">
        <SuggestedPrompts mode={profile?.mode ?? "student"} disabled={streaming || !ready} onPick={(p) => void send(p)} />
        <form onSubmit={submit} className="mt-2 flex items-end gap-2">
          <textarea
            className="input-dark min-h-[40px] resize-none"
            rows={1}
            placeholder={ready ? "Ask the assistant…" : "Upload a CV to start"}
            value={draft}
            disabled={!ready || streaming}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(e);
              }
            }}
          />
          {streaming ? (
            <button type="button" className="btn-ghost-dark border border-white/10" onClick={stop} aria-label="Stop">
              <Square className="h-4 w-4" aria-hidden />
            </button>
          ) : (
            <button type="submit" className="btn-primary" disabled={!ready || !draft.trim()} aria-label="Send">
              <Send className="h-4 w-4" aria-hidden />
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
