// Centre zone of the interview screen: mirrored webcam preview with the live landmark overlay.
// The page owns the hook (useVisionMetrics) and passes it here and to NonVerbalGauges.

import type { VisionController } from "../../hooks/useVisionMetrics";

interface Props {
  vision: VisionController;
  className?: string;
}

const STATUS_TEXT: Record<string, string> = {
  idle: "Camera off",
  "loading-models": "Loading body-language models…",
  "starting-camera": "Starting camera…",
};

export default function WebcamPanel({ vision, className = "" }: Props) {
  const { videoRef, canvasRef, status, error, live, recording, delegate } = vision;
  const running = status === "running";

  return (
    <div className={`relative aspect-[4/3] w-full overflow-hidden rounded-xl bg-slate-900 ${className}`}>
      {/* Mirrored like a selfie view; video and canvas share the same box so the overlay lines up. */}
      <video ref={videoRef} className="absolute inset-0 h-full w-full -scale-x-100 object-contain" muted playsInline />
      <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100 object-contain" />

      {!running && (
        <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-slate-200">
          {status === "error" ? <p className="max-w-sm text-amber-300">{error}</p> : <p>{STATUS_TEXT[status]}</p>}
        </div>
      )}

      {running && !live.faceDetected && (
        <div className="absolute inset-x-0 top-3 mx-auto w-fit rounded-full bg-amber-500/90 px-3 py-1 text-xs font-medium text-slate-950">
          Face not visible – move into the frame
        </div>
      )}
      {running && live.faceDetected && !live.calibrated && (
        <div className="absolute inset-x-0 top-3 mx-auto w-fit rounded-full bg-slate-800/90 px-3 py-1 text-xs text-slate-100">
          Look at the screen for a moment…
        </div>
      )}

      {recording && (
        <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-red-600/90 px-2.5 py-1 text-xs font-medium text-white">
          <span className="h-2 w-2 animate-pulse rounded-full bg-white" /> REC
        </div>
      )}

      <div className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-full bg-slate-950/75 px-3 py-1 text-xs text-slate-100">
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-emerald-400" aria-hidden="true">
          <path d="M8 1 2 3.5v4C2 11 4.6 14.2 8 15c3.4-.8 6-4 6-7.5v-4L8 1Zm-1 10L4 8l1.1-1.1L7 8.8l3.9-3.9L12 6l-5 5Z" />
        </svg>
        Video stays on your device
      </div>

      {running && (
        <div className="absolute bottom-3 right-3 rounded-full bg-slate-950/60 px-2 py-0.5 text-[10px] text-slate-300 tabular-nums">
          {live.fps} fps · {delegate}
        </div>
      )}
    </div>
  );
}
