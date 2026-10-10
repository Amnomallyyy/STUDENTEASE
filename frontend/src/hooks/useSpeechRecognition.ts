// Live transcript with the browser's Web Speech API (free, no backend). Chrome and Edge support it;
// elsewhere `supported` is false and the interview falls back to typed answers. Chrome stops
// listening after a pause, so the hook restarts it until stop() is called.

import { useCallback, useEffect, useRef, useState } from "react";

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface SpeechRecognitionState {
  supported: boolean;
  listening: boolean;
  /** Finalised text so far. */
  finalText: string;
  /** Words still being recognised (shown greyed out). */
  interim: string;
  error: string | null;
  start(): void;
  /** Stops listening and returns everything heard, including the last interim words. */
  stop(): string;
  reset(): void;
}

export function useSpeechRecognition(lang = "en-US"): SpeechRecognitionState {
  const supported = typeof window !== "undefined" && getCtor() !== null;
  const [listening, setListening] = useState(false);
  const [finalText, setFinalText] = useState("");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);

  const rec = useRef<SpeechRecognitionLike | null>(null);
  const wanted = useRef(false);
  const finalRef = useRef("");
  const interimRef = useRef("");

  const start = useCallback(() => {
    const Ctor = getCtor();
    if (!Ctor) return;
    setError(null);
    wanted.current = true;
    const r = new Ctor();
    r.continuous = true;
    r.interimResults = true;
    r.lang = lang;
    r.onresult = (e) => {
      let interimNow = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        const text = res[0].transcript;
        if (res.isFinal) finalRef.current = joinText(finalRef.current, text);
        else interimNow += text;
      }
      interimRef.current = interimNow;
      setFinalText(finalRef.current);
      setInterim(interimNow);
    };
    r.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return; // normal pauses
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        wanted.current = false;
        setError("Microphone access was blocked. Allow it, or type your answer instead.");
      } else if (e.error === "network") {
        setError("Speech recognition needs an internet connection. Type your answer instead.");
        wanted.current = false;
      } else setError(`Speech recognition error: ${e.error}`);
    };
    r.onend = () => {
      if (wanted.current) {
        try {
          r.start(); // Chrome ends after silence; keep going until stop()
          return;
        } catch {
          /* fall through */
        }
      }
      setListening(false);
    };
    rec.current = r;
    r.start();
    setListening(true);
  }, [lang]);

  const stop = useCallback((): string => {
    wanted.current = false;
    rec.current?.stop();
    const all = joinText(finalRef.current, interimRef.current);
    finalRef.current = all;
    interimRef.current = "";
    setFinalText(all);
    setInterim("");
    setListening(false);
    return all;
  }, []);

  const reset = useCallback(() => {
    finalRef.current = "";
    interimRef.current = "";
    setFinalText("");
    setInterim("");
    setError(null);
  }, []);

  useEffect(
    () => () => {
      wanted.current = false;
      rec.current?.abort();
    },
    [],
  );

  return { supported, listening, finalText, interim, error, start, stop, reset };
}

function joinText(a: string, b: string): string {
  const t = b.trim();
  if (!t) return a;
  return a ? `${a.trimEnd()} ${t}` : t;
}
