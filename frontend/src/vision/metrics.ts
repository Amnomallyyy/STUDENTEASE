// Per-frame geometry from MediaPipe results. Pure functions plus small stateful trackers
// (hand speed and nods) that need the previous frames. No scoring happens here.

import type { Category, Classifications, Matrix, NormalizedLandmark } from "@mediapipe/tasks-vision";
import { THRESHOLDS } from "./thresholds";
import type { FaceFrame, Hand, HandAction, PoseFrame, Point } from "./types";

const RAD_TO_DEG = 180 / Math.PI;

// Landmark indices (MediaPipe face mesh / BlazePose / hand).
export const FACE_NOSE_TIP = 1;
export const POSE = { nose: 0, leftShoulder: 11, rightShoulder: 12 } as const;
const PALM = [0, 5, 9, 13, 17];

export interface HeadAngles {
  yawDeg: number;
  pitchDeg: number;
  rollDeg: number;
}

/**
 * Yaw / pitch / roll from the 4x4 facial transformation matrix. MediaPipe packs it column-major,
 * so element (row r, col c) is data[c * 4 + r]. Columns are normalized first to remove scale.
 */
export function headAnglesFromMatrix(matrix: Matrix): HeadAngles {
  const d = matrix.data;
  const at = (r: number, c: number) => d[c * 4 + r];
  const col = (c: number) => Math.hypot(at(0, c), at(1, c), at(2, c)) || 1;
  const s0 = col(0);
  const s1 = col(1);
  const s2 = col(2);
  const r00 = at(0, 0) / s0;
  const r10 = at(1, 0) / s0;
  const r20 = at(2, 0) / s0;
  const r21 = at(2, 1) / s1;
  const r22 = at(2, 2) / s2;
  return {
    yawDeg: Math.asin(clamp(-r20, -1, 1)) * RAD_TO_DEG,
    pitchDeg: Math.atan2(r21, r22) * RAD_TO_DEG,
    rollDeg: Math.atan2(r10, r00) * RAD_TO_DEG,
  };
}

/** Blendshape scores by name, so each one is a lookup instead of a scan. */
export function blendshapeMap(classifications: Classifications | undefined): Record<string, number> {
  const out: Record<string, number> = {};
  for (const c of classifications?.categories ?? []) out[c.categoryName] = c.score;
  return out;
}

const pair = (b: Record<string, number>, name: string) => ((b[`${name}Left`] ?? 0) + (b[`${name}Right`] ?? 0)) / 2;

/**
 * Eye direction inside the head from the eyeLook* blendshapes (ARKit convention: "Out" on the left eye
 * and "In" on the right eye both mean looking towards the subject's left). Each axis is -1..1.
 */
export function gazeFromBlendshapes(b: Record<string, number>): { gazeX: number; gazeY: number } {
  const left = (b.eyeLookOutLeft ?? 0) - (b.eyeLookInLeft ?? 0);
  const right = (b.eyeLookInRight ?? 0) - (b.eyeLookOutRight ?? 0);
  const up = pair(b, "eyeLookUp");
  const down = pair(b, "eyeLookDown");
  return { gazeX: (left + right) / 2, gazeY: up - down };
}

/** Face geometry for the first detected face, or null. */
export function extractFace(
  landmarks: NormalizedLandmark[] | undefined,
  blendshapes: Classifications | undefined,
  matrix: Matrix | undefined,
): FaceFrame | null {
  if (!landmarks || landmarks.length <= FACE_NOSE_TIP || !matrix) return null;
  const b = blendshapeMap(blendshapes);
  const nose = landmarks[FACE_NOSE_TIP];
  let minX = 1, minY = 1, maxX = 0, maxY = 0;
  for (const p of landmarks) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  return {
    ...headAnglesFromMatrix(matrix),
    ...gazeFromBlendshapes(b),
    noseX: nose.x,
    noseY: nose.y,
    box: { minX, minY, maxX, maxY },
    smile: pair(b, "mouthSmile"),
    tension: {
      browDown: pair(b, "browDown"),
      noseSneer: pair(b, "noseSneer"),
      mouthPress: pair(b, "mouthPress"),
      mouthFrown: pair(b, "mouthFrown"),
    },
  };
}

/**
 * Body geometry for the first detected pose, or null. `aspect` is video width / height: normalized
 * x and y use different units, so x is scaled by the aspect before any angle or distance.
 * Wrists are deliberately not read from the pose model: when hands are below the frame it still
 * guesses them, often on top of the shoulders. Hands come from the hand model instead.
 */
