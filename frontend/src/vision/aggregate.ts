// Frames (~15 fps) -> one NonVerbalSample per second -> NonVerbalMetrics per answer.
// analyzeAnswer() is the browser copy of backend/services/interview/nonverbal.py's analyze_answer();
// the browser uses it for the live gauges, the backend's result is the one that is stored.

import { bodyLanguageScore, round, subScores } from "./bodyLanguageScore";
import { clamp } from "./metrics";
import { THRESHOLDS } from "./thresholds";
import {
  DISTRACTING_ACTIONS,
  type ExpressionLabel,
  type FaceBaseline,
  type FaceFrame,
  type GazeState,
  type HandAction,
  type NonVerbalMetrics,
  type NonVerbalSample,
  type PoseFrame,
  type PostureFlag,
  type SubScores,
  type TensionParts,
} from "./types";

/** A frame after the stateful trackers have run on it. */
export interface ProcessedFrame {
  t: number;
  face: FaceFrame | null;
  /** undefined = pose not run on this frame (pose and hands alternate frames). */
  pose?: PoseFrame | null;
  /** undefined = hand model not run on this frame. */
  hands?: { count: number; speed: number | null; action: HandAction | null };
  nod: boolean;
}

/** Most distracting first; a frame with two hands reports the worse one. */
export const HAND_ACTION_ORDER: HandAction[] = [...DISTRACTING_ACTIONS, "gesturing", "resting"];

export function worstAction(actions: HandAction[]): HandAction | null {
  for (const a of HAND_ACTION_ORDER) if (actions.includes(a)) return a;
  return null;
}

// --------------------------------------------------------------------------- per-user baseline

const TENSION_KEYS: (keyof TensionParts)[] = ["browDown", "noseSneer", "mouthPress", "mouthFrown"];

/**
 * Learns this user's "looking at the screen" head angle and eye direction, and their neutral face.
 * A laptop camera sits above the screen, so reading the question tilts the head and eyes down;
 * and blendshape levels differ from face to face, so tension is measured above the user's own neutral.
 * Watches the last ~3 s continuously and freezes when an answer starts.
 */
export class Calibrator {
  private window: FaceFrame[] = [];
  private frozen: FaceBaseline | null = null;
  private freezeWhenReady = false;

  observe(face: FaceFrame | null): void {
    if (this.frozen || !face) return;
    this.window.push(face);
    if (this.window.length > 45) this.window.shift();
    if (this.freezeWhenReady && this.window.length >= THRESHOLDS.calibrationFrames) this.frozen = this.provisional();
  }

  /** Lock the baseline for the answer; if there is not enough data yet, lock as soon as there is. */
  freeze(): void {
    if (this.window.length >= THRESHOLDS.calibrationFrames) this.frozen = this.provisional();
    else this.freezeWhenReady = true;
  }

  reset(): void {
    this.window = [];
    this.frozen = null;
    this.freezeWhenReady = false;
  }

  get baseline(): FaceBaseline | null {
    return this.frozen ?? (this.window.length >= THRESHOLDS.calibrationFrames ? this.provisional() : null);
  }

  private provisional(): FaceBaseline {
    const T = THRESHOLDS;
    const med = (f: (x: FaceFrame) => number) => median(this.window.map(f));
    const tension = {} as TensionParts;
    for (const k of TENSION_KEYS) tension[k] = clamp(med((x) => x.tension[k]), 0, T.baselineMaxTension);
    return {
      yawDeg: clamp(med((x) => x.yawDeg), -T.baselineMaxDeg, T.baselineMaxDeg),
      pitchDeg: clamp(med((x) => x.pitchDeg), -T.baselineMaxDeg, T.baselineMaxDeg),
      gazeX: clamp(med((x) => x.gazeX), -T.baselineMaxGaze, T.baselineMaxGaze),
      gazeY: clamp(med((x) => x.gazeY), -T.baselineMaxGaze, T.baselineMaxGaze),
      smile: clamp(med((x) => x.smile), 0, T.baselineMaxSmile),
      tension,
    };
  }
}

const NEUTRAL: FaceBaseline = {
  yawDeg: 0,
  pitchDeg: 0,
  gazeX: 0,
  gazeY: 0,
  smile: 0,
  tension: { browDown: 0, noseSneer: 0, mouthPress: 0, mouthFrown: 0 },
};

/** Eye contact needs both the head and the eyes on the screen. */
export function gazeState(face: FaceFrame, baseline: FaceBaseline | null): GazeState {
  const b = baseline ?? NEUTRAL;
  const T = THRESHOLDS;
  if (Math.abs(face.yawDeg - b.yawDeg) > T.eyeContactDeg || Math.abs(face.pitchDeg - b.pitchDeg) > T.eyeContactDeg)
    return "head_away";
  if (Math.abs(face.gazeX - b.gazeX) > T.gazeMax || Math.abs(face.gazeY - b.gazeY) > T.gazeMax) return "eyes_away";
  return "contact";
}

export function isEyeContact(face: FaceFrame | null, baseline: FaceBaseline | null): boolean {
  return face !== null && gazeState(face, baseline) === "contact";
}

