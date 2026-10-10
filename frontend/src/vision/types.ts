// Vision types. NonVerbalSample / NonVerbalMetrics mirror backend/schemas/interview.py field for field
// (snake_case on purpose, so the samples can be posted as-is to POST /interview/answer).

export interface Point {
  x: number;
  y: number;
}

/** Blendshapes that rise with a tense or angry face (0..1 each, mean of left and right). */
export interface TensionParts {
  browDown: number;
  noseSneer: number;
  mouthPress: number;
  mouthFrown: number;
}

export interface FaceFrame {
  yawDeg: number;
  pitchDeg: number;
  rollDeg: number;
  /** Where the eyes point inside the head, from the eyeLook* blendshapes: -1..1, + = subject's left / up. */
  gazeX: number;
  gazeY: number;
  /** Nose tip (face landmark 1), normalized image coordinates 0..1. */
  noseX: number;
  noseY: number;
  /** Face bounding box in normalized image coordinates, used for the hand-on-face check. */
  box: { minX: number; minY: number; maxX: number; maxY: number };
  /** Mean of mouthSmileLeft / mouthSmileRight blendshapes, 0..1. */
  smile: number;
  tension: TensionParts;
}

export interface PoseFrame {
  /** True when both shoulders are visible with enough confidence. */
  shoulders: boolean;
  /** Signed tilt of the shoulder line in degrees (0 = level). */
  shoulderTiltDeg: number;
  /** Nose-to-shoulder-midpoint distance divided by shoulder width. Drops when the user slouches. */
  lean: number;
  /** Shoulder width in aspect-corrected image units, used to scale hand speed. */
  shoulderWidth: number;
}

export interface Hand {
  /** "Left" / "Right" as reported by MediaPipe (informational; tracking matches by distance). */
  label: string;
  /** Palm centre, aspect-corrected (x scaled by width / height). */
  center: Point;
  /** Palm centre in plain normalized image coordinates, for comparing with the face box. */
  imageCenter: Point;
  /** Wrist-to-middle-knuckle length, aspect-corrected; fallback scale when shoulders are not visible. */
  size: number;
  /** Index, middle, ring and little fingertips relative to the palm centre, aspect-corrected. */
  tips: Point[];
  /** How many of those four fingers are straight. */
  extendedFingers: number;
  /** All four fingers curled into the palm. */
  fist: boolean;
}

/**
 * What a hand is doing, from rule-based geometry. The first six are distracting habits and count
 * against the score; "gesturing" (open hand, moving) and "resting" do not.
 */
export type HandAction =
  | "touching_face"
  | "covering_mouth"
  | "touching_head"
  | "fiddling"
  | "restless"
  | "fist"
  | "gesturing"
  | "resting";

export const DISTRACTING_ACTIONS: readonly HandAction[] = [
  "covering_mouth",
  "touching_face",
  "touching_head",
  "fiddling",
  "restless",
  "fist",
];

/** Where the user is looking relative to their calibrated "screen" direction, and what the face is doing. */
export interface FaceBaseline {
  yawDeg: number;
  pitchDeg: number;
  gazeX: number;
  gazeY: number;
  smile: number;
  tension: TensionParts;
}

export type GazeState = "contact" | "head_away" | "eyes_away";

/** One second of browser-side vision output (M4 -> M3). Mirrors NonVerbalSample in backend/schemas/interview.py. */
export interface NonVerbalSample {
  t: number;
  head_yaw_deg: number;
  head_pitch_deg: number;
  nose_x: number;
  nose_y: number;
  shoulder_tilt_deg: number;
  forward_lean: number;
  /** Palm speed in shoulder widths per second (from the hand model). */
  wrist_velocity: number;
  /** Smile above the user's neutral face, 0..1. */
  smile: number;
  /** Brow lowering above the user's neutral face, 0..1. */
  brow: number;
  nodded: boolean;
  /** Share of this second's frames with head AND eyes on the screen (vs the user's baseline). */
  eye_contact_frac: number;
  face_detected: boolean;
  pose_detected: boolean;
  hands_visible: boolean;
  /** Strongest of brow-down / nose-wrinkle / lip-press / mouth-frown above the user's neutral face, 0..1. */
  tension: number;
  /** Dominant hand action this second (distracting ones win if they lasted a third of it); null = no hands seen. */
  hand_action: HandAction | null;
}

export type PostureFlag = "slouching" | "leaning_out_of_frame" | "shoulders_tilted";
export type ExpressionLabel = "neutral" | "engaged" | "tense";

/** Per-answer aggregation. Mirrors NonVerbalMetrics in backend/schemas/interview.py. */
export interface NonVerbalMetrics {
  eye_contact_pct: number;
  head_stability: number;
  posture_flags: PostureFlag[];
  fidget_pct: number;
  expression_label: ExpressionLabel;
  nod_count: number;
  body_language_score: number;
  /** Share of the answer's seconds (0-100) spent on each hand action that occurred. */
  hand_actions: Partial<Record<HandAction, number>>;
}

/** The five 0-100 sub-scores that feed body_language_score, shown in the weights tooltip. */
export interface SubScores {
  eyeContact: number;
  posture: number;
  fidget: number;
  stability: number;
  expression: number;
}

/** What the gauges show while the camera is on, refreshed every second. */
export interface LiveVisionState {
  /** Gaze on the latest frame, null when no face. */
  gazeNow: GazeState | null;
  /** Eye contact % over the last few seconds (the ring), null before the first second. */
  eyeContactRecentPct: number | null;
  postureIssue: PostureFlag | null;
  /** Fidget % over the last few seconds. */
  fidgetRecentPct: number | null;
  expression: ExpressionLabel | null;
  handsInView: number;
  /** Hand action over the last second, null when no hands are visible. */
  handAction: HandAction | null;
  faceDetected: boolean;
  calibrated: boolean;
  fps: number;
}

/** Raw numbers for threshold tuning (shown in the playground's debug panel), relative to the baseline. */
export interface VisionDebug {
  yawDeg: number | null;
  pitchDeg: number | null;
  gazeX: number | null;
  gazeY: number | null;
  smile: number | null;
  tension: number | null;
  tensionSource: keyof TensionParts | null;
  hands: number;
  handSpeed: number | null;
  fingerSpeed: number | null;
  extendedFingers: number | null;
  handAction: HandAction | null;
  shoulderTiltDeg: number | null;
  lean: number | null;
  leanBaseline: number;
  noseY: number | null;
}
