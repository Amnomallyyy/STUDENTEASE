// Records the spoken answer (audio only):
//  - one continuous recording, sent with the answer for an accurate Whisper transcript;
//  - optionally, short standalone clips every few seconds (onSegment) for live Whisper filler counting,
//    because the browser's own speech recognition drops "um" and "uh".
// Optional: if the microphone or MediaRecorder is unavailable, start() returns false, stop() resolves to
// null, and the browser's live transcript is used instead.

import { useCallback, useEffect, useRef } from "react";

export interface RecorderOptions {
  /** Length of each live clip in ms. Default 5000. */
  segmentMs?: number;
  /** Called with each finished clip while recording (each is a standalone, decodable file). */
  onSegment?(clip: Blob, index: number): void;
}

const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];

export function useAudioRecorder() {
  const stream = useRef<MediaStream | null>(null);
  const main = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const segment = useRef<MediaRecorder | null>(null);
  const segmentTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const segmenting = useRef(false);

  const stopSegments = () => {
    segmenting.current = false;
    if (segmentTimer.current) clearTimeout(segmentTimer.current);
    segmentTimer.current = null;
    if (segment.current && segment.current.state !== "inactive") segment.current.stop();
    segment.current = null;
  };

  const release = () => {
    stopSegments();
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    main.current = null;
  };

  const start = useCallback(async (options: RecorderOptions = {}): Promise<boolean> => {
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices) return false;
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = s;
      const type = MIME_TYPES.find((t) => MediaRecorder.isTypeSupported(t));
      const opts = type ? { mimeType: type } : undefined;

      const r = new MediaRecorder(s, opts);
      chunks.current = [];
      r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      r.start(1000);
      main.current = r;

      if (options.onSegment) {
        // A second recorder restarted every segmentMs, so each clip has its own header and can be
        // transcribed on its own (slices of one long recording cannot).
        segmenting.current = true;
        let index = 0;
        const next = () => {
          if (!segmenting.current || !stream.current) return;
          const seg = new MediaRecorder(stream.current, opts);
          const parts: Blob[] = [];
          const i = index++;
          seg.ondataavailable = (e) => e.data.size && parts.push(e.data);
          seg.onstop = () => {
            if (parts.length) options.onSegment!(new Blob(parts, { type: seg.mimeType }), i);
          };
          seg.start();
          segment.current = seg;
          segmentTimer.current = setTimeout(() => {
            if (seg.state !== "inactive") seg.stop();
            next();
          }, options.segmentMs ?? 5000);
        };
        next();
      }
      return true;
    } catch {
      release();
      return false;
    }
  }, []);

  /** Stops recording; the last partial clip is still delivered to onSegment. Resolves to the full recording. */
  const stop = useCallback(
    () =>
      new Promise<Blob | null>((resolve) => {
        stopSegments();
        const r = main.current;
        if (!r || r.state === "inactive") {
          release();
          return resolve(null);
        }
        r.onstop = () => {
          const blob = chunks.current.length ? new Blob(chunks.current, { type: r.mimeType }) : null;
          release();
          resolve(blob);
        };
        r.stop();
      }),
    [],
  );

  useEffect(() => () => release(), []);

  return { start, stop };
}