/** Strongest tension blendshape above the user's neutral face, and which one it was. */
export function tensionLevel(face: FaceFrame, baseline: FaceBaseline | null): { level: number; source: keyof TensionParts } {
  const b = (baseline ?? NEUTRAL).tension;
  let level = 0;
  let source: keyof TensionParts = "browDown";
  for (const k of TENSION_KEYS) {
    const v = face.tension[k] - b[k];
    if (v > level) [level, source] = [v, k];
  }
  return { level: clamp(level, 0, 1), source };
}

export function smileLevel(face: FaceFrame, baseline: FaceBaseline | null): number {
  return clamp(face.smile - (baseline ?? NEUTRAL).smile, 0, 1);
}

// --------------------------------------------------------------------------- frames -> 1 s sample

export function summarizeSecond(frames: ProcessedFrame[], t: number, baseline: FaceBaseline | null): NonVerbalSample {
  const faces = frames.map((f) => f.face).filter((f): f is FaceFrame => f !== null);
  const poseRuns = frames.filter((f) => f.pose !== undefined);
  const shoulders = poseRuns.map((f) => f.pose).filter((p): p is PoseFrame => !!p?.shoulders);
  const handRuns = frames.map((f) => f.hands).filter((h) => h !== undefined);
  const withHands = handRuns.filter((h) => h.count > 0);
  const speeds = withHands.map((h) => h.speed).filter((v): v is number => v !== null);
  const browBase = (baseline ?? NEUTRAL).tension.browDown;

  return {
    t,
    head_yaw_deg: r4(mean(faces.map((f) => f.yawDeg))),
    head_pitch_deg: r4(mean(faces.map((f) => f.pitchDeg))),
    nose_x: r4(mean(faces.map((f) => f.noseX))),
    nose_y: r4(mean(faces.map((f) => f.noseY))),
    shoulder_tilt_deg: r4(mean(shoulders.map((p) => p.shoulderTiltDeg))),
    forward_lean: r4(mean(shoulders.map((p) => p.lean))),
    wrist_velocity: r4(mean(speeds)),
    smile: r4(mean(faces.map((f) => smileLevel(f, baseline)))),
    brow: r4(clamp(mean(faces.map((f) => f.tension.browDown - browBase)), 0, 1)),
    tension: r4(mean(faces.map((f) => tensionLevel(f, baseline).level))),
    nodded: frames.some((f) => f.nod),
    eye_contact_frac: r4(frames.length ? frames.filter((f) => isEyeContact(f.face, baseline)).length / frames.length : 0),
    face_detected: frames.length > 0 && faces.length * 2 >= frames.length,
    pose_detected: poseRuns.length > 0 && shoulders.length * 2 >= poseRuns.length,
    hands_visible: handRuns.length > 0 && withHands.length * 3 >= handRuns.length,
    hand_action: secondHandAction(withHands.map((h) => h.action).filter((a): a is HandAction => a !== null)),
  };
}

/**
 * The second's hand action: a distracting action wins if it was seen on at least a third of the
 * frames with hands (a brief face touch still counts); otherwise the most common of gesturing / resting.
 */
export function secondHandAction(actions: HandAction[]): HandAction | null {
  if (!actions.length) return null;
  const count = (a: HandAction) => actions.filter((x) => x === a).length;
  for (const a of DISTRACTING_ACTIONS) if (count(a) >= THRESHOLDS.handActionShare * actions.length) return a;
  return count("gesturing") >= count("resting") ? "gesturing" : "resting";
}

/** Groups frames into whole seconds relative to `startMs` and emits a sample when a second closes. */
export class SecondAggregator {
  private frames: ProcessedFrame[] = [];
  private second = 0;

  constructor(private startMs: number) {}

  /** Returns the finished sample when this frame starts a new second, else null. */
  push(frame: ProcessedFrame, baseline: FaceBaseline | null): NonVerbalSample | null {
    const sec = Math.floor((frame.t - this.startMs) / 1000);
    let done: NonVerbalSample | null = null;
    if (sec > this.second && this.frames.length) {
      done = summarizeSecond(this.frames, this.second, baseline);
      this.frames = [];
    }
    if (sec > this.second) this.second = sec;
    this.frames.push(frame);
    return done;
  }

  /** Summarizes the partial last second (when the answer stops), if it has at least a few frames. */
  flush(baseline: FaceBaseline | null, minFrames = 5): NonVerbalSample | null {
    if (this.frames.length < minFrames) return null;
    const s = summarizeSecond(this.frames, this.second, baseline);
    this.frames = [];
    return s;
  }
}

// --------------------------------------------------------------------------- samples -> answer metrics

export interface AnswerAnalysis {
  metrics: NonVerbalMetrics;
  subScores: SubScores;
}

/** Per-answer metrics; null when there are no samples (verbal-only mode). */
export function aggregateAnswer(samples: NonVerbalSample[]): NonVerbalMetrics | null {
  return analyzeAnswer(samples)?.metrics ?? null;
}

