// Raw per-second vision numbers next to their thresholds, for tuning thresholds.ts on real people.
// Values are relative to the user's calibrated baseline where that applies.

import { THRESHOLDS } from "../vision/thresholds";
import type { VisionDebug } from "../vision/types";

const fmt = (v: number | null, digits = 2) => (v === null ? "–" : v.toFixed(digits));

export default function VisionDebugPanel({ debug }: { debug: VisionDebug | null }) {
  if (!debug) return null;
  const T = THRESHOLDS;
  const rows: [string, string, string, boolean][] = [
    ["Head yaw (deg)", fmt(debug.yawDeg, 1), `±${T.eyeContactDeg}`, debug.yawDeg !== null && Math.abs(debug.yawDeg) > T.eyeContactDeg],
    ["Head pitch (deg)", fmt(debug.pitchDeg, 1), `±${T.eyeContactDeg}`, debug.pitchDeg !== null && Math.abs(debug.pitchDeg) > T.eyeContactDeg],
    ["Eyes left/right", fmt(debug.gazeX), `±${T.gazeMax}`, debug.gazeX !== null && Math.abs(debug.gazeX) > T.gazeMax],
    ["Eyes up/down", fmt(debug.gazeY), `±${T.gazeMax}`, debug.gazeY !== null && Math.abs(debug.gazeY) > T.gazeMax],
    ["Smile (above neutral)", fmt(debug.smile), `≥ ${T.engagedSmile}`, false],
    [
      `Tension (${debug.tensionSource ?? "–"})`,
      fmt(debug.tension),
      `≥ ${T.tenseLevel}`,
      debug.tension !== null && debug.tension >= T.tenseLevel,
    ],
    ["Nose height in frame", fmt(debug.noseY), `> ${T.slouchNoseY}`, debug.noseY !== null && debug.noseY > T.slouchNoseY],
    ["Shoulder tilt (deg)", fmt(debug.shoulderTiltDeg, 1), `±${T.shoulderTiltDeg}`, debug.shoulderTiltDeg !== null && Math.abs(debug.shoulderTiltDeg) > T.shoulderTiltDeg],
    [
      "Lean / baseline",
      `${fmt(debug.lean)} / ${debug.leanBaseline ? debug.leanBaseline.toFixed(2) : "–"}`,
      `< ${T.slouchRatio}×`,
      debug.lean !== null && debug.leanBaseline > 0 && debug.lean < T.slouchRatio * debug.leanBaseline,
    ],
    ["Hands in view", String(debug.hands), "", false],
    ["Palm speed", fmt(debug.handSpeed), `> ${T.fidgetVelocity}`, debug.handSpeed !== null && debug.handSpeed > T.fidgetVelocity],
    ["Finger speed", fmt(debug.fingerSpeed), `> ${T.fiddleVelocity}`, debug.fingerSpeed !== null && debug.fingerSpeed > T.fiddleVelocity],
    ["Straight fingers", debug.extendedFingers === null ? "–" : String(debug.extendedFingers), "≥ 3 = open", false],
    ["Hand action", debug.handAction ?? "–", "", false],
  ];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 text-xs dark:border-slate-700 dark:bg-slate-900">
      <h2 className="mb-2 font-semibold">Debug: raw values (relative to your calibrated baseline)</h2>
      <table className="w-full tabular-nums">
        <thead className="text-left text-slate-500">
          <tr>
            <th className="font-normal">Measure</th>
            <th className="text-right font-normal">Now</th>
            <th className="text-right font-normal">Threshold</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, value, threshold, over]) => (
            <tr key={label} className={over ? "text-red-600 dark:text-red-400" : ""}>
              <td className="py-0.5">{label}</td>
              <td className="py-0.5 text-right font-medium">{value}</td>
              <td className="py-0.5 text-right text-slate-500">{threshold}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
