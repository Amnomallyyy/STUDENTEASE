// Draws the live landmark overlay on a canvas laid over the video: face contours coloured by gaze
// (green = on screen, amber = head turned, orange = eyes away), shoulders/torso from the pose model,
// and hands from the hand model coloured by what they are doing.

import { FaceLandmarker, HandLandmarker } from "@mediapipe/tasks-vision";
import type { NormalizedLandmark } from "@mediapipe/tasks-vision";
import { THRESHOLDS } from "./thresholds";
import { DISTRACTING_ACTIONS, type GazeState, type HandAction } from "./types";

type Connection = { start: number; end: number };

const FACE_CONNECTIONS: Connection[] = [
  ...FaceLandmarker.FACE_LANDMARKS_FACE_OVAL,
  ...FaceLandmarker.FACE_LANDMARKS_LEFT_EYE,
  ...FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE,
  ...FaceLandmarker.FACE_LANDMARKS_LEFT_EYEBROW,
  ...FaceLandmarker.FACE_LANDMARKS_RIGHT_EYEBROW,
  ...FaceLandmarker.FACE_LANDMARKS_LEFT_IRIS,
  ...FaceLandmarker.FACE_LANDMARKS_RIGHT_IRIS,
  ...FaceLandmarker.FACE_LANDMARKS_LIPS,
];

/** Shoulder line and torso only. Pose arms/wrists are not drawn: they are guessed when hands are off-screen. */
const BODY_CONNECTIONS: Connection[] = [
  { start: 11, end: 12 },
  { start: 11, end: 23 },
  { start: 12, end: 24 },
  { start: 23, end: 24 },
];

export const OVERLAY_COLORS = {
  contact: "#22c55e",
  head_away: "#f59e0b",
  eyes_away: "#f97316",
  none: "#94a3b8",
  body: "#38bdf8",
  handGood: "#22c55e",
  handNeutral: "#38bdf8",
  handBad: "#ef4444",
} as const;

export interface OverlayInput {
  face?: NormalizedLandmark[];
  /** Latest pose landmarks; pose runs on alternate frames, so the caller passes the last result. */
  pose?: NormalizedLandmark[];
  hands?: NormalizedLandmark[][];
  handActions?: (HandAction | null)[];
  gaze: GazeState | null;
}

export function drawOverlay(canvas: HTMLCanvasElement, input: OverlayInput): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const { width: w, height: h } = canvas;
  ctx.clearRect(0, 0, w, h);
  const lw = Math.max(1, w / 400);

  if (input.pose) {
    ctx.strokeStyle = OVERLAY_COLORS.body;
    ctx.fillStyle = OVERLAY_COLORS.body;
    ctx.lineWidth = lw * 2;
    strokeConnections(ctx, input.pose, BODY_CONNECTIONS, w, h, true);
    for (const i of [11, 12]) {
      const p = input.pose[i];
      if (p && p.visibility >= THRESHOLDS.minVisibility) dot(ctx, p.x * w, p.y * h, lw * 3);
    }
  }

  input.hands?.forEach((pts, i) => {
    const action = input.handActions?.[i] ?? null;
    const color = !action
      ? OVERLAY_COLORS.handNeutral
      : DISTRACTING_ACTIONS.includes(action)
        ? OVERLAY_COLORS.handBad
        : action === "gesturing"
          ? OVERLAY_COLORS.handGood
          : OVERLAY_COLORS.handNeutral;
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = lw * 1.5;
    strokeConnections(ctx, pts, HandLandmarker.HAND_CONNECTIONS, w, h, false);
    for (const p of pts) dot(ctx, p.x * w, p.y * h, lw * 1.8);
  });

  if (input.face) {
    const color = input.gaze === null ? OVERLAY_COLORS.none : OVERLAY_COLORS[input.gaze];
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = lw;
    strokeConnections(ctx, input.face, FACE_CONNECTIONS, w, h, false);
    const nose = input.face[1];
    if (nose) dot(ctx, nose.x * w, nose.y * h, lw * 3);
  }
}

export function clearOverlay(canvas: HTMLCanvasElement): void {
  canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
}

function strokeConnections(
  ctx: CanvasRenderingContext2D,
  points: NormalizedLandmark[],
  connections: Connection[],
  w: number,
  h: number,
  checkVisibility: boolean,
): void {
  ctx.beginPath();
  for (const { start, end } of connections) {
    const a = points[start];
    const b = points[end];
    if (!a || !b) continue;
    if (checkVisibility && (a.visibility < THRESHOLDS.minVisibility || b.visibility < THRESHOLDS.minVisibility)) continue;
    ctx.moveTo(a.x * w, a.y * h);
    ctx.lineTo(b.x * w, b.y * h);
  }
  ctx.stroke();
}

function dot(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void {
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}
