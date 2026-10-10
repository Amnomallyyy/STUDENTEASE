// Every tunable number in the vision pipeline. backend/services/interview/nonverbal.py keeps the same
// values; the shared fixture test fails if the two drift apart. Tune with the playground's debug panel.

export const THRESHOLDS = {
  /** Head within this many degrees of the baseline (yaw and pitch) counts as facing the screen. */
  eyeContactDeg: 15,
  /** Eyes within this much of the baseline (eyeLook* blendshape units, -1..1) count as looking at the screen. */
  gazeMax: 0.3,
  /** Baselines are clamped so a user who looks away or frowns while calibrating cannot break them. */
  baselineMaxDeg: 20,
  baselineMaxGaze: 0.4,
  baselineMaxSmile: 0.3,
  baselineMaxTension: 0.25,
  /** Frames needed before the baseline is trusted (~1.5 s at 15 fps). */
  calibrationFrames: 20,

  /** Landmark visibility needed to use a pose point. */
  minVisibility: 0.5,
  /** Shoulder width below this (aspect-corrected) is treated as "no shoulders" (too far away / cropped). */
  minShoulderWidth: 0.05,
  /** Hand-model confidence; high enough that shoulders or clothing are not read as hands. */
  minHandConfidence: 0.6,

  /** |shoulder tilt| above this many degrees counts as tilted. */
  shoulderTiltDeg: 8,
  /** Lean ratio below this share of the answer's baseline counts as slouching. */
  slouchRatio: 0.8,
  /** Nose lower than this in the frame counts as slouching even if the user slouched from the start. */
  slouchNoseY: 0.65,
  /** Seconds at the start of an answer used as the posture baseline. */
  postureBaselineSeconds: 3,
  /** Nose outside this normalized box counts as leaving the frame. */
  frameMarginX: 0.08,
  frameMarginY: 0.05,

  /** Palm speed (shoulder widths per second) above this, without an open hand, counts as restless. */
  fidgetVelocity: 0.5,
  /** Smoothing for palm speed, to stop landmark jitter reading as fidgeting. */
  handSmoothing: 0.4,
  /** Palm length is roughly this share of shoulder width; used to scale speed when shoulders are hidden. */
  palmToShoulder: 0.25,
  /** Face box is grown by this share on each side for the hand-on-face check. */
  faceBoxMargin: 0.1,
  /** A palm in the lower part of the face box (this share of its height) is covering the mouth. */
  mouthShare: 0.4,
  /** Beyond the face box but within this share of the face size around/above it = touching hair, head or neck. */
  headMargin: 0.5,
  /** Finger counts as straight when tip-to-wrist is this many times knuckle(PIP)-to-wrist. */
  fingerExtendRatio: 1.2,
  /** Finger counts as curled into a fist when tip-to-wrist is under this many times base-knuckle(MCP)-to-wrist. */
  fistRatio: 1.3,
  /** Fingertip speed relative to the palm (shoulder widths / s) above this, with the palm still, = fiddling. */
  fiddleVelocity: 0.6,
  /** Open hand moving at least this fast (shoulder widths / s) = a gesture. */
  gestureMinVelocity: 0.15,
  /** A distracting action wins the second if it is seen on at least this share of the frames with hands. */
  handActionShare: 1 / 3,

  /** Nose-position standard deviation (normalized units): at or below `stableStd` scores 100, at `unstableStd` scores 0. */
  stableStd: 0.01,
  unstableStd: 0.06,

  /** Expression: per-second smile / tension above the user's neutral face that counts. */
  engagedSmile: 0.2,
  tenseLevel: 0.15,
  /** Share of face-visible seconds needed for the "engaged" / "tense" label. */
  engagedShare: 0.2,
  tenseShare: 0.25,

  /** A nod is a pitch excursion of at least this many degrees that returns within `nodWindowMs`. */
  nodMinDeg: 5,
  nodReturnDeg: 2,
  nodWindowMs: 1200,
  nodCooldownMs: 500,

  /** A posture flag is raised when it holds for at least this share of the answer. */
  tiltFlagShare: 0.25,
  slouchFlagShare: 0.25,
  outOfFrameFlagShare: 0.15,

  /** Seconds used for the live "recent" gauges. */
  recentWindowSeconds: 3,
} as const;

/** Body-language weights (outline section 3). Shown to the user in the score tooltip. */
export const WEIGHTS = {
  eyeContact: 0.35,
  posture: 0.25,
  fidget: 0.2,
  stability: 0.1,
  expression: 0.1,
} as const;

/** Expression sub-score per label: coaching, not judging. */
export const EXPRESSION_SCORES = { engaged: 100, neutral: 75, tense: 30 } as const;