export function analyzeAnswer(samples: NonVerbalSample[]): AnswerAnalysis | null {
  const n = samples.length;
  if (!n) return null;
  const faces = samples.filter((s) => s.face_detected);

  const eyeContactPct = 100 * mean(samples.map((s) => s.eye_contact_frac));
  const headVariance = variance(faces.map((s) => s.nose_x)) + variance(faces.map((s) => s.nose_y));

  const posture = postureAnalysis(samples);
  const fidgetPct = (100 * samples.filter(isFidgetSecond).length) / n;
  const expression = expressionFromSamples(samples);

  const handActions: Partial<Record<HandAction, number>> = {};
  for (const a of HAND_ACTION_ORDER) {
    const c = samples.filter((s) => s.hand_action === a).length;
    if (c) handActions[a] = round((100 * c) / n, 1);
  }

  let nods = 0;
  samples.forEach((s, i) => {
    if (s.nodded && !(i > 0 && samples[i - 1].nodded)) nods += 1;
  });

  const inputs = {
    eyeContactPct,
    postureProblemShare: posture.problemShare,
    fidgetPct,
    headVariance,
    expression,
  };
  return {
    metrics: {
      eye_contact_pct: round(eyeContactPct, 1),
      head_stability: round(headVariance, 6),
      posture_flags: posture.flags,
      fidget_pct: round(fidgetPct, 1),
      expression_label: expression,
      nod_count: nods,
      body_language_score: bodyLanguageScore(inputs),
      hand_actions: handActions,
    },
    subScores: subScores(inputs),
  };
}

export function isOutOfFrame(s: NonVerbalSample): boolean {
  if (!s.face_detected) return true;
  const { frameMarginX: mx, frameMarginY: my } = THRESHOLDS;
  return s.nose_x < mx || s.nose_x > 1 - mx || s.nose_y < my || s.nose_y > 1 - my;
}

export function isTilted(s: NonVerbalSample): boolean {
  return s.pose_detected && Math.abs(s.shoulder_tilt_deg) > THRESHOLDS.shoulderTiltDeg;
}

/** Slouching = sunk lower than at the start of the answer, or simply sitting very low in the frame. */
export function isSlouching(s: NonVerbalSample, baselineLean: number): boolean {
  if (s.face_detected && s.nose_y > THRESHOLDS.slouchNoseY) return true;
  return s.pose_detected && baselineLean > 0 && s.forward_lean < THRESHOLDS.slouchRatio * baselineLean;
}

/** A second with a distracting hand action (touching face, fiddling, restless hands, fist...). */
export function isFidgetSecond(s: NonVerbalSample): boolean {
  return s.hand_action !== null && DISTRACTING_ACTIONS.includes(s.hand_action);
}

/** Median lean of the first few seconds with shoulders visible: "sitting normally" for this answer. */
export function postureBaseline(samples: NonVerbalSample[]): number {
  const first = samples.filter((s) => s.pose_detected).slice(0, THRESHOLDS.postureBaselineSeconds);
  return first.length ? median(first.map((s) => s.forward_lean)) : 0;
}

function postureAnalysis(samples: NonVerbalSample[]): { flags: PostureFlag[]; problemShare: number } {
  const n = samples.length;
  const base = postureBaseline(samples);
  let out = 0;
  let tilt = 0;
  let slouch = 0;
  let problem = 0;
  for (const s of samples) {
    const o = isOutOfFrame(s);
    const t = isTilted(s);
    const sl = isSlouching(s, base);
    out += +o;
    tilt += +t;
    slouch += +sl;
    problem += +(o || t || sl);
  }
  const flags: PostureFlag[] = [];
  if (slouch / n >= THRESHOLDS.slouchFlagShare) flags.push("slouching");
  if (out / n >= THRESHOLDS.outOfFrameFlagShare) flags.push("leaning_out_of_frame");
  if (tilt / n >= THRESHOLDS.tiltFlagShare) flags.push("shoulders_tilted");
  return { flags, problemShare: problem / n };
}

/**
 * Label from the share of face-visible seconds that were tense / smiling. A short frown is enough to
 * be noticed: a quarter of the answer makes it "tense", even if the rest was neutral.
 */
export function expressionFromSamples(samples: NonVerbalSample[]): ExpressionLabel {
  const faces = samples.filter((s) => s.face_detected);
  if (!faces.length) return "neutral";
  const tense = faces.filter((s) => s.tension >= THRESHOLDS.tenseLevel).length / faces.length;
  const smiling = faces.filter((s) => s.smile >= THRESHOLDS.engagedSmile).length / faces.length;
  if (tense >= THRESHOLDS.tenseShare && tense >= smiling) return "tense";
  if (smiling >= THRESHOLDS.engagedShare) return "engaged";
  return "neutral";
}

// --------------------------------------------------------------------------- small math helpers

export function mean(xs: number[]): number {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
}

/** Population variance; 0 for fewer than two values. */
export function variance(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return mean(xs.map((x) => (x - m) ** 2));
}

export function median(xs: number[]): number {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const mid = s.length >> 1;
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

function r4(v: number): number {
  return round(v, 4);
}
