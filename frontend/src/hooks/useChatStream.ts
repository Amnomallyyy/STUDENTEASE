// Streams POST /chat into the session store. Action events (open_map, open_career_map, open_interview)
// are attached to the assistant message as "open in module" chips and handed to the Shell via pendingAction.
import { useCallback, useRef, useState } from "react";
import { api, errorMessage } from "../lib/api";
import { useSessionStore } from "../store/session";
import type { ChatAction, UIMessage } from "../types/api";
import type { ChatMessage } from "../types/profile";

export function useChatStream() {
  const messages = useSessionStore((s) => s.messages);
  const setMessages = useSessionStore((s) => s.setMessages);
  const setPendingAction = useSessionStore((s) => s.setPendingAction);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content || streaming) return;
      const current = useSessionStore.getState().messages;
      const history: ChatMessage[] = current
        .filter((m) => m.content.trim() && !m.error)
        .map((m) => ({ role: m.role, content: m.content }));

      const base: UIMessage[] = [...current, { role: "user", content }];
      let reply: UIMessage = { role: "assistant", content: "" };
      const commit = () => setMessages([...base, reply]);
      commit();

      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      try {
        await api.chat(
          { message: content, history },
          (event) => {
            switch (event.type) {
              case "text":
                reply = { ...reply, content: reply.content + event.delta };
                break;
              case "error":
                reply = { ...reply, error: event.message };
                break;
              case "done":
                break;
              default: {
                const action: ChatAction = event;
                reply = { ...reply, actions: [...(reply.actions ?? []), action] };
                setPendingAction(action);
              }
            }
            commit();
          },
          controller.signal,
        );
      } catch (err) {
        reply = { ...reply, error: errorMessage(err) };
        commit();
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setStreaming(false);
      }
    },
    [setMessages, setPendingAction, streaming],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  /** Re-ask the last question after a failed reply: drops the failed turn first so it is not shown twice. */
  const retry = useCallback(() => {
    if (streaming) return;
    const current = useSessionStore.getState().messages;
    const last = current[current.length - 1];
    const asked = current[current.length - 2];
    if (!last?.error || asked?.role !== "user") return;
    setMessages(current.slice(0, -2));
    void send(asked.content);
  }, [send, setMessages, streaming]);

  return { messages, send, stop, retry, streaming };
}
