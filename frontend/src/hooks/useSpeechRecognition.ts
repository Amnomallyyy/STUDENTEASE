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

/** What went wrong, so the page can say something useful (e.g. "still recording, keep talking"). */
export type SpeechErrorKind = "blocked" | "network" | "other";

// Chrome streams the audio to Google's speech service, and that connection drops now and then. Retry a few
// times with a short back-off before giving up, so one blip does not end the live captions.
const NETWORK_RETRIES = 3;
const RETRY_DELAY_MS = 600;

export interface SpeechRecognitionState {
  supported: boolean;
  listening: boolean;
  /** True while the captions are re-connecting after a dropped connection. */
  reconnecting: boolean;
  /** Finalised text so far. */
  finalText: string;
  /** Words still being recognised (shown greyed out). */
  interim: string;
  error: string | null;
  errorKind: SpeechErrorKind | null;
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
  const [errorKind, setErrorKind] = useState<SpeechErrorKind | null>(null);
  const [reconnecting, setReconnecting] = useState(false);

  const retries = useRef(0);
  const retryDelay = useRef(0); // set by a network error, used by the onend that follows it
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rec = useRef<SpeechRecognitionLike | null>(null);
  const wanted = useRef(false);
  const finalRef = useRef("");
  const interimRef = useRef("");

  const start = useCallback(() => {
    const Ctor = getCtor();
    if (!Ctor) return;
    setError(null);
    setErrorKind(null);
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
      retries.current = 0; // the connection is working again
      setReconnecting(false);
      interimRef.current = interimNow;
      setFinalText(finalRef.current);
      setInterim(interimNow);
    };
    r.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return; // normal pauses
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        wanted.current = false;
        setErrorKind("blocked");
        setError("Microphone access was blocked. Allow it, or type your answer instead.");
      } else if (e.error === "network") {
        retries.current += 1;
        if (retries.current <= NETWORK_RETRIES) {
          retryDelay.current = RETRY_DELAY_MS * 2 ** (retries.current - 1);
          setReconnecting(true); // onend restarts it after the back-off
        } else {
          wanted.current = false;
          setReconnecting(false);
          setErrorKind("network");
          setError("Live captions lost their connection to the speech service.");
        }
      } else {
        setErrorKind("other");
        setError(`Speech recognition error: ${e.error}`);
      }
    };
    r.onend = () => {
      if (wanted.current) {
        const delay = retryDelay.current;
        retryDelay.current = 0;
        const restart = () => {
          if (!wanted.current) return;
          try {
            r.start(); // Chrome ends after silence; keep going until stop()
          } catch {
            setListening(false);
          }
        };
        if (delay) retryTimer.current = setTimeout(restart, delay);
        else restart();
        return;
      }
      setListening(false);
    };
    rec.current = r;
    r.start();
    setListening(true);
  }, [lang]);

  const clearRetry = () => {
    if (retryTimer.current) clearTimeout(retryTimer.current);
    retryTimer.current = null;
    retries.current = 0;
    retryDelay.current = 0;
  };

  const stop = useCallback((): string => {
    wanted.current = false;
    clearRetry();
    setReconnecting(false);
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
    setErrorKind(null);
    setReconnecting(false);
  }, []);

  useEffect(
    () => () => {
      wanted.current = false;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      rec.current?.abort();
    },
    [],
  );

  return { supported, listening, reconnecting, finalText, interim, error, errorKind, start, stop, reset };
}

function joinText(a: string, b: string): string {
  const t = b.trim();
  if (!t) return a;
  return a ? `${a.trimEnd()} ${t}` : t;
}