export function extractPose(landmarks: NormalizedLandmark[] | undefined, aspect: number): PoseFrame | null {
  if (!landmarks || landmarks.length <= POSE.rightShoulder) return null;
  const p = (i: number): Point => ({ x: landmarks[i].x * aspect, y: landmarks[i].y });
  const visible = (i: number) => landmarks[i].visibility >= THRESHOLDS.minVisibility && inImage(landmarks[i]);

  const ls = p(POSE.leftShoulder);
  const rs = p(POSE.rightShoulder);
  const shoulderWidth = Math.hypot(ls.x - rs.x, ls.y - rs.y);
  const shoulders =
    visible(POSE.leftShoulder) && visible(POSE.rightShoulder) && shoulderWidth >= THRESHOLDS.minShoulderWidth;

  let shoulderTiltDeg = 0;
  let lean = 0;
  if (shoulders) {
    shoulderTiltDeg = lineTiltDeg(ls, rs);
    const mid = { x: (ls.x + rs.x) / 2, y: (ls.y + rs.y) / 2 };
    const nose = p(POSE.nose);
    lean = Math.hypot(nose.x - mid.x, nose.y - mid.y) / shoulderWidth;
  }
  return { shoulders, shoulderTiltDeg, lean, shoulderWidth };
}

/** Hands from the hand model (confidence already filtered by the task options), with finger shape. */
export function extractHands(
  landmarks: NormalizedLandmark[][] | undefined,
  handedness: Category[][] | undefined,
  aspect: number,
): Hand[] {
  return (landmarks ?? []).map((pts, i) => {
    const p = (k: number): Point => ({ x: pts[k].x * aspect, y: pts[k].y });
    const cx = PALM.reduce((s, k) => s + pts[k].x, 0) / PALM.length;
    const cy = PALM.reduce((s, k) => s + pts[k].y, 0) / PALM.length;
    const center = { x: cx * aspect, y: cy };
    const wrist = p(0);
    let extended = 0;
    let curled = 0;
    for (const f of FINGERS) {
      const tip = dist(p(f.tip), wrist);
      if (tip > THRESHOLDS.fingerExtendRatio * dist(p(f.pip), wrist)) extended += 1;
      if (tip < THRESHOLDS.fistRatio * dist(p(f.mcp), wrist)) curled += 1;
    }
    return {
      label: handedness?.[i]?.[0]?.categoryName ?? `hand${i}`,
      center,
      imageCenter: { x: cx, y: cy },
      size: dist(wrist, p(9)),
      tips: FINGERS.map((f) => ({ x: p(f.tip).x - center.x, y: p(f.tip).y - center.y })),
      extendedFingers: extended,
      fist: curled === FINGERS.length,
    };
  });
}

// Index, middle, ring, little: base knuckle (MCP), middle knuckle (PIP) and tip.
const FINGERS = [
  { mcp: 5, pip: 6, tip: 8 },
  { mcp: 9, pip: 10, tip: 12 },
  { mcp: 13, pip: 14, tip: 16 },
  { mcp: 17, pip: 18, tip: 20 },
];

/** Where a palm is relative to the face: on the mouth, elsewhere on the face, on the head/hair/neck, or away. */
export function handFaceZone(hand: Hand, face: FaceFrame | null): "mouth" | "face" | "head" | null {
  if (!face) return null;
  const { minX, minY, maxX, maxY } = face.box;
  const w = maxX - minX;
  const h = maxY - minY;
  const { x, y } = hand.imageCenter;
  const m = THRESHOLDS.faceBoxMargin;
  if (x >= minX - w * m && x <= maxX + w * m && y >= minY - h * m && y <= maxY + h * m) {
    return y >= maxY - h * THRESHOLDS.mouthShare ? "mouth" : "face";
  }
  const hm = THRESHOLDS.headMargin;
  if (x >= minX - w * hm && x <= maxX + w * hm && y >= minY - h * hm && y <= maxY + h * hm * 0.5) return "head";
  return null;
}

/** Motion of one hand: palm speed and fingertip speed relative to the palm, in shoulder widths / s. */
export interface HandMotion {
  palm: number | null;
  fingers: number | null;
}

/**
 * Rule-based action for one hand on one frame. Order matters: touching the face beats everything,
 * then fiddling (fingers busy, palm still), restless (palm moving fast without an open hand), fist,
 * gesturing (open hand moving), resting.
 */
