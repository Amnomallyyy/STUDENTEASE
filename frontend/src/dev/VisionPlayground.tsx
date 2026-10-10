// M4 test page: the interview screen's centre and right zones, without M3's question/speech parts.
// Use it to check the overlay, fps and metrics on your own webcam, or replay a recorded answer video.
// Remove from main.tsx once M2's router and M3's Interview page exist.

import { useState } from "react";
import NonVerbalGauges from "../components/interview/NonVerbalGauges";
import WebcamPanel from "../components/interview/WebcamPanel";
import { useVisionMetrics } from "../hooks/useVisionMetrics";
import type { NonVerbalSample } from "../vision/types";
import VisionDebugPanel from "./VisionDebugPanel";

export default function VisionPlayground() {
  const [enabled, setEnabled] = useState(true);
  const [overlay, setOverlay] = useState(true);
  const [source, setSource] = useState<"camera" | string>("camera");
  const [samples, setSamples] = useState<NonVerbalSample[]>([]);
  const vision = useVisionMetrics({ enabled, source, overlay });

  const onFile = (file: File | undefined) => {
    if (!file) return;
    if (source !== "camera") URL.revokeObjectURL(source);
    setSource(URL.createObjectURL(file)); // stays local: an object URL never leaves the browser
  };

  return (
    <main className="min-h-screen bg-slate-50 p-4 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="mx-auto mb-4 flex max-w-6xl flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold">CareerLens · M4 vision playground</h1>
        <span className="text-xs text-slate-500">status: {vision.status}</span>
      </header>

      <div className="mx-auto grid max-w-6xl gap-4 lg:grid-cols-[220px_1fr_300px]">
        <aside className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 text-sm dark:border-slate-700 dark:bg-slate-900">
          {!vision.recording ? (
            <button
              className="rounded-lg bg-slate-900 px-3 py-2 font-medium text-white disabled:opacity-40 dark:bg-white dark:text-slate-900"
              disabled={vision.status !== "running"}
              onClick={vision.startAnswer}
            >
              Start answer
            </button>
          ) : (
            <button className="rounded-lg bg-red-600 px-3 py-2 font-medium text-white" onClick={() => setSamples(vision.stopAnswer())}>
              Stop answer
            </button>
          )}
          <button className="rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600" onClick={vision.recalibrate}>
            Recalibrate
          </button>
          <label className="mt-2 flex items-center gap-2">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Camera on
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={overlay} onChange={(e) => setOverlay(e.target.checked)} /> Landmark overlay
          </label>
          <div className="mt-2 border-t border-slate-200 pt-2 text-xs dark:border-slate-700">
            <p className="mb-1 text-slate-500">Replay a recorded answer instead of the webcam:</p>
            <input type="file" accept="video/*" className="w-full text-xs" onChange={(e) => onFile(e.target.files?.[0])} />
            {source !== "camera" && (
              <button className="mt-1 underline" onClick={() => setSource("camera")}>
                Back to webcam
              </button>
            )}
          </div>
        </aside>

        <WebcamPanel vision={vision} />
        <div className="flex flex-col gap-4">
          <NonVerbalGauges live={vision.live} answer={vision.answer} recording={vision.recording} />
          <VisionDebugPanel debug={vision.debug} />
        </div>
      </div>

      {samples.length > 0 && (
        <section className="mx-auto mt-4 max-w-6xl rounded-xl border border-slate-200 bg-white p-4 text-xs dark:border-slate-700 dark:bg-slate-900">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold">Last answer payload ({samples.length} samples → POST /interview/answer)</h2>
            <button className="underline" onClick={() => navigator.clipboard.writeText(JSON.stringify(samples, null, 2))}>
              Copy JSON
            </button>
          </div>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap">{JSON.stringify(vision.answer?.metrics, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}