export function classifyHand(hand: Hand, motion: HandMotion, face: FaceFrame | null): HandAction {
  const zone = handFaceZone(hand, face);
  if (zone === "mouth") return "covering_mouth";
  if (zone === "face") return "touching_face";
  if (zone === "head") return "touching_head";
  const palm = motion.palm ?? 0;
  const fingers = motion.fingers ?? 0;
  const open = hand.extendedFingers >= 3;
  if (fingers > THRESHOLDS.fiddleVelocity && palm < THRESHOLDS.fidgetVelocity) return "fiddling";
  if (palm > THRESHOLDS.fidgetVelocity && !open) return "restless";
  if (hand.fist) return "fist";
  if (open && palm >= THRESHOLDS.gestureMinVelocity) return "gesturing";
  return "resting";
}

/** Angle of the line a-b from horizontal, folded into -90..90 so the order of the points does not matter. */
export function lineTiltDeg(a: Point, b: Point): number {
  let deg = Math.atan2(a.y - b.y, a.x - b.x) * RAD_TO_DEG;
  if (deg > 90) deg -= 180;
  if (deg < -90) deg += 180;
  return deg;
}

/**
 * Palm speed and fingertip speed (relative to the palm) for each hand, in shoulder widths per second
 * so they do not depend on distance to the camera. Each hand is matched to the nearest hand of the
 * previous frame and its speeds are smoothed, to keep landmark jitter from reading as fidgeting.
 */
export class HandTracker {
  private prev: { t: number; hands: Hand[]; motion: HandMotion[] } | null = null;

  /** Returns one HandMotion per input hand (null speeds on the first frame a hand appears). */
  update(t: number, hands: Hand[], shoulderWidth: number): HandMotion[] {
    const prev = this.prev;
    const dt = prev ? (t - prev.t) / 1000 : 0;
    const usable = prev && dt > 0 && dt <= 0.5;
    const a = THRESHOLDS.handSmoothing;

    const motion = hands.map((h): HandMotion => {
      const scale = shoulderWidth > 0 ? shoulderWidth : h.size / THRESHOLDS.palmToShoulder;
      if (!usable || scale <= 0) return { palm: null, fingers: null };
      let best = -1;
      let bestDist = Infinity;
      prev.hands.forEach((q, j) => {
        const d = dist(h.center, q.center);
        if (d < bestDist) [best, bestDist] = [j, d];
      });
      if (best < 0 || bestDist > scale) return { palm: null, fingers: null }; // > 1 shoulder width in one frame = a different hand
      const q = prev.hands[best];
      const fingerMove = h.tips.reduce((s, tip, k) => s + dist(tip, q.tips[k]), 0) / h.tips.length;
      const palmRaw = bestDist / dt / scale;
      const fingerRaw = fingerMove / dt / scale;
      const before = prev.motion[best];
      return {
        palm: before.palm === null ? palmRaw : a * palmRaw + (1 - a) * before.palm,
        fingers: before.fingers === null ? fingerRaw : a * fingerRaw + (1 - a) * before.fingers,
      };
    });
    this.prev = { t, hands, motion };
    return motion;
  }

  reset(): void {
    this.prev = null;
  }
}

/**
 * Detects a nod: head pitch moves at least `nodMinDeg` away and comes back within `nodWindowMs`.
 * Direction-agnostic, because the pitch sign depends on the camera; a slow look-down that stays
 * down is not a nod.
 */
export class NodDetector {
  private buf: { t: number; pitch: number }[] = [];
  private lastNod = -Infinity;

  update(t: number, pitchDeg: number | null): boolean {
    if (pitchDeg === null) {
      this.buf = [];
      return false;
    }
    this.buf.push({ t, pitch: pitchDeg });
    while (this.buf.length && t - this.buf[0].t > THRESHOLDS.nodWindowMs) this.buf.shift();
    if (this.buf.length < 3 || t - this.lastNod < THRESHOLDS.nodCooldownMs) return false;

    const start = this.buf[0].pitch;
    let peak = 0;
    for (let i = 1; i < this.buf.length - 1; i++) peak = Math.max(peak, Math.abs(this.buf[i].pitch - start));
    if (peak >= THRESHOLDS.nodMinDeg && Math.abs(pitchDeg - start) <= THRESHOLDS.nodReturnDeg) {
      this.lastNod = t;
      this.buf = [];
      return true;
    }
    return false;
  }

  reset(): void {
    this.buf = [];
    this.lastNod = -Infinity;
  }
}

function dist(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function inImage(l: NormalizedLandmark): boolean {
  return l.x >= 0 && l.x <= 1 && l.y >= 0 && l.y <= 1;
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}
