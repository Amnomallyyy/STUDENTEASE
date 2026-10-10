import type { Matrix, NormalizedLandmark } from "@mediapipe/tasks-vision";
import { describe, expect, it } from "vitest";
import fixtures from "../__fixtures__/answers.json";
import {
  analyzeAnswer,
  Calibrator,
  expressionFromSamples,
  gazeState,
  isEyeContact,
  SecondAggregator,
  secondHandAction,
  summarizeSecond,
  tensionLevel,
  type ProcessedFrame,
} from "../aggregate";
import { bodyLanguageScore, stabilityScore } from "../bodyLanguageScore";
import {
  classifyHand,
  extractFace,
  extractHands,
  extractPose,
  gazeFromBlendshapes,
  HandTracker,
  headAnglesFromMatrix,
  lineTiltDeg,
  NodDetector,
} from "../metrics";
import type { FaceBaseline, FaceFrame, Hand, NonVerbalSample, PoseFrame } from "../types";

const DEG = Math.PI / 180;

/** Column-major 4x4 for R = Ry(yaw) * Rx(pitch), with a uniform scale to check normalization. */
function poseMatrix(yawDeg: number, pitchDeg: number, scale = 1): Matrix {
  const cy = Math.cos(yawDeg * DEG), sy = Math.sin(yawDeg * DEG);
  const cp = Math.cos(pitchDeg * DEG), sp = Math.sin(pitchDeg * DEG);
  const r = [
    [cy, sy * sp, sy * cp],
    [0, cp, -sp],
    [-sy, cy * sp, cy * cp],
  ];
  const data: number[] = [];
  for (let c = 0; c < 4; c++) for (let row = 0; row < 4; row++) data.push(c < 3 && row < 3 ? r[row][c] * scale : row === c ? 1 : 0);
  return { rows: 4, columns: 4, data };
}

function lm(x: number, y: number, visibility = 1): NormalizedLandmark {
  return { x, y, z: 0, visibility };
}

function shapes(scores: Record<string, number>) {
  return {
    headIndex: 0,
    headName: "",
    categories: Object.entries(scores).map(([categoryName, score], index) => ({ categoryName, score, index, displayName: "" })),
  };
}

function poseLandmarks(overrides: Record<number, NormalizedLandmark> = {}): NormalizedLandmark[] {
  const pts = Array.from({ length: 33 }, () => lm(0.5, 0.5, 0));
  pts[0] = lm(0.5, 0.3); // nose
  pts[11] = lm(0.65, 0.6); // left shoulder (image right)
  pts[12] = lm(0.35, 0.6); // right shoulder
  return Object.assign(pts, overrides);
}

/** 21 hand points around (cx, cy): fingers straight up when open, folded onto the palm when closed. */
function handLandmarks(cx: number, cy: number, open: boolean, s = 0.05): NormalizedLandmark[] {
  const pts: NormalizedLandmark[] = Array.from({ length: 21 }, () => lm(cx, cy));
  pts[0] = lm(cx, cy + 2 * s); // wrist
  pts[1] = lm(cx - s, cy + s);
  pts[2] = lm(cx - 1.4 * s, cy + 0.5 * s);
  pts[3] = lm(cx - 1.7 * s, cy);
  pts[4] = lm(cx - 2 * s, cy - 0.3 * s);
  [5, 9, 13, 17].forEach((mcp, i) => {
    const x = cx - s + (i * 2 * s) / 3;
    pts[mcp] = lm(x, cy);
    pts[mcp + 1] = lm(x, cy - s); // PIP
    pts[mcp + 2] = open ? lm(x, cy - 1.6 * s) : lm(x, cy - 0.4 * s);
    pts[mcp + 3] = open ? lm(x, cy - 2.2 * s) : lm(x, cy + 0.4 * s); // tip
  });
  return pts;
}

const face = (yawDeg: number, pitchDeg: number, extra: Partial<FaceFrame> = {}): FaceFrame => ({
  yawDeg,
  pitchDeg,
  rollDeg: 0,
  gazeX: 0,
  gazeY: 0,
  noseX: 0.5,
  noseY: 0.45,
  box: { minX: 0.4, minY: 0.25, maxX: 0.6, maxY: 0.55 },
  smile: 0.05,
  tension: { browDown: 0.05, noseSneer: 0, mouthPress: 0.05, mouthFrown: 0 },
  ...extra,
});

describe("head angles and eyes", () => {
  it("recovers yaw and pitch from a column-major transform, ignoring scale", () => {
    const a = headAnglesFromMatrix(poseMatrix(20, -10, 3.2));
    expect(a.yawDeg).toBeCloseTo(20, 4);
    expect(a.pitchDeg).toBeCloseTo(-10, 4);
    expect(a.rollDeg).toBeCloseTo(0, 4);
  });

  it("reads eye direction from the eyeLook blendshapes", () => {
    // Both eyes looking to the subject's left: Out on the left eye, In on the right eye.
    expect(gazeFromBlendshapes({ eyeLookOutLeft: 0.6, eyeLookInRight: 0.6 }).gazeX).toBeCloseTo(0.6);
    expect(gazeFromBlendshapes({ eyeLookDownLeft: 0.5, eyeLookDownRight: 0.5 }).gazeY).toBeCloseTo(-0.5);
  });

  it("reads smile and the tension blendshapes", () => {
    const landmarks = Array.from({ length: 478 }, () => lm(0.5, 0.4));
    const f = extractFace(
      landmarks,
      shapes({ mouthSmileLeft: 0.6, mouthSmileRight: 0.4, browDownLeft: 0.2, browDownRight: 0.4, mouthPressLeft: 0.5, mouthPressRight: 0.5 }),
      poseMatrix(0, 0),
    )!;
    expect(f.smile).toBeCloseTo(0.5);
    expect(f.tension.browDown).toBeCloseTo(0.3);
    expect(f.tension.mouthPress).toBeCloseTo(0.5);
    expect(extractFace(undefined, undefined, undefined)).toBeNull();
  });
});

describe("pose geometry", () => {
  it("measures level shoulders and the lean ratio", () => {
    const p = extractPose(poseLandmarks(), 1)!;
    expect(p.shoulders).toBe(true);
    expect(p.shoulderTiltDeg).toBeCloseTo(0);
    expect(p.shoulderWidth).toBeCloseTo(0.3);
    expect(p.lean).toBeCloseTo(1); // nose 0.3 above the shoulder midpoint, shoulders 0.3 apart
  });

  it("corrects for aspect ratio and ignores point order", () => {
    // 0.1 high over 0.3 wide on a 4:3 video: atan(0.1 / 0.4) = 14.04 deg
    const p = extractPose(poseLandmarks({ 11: lm(0.65, 0.55), 12: lm(0.35, 0.65) }), 4 / 3)!;
    expect(Math.abs(p.shoulderTiltDeg)).toBeCloseTo(14.04, 1);
    expect(lineTiltDeg({ x: 0, y: 0 }, { x: 1, y: 1 })).toBeCloseTo(lineTiltDeg({ x: 1, y: 1 }, { x: 0, y: 0 }));
  });

  it("drops low-visibility shoulders", () => {
    expect(extractPose(poseLandmarks({ 12: lm(0.35, 0.6, 0.2) }), 1)!.shoulders).toBe(false);
  });
});

describe("hands", () => {
  const hand = (cx: number, cy: number, open: boolean): Hand => extractHands([handLandmarks(cx, cy, open)], undefined, 1)[0];

  it("tells an open hand from a fist", () => {
    expect(hand(0.3, 0.8, true).extendedFingers).toBe(4);
    expect(hand(0.3, 0.8, true).fist).toBe(false);
    expect(hand(0.3, 0.8, false).extendedFingers).toBe(0);
    expect(hand(0.3, 0.8, false).fist).toBe(true);
  });

  it("classifies face, mouth and head touches before anything else", () => {
    const f = face(0, 0); // box x 0.4-0.6, y 0.25-0.55
    const still = { palm: 0, fingers: 0 };
    expect(classifyHand(hand(0.5, 0.5, true), still, f)).toBe("covering_mouth");
    expect(classifyHand(hand(0.45, 0.32, true), still, f)).toBe("touching_face");
    expect(classifyHand(hand(0.66, 0.2, true), still, f)).toBe("touching_head");
  });

  it("classifies what hands away from the face are doing", () => {
    const f = face(0, 0);
    expect(classifyHand(hand(0.3, 0.85, false), { palm: 0.1, fingers: 0.9 }, f)).toBe("fiddling");
    expect(classifyHand(hand(0.3, 0.85, false), { palm: 0.9, fingers: 0 }, f)).toBe("restless");
    expect(classifyHand(hand(0.3, 0.85, false), { palm: 0, fingers: 0 }, f)).toBe("fist");
    expect(classifyHand(hand(0.3, 0.85, true), { palm: 0.9, fingers: 0 }, f)).toBe("gesturing");
    expect(classifyHand(hand(0.3, 0.85, true), { palm: 0.02, fingers: 0 }, f)).toBe("resting");
  });

  it("tracks palm and finger speed in shoulder widths per second", () => {
    const t = new HandTracker();
    expect(t.update(0, [hand(0.5, 0.8, true)], 0.2)[0].palm).toBeNull(); // first sight
    const m = t.update(100, [hand(0.52, 0.8, true)], 0.2)[0]; // 0.02 in 0.1 s = 0.2/s = 1 shoulder width/s
    expect(m.palm).toBeCloseTo(1);
    expect(m.fingers).toBeCloseTo(0); // fingers moved with the palm
    const closing = t.update(200, [hand(0.52, 0.8, false)], 0.2)[0]; // fingers fold while the palm stays
    expect(closing.fingers!).toBeGreaterThan(0);
  });

  it("does not match a hand that jumped more than a shoulder width (a different hand)", () => {
    const t = new HandTracker();
    t.update(0, [hand(0.1, 0.8, true)], 0.2);
    expect(t.update(100, [hand(0.9, 0.8, true)], 0.2)[0].palm).toBeNull();
  });

  it("picks the second's action: distracting wins at a third of the frames", () => {
    expect(secondHandAction(["resting", "resting", "touching_face"])).toBe("touching_face");
    expect(secondHandAction(["resting", "resting", "resting", "touching_face"])).toBe("resting");
    expect(secondHandAction(["gesturing", "gesturing", "resting"])).toBe("gesturing");
    expect(secondHandAction([])).toBeNull();
  });
});

describe("nod detector", () => {
  it("fires on a down-and-back pitch movement and not on a held look-down", () => {
    const n = new NodDetector();
    const nod = [-8, -11, -15, -11, -8].map((p, i) => n.update(i * 100, p));
    expect(nod.filter(Boolean)).toHaveLength(1);

    const held = new NodDetector();
    const look = [-8, -12, -16, -20, -20, -20].map((p, i) => held.update(i * 100, p));
    expect(look.some(Boolean)).toBe(false);
  });
});

describe("calibration, eye contact and expression", () => {
  const calibrated = (f: FaceFrame) => {
    const c = new Calibrator();
    for (let i = 0; i < 25; i++) c.observe(f);
    c.freeze();
    return c;
  };

  it("measures head and eyes against the user's own baseline", () => {
    const c = calibrated(face(3, -12, { gazeY: -0.3 })); // reading the screen below a laptop camera
    const b = c.baseline!;
    expect(b.pitchDeg).toBeCloseTo(-12);
    expect(gazeState(face(3, -12, { gazeY: -0.3 }), b)).toBe("contact");
    expect(gazeState(face(3, 4, { gazeY: -0.3 }), b)).toBe("head_away"); // 16 deg off
    expect(gazeState(face(3, -12, { gazeX: 0.45, gazeY: -0.3 }), b)).toBe("eyes_away"); // head still, eyes to the side
    expect(isEyeContact(face(3, 4), null)).toBe(true); // camera-axis fallback before calibration
    c.observe(face(40, 40));
    expect(c.baseline!.yawDeg).toBeCloseTo(3); // frozen during the answer
  });

  it("clamps a baseline learned while looking away or frowning", () => {
    const b = calibrated(face(45, 0, { tension: { browDown: 0.9, noseSneer: 0, mouthPress: 0, mouthFrown: 0 } })).baseline!;
    expect(b.yawDeg).toBe(20);
    expect(b.tension.browDown).toBe(0.25); // a constant frown still shows up as tension
  });

  it("measures tension above the neutral face and reports its source", () => {
    const b: FaceBaseline = calibrated(face(0, 0)).baseline!;
    const angry = face(0, 0, { tension: { browDown: 0.3, noseSneer: 0.1, mouthPress: 0.55, mouthFrown: 0 } });
    const t = tensionLevel(angry, b);
    expect(t.source).toBe("mouthPress");
    expect(t.level).toBeCloseTo(0.5);
  });

  it("labels an answer tense when a quarter of it is tense", () => {
    const base = fixtures.calm.samples[0] as NonVerbalSample;
    const seconds = (tense: number, n: number) =>
      Array.from({ length: n }, (_, i) => ({ ...base, smile: 0, tension: i < tense ? 0.3 : 0 }));
    expect(expressionFromSamples(seconds(2, 10))).toBe("neutral"); // 20%
    expect(expressionFromSamples(seconds(2, 8))).toBe("tense"); // 25%
  });
});

describe("frames -> seconds", () => {
  const pf = (t: number, f: FaceFrame | null, extra: Partial<ProcessedFrame> = {}): ProcessedFrame => ({ t, face: f, nod: false, ...extra });
  const goodPose: PoseFrame = { shoulders: true, shoulderTiltDeg: 2, lean: 0.9, shoulderWidth: 0.3 };

  it("summarizes a second: eye-contact share, pose, hands and action", () => {
    const frames = [
      pf(0, face(0, 0), { pose: goodPose }),
      pf(66, face(30, 0), { hands: { count: 1, speed: 0.2, action: "touching_face" } }),
      pf(133, face(0, 0, { gazeX: 0.5 }), { pose: goodPose }),
      pf(200, null, { hands: { count: 1, speed: 0.4, action: "resting" } }),
    ];
    const s = summarizeSecond(frames, 0, null);
    expect(s.eye_contact_frac).toBeCloseTo(0.25); // only the first frame has head AND eyes on screen
    expect(s.face_detected).toBe(true);
    expect(s.head_yaw_deg).toBeCloseTo(10);
    expect(s.pose_detected).toBe(true);
    expect(s.forward_lean).toBeCloseTo(0.9);
    expect(s.hands_visible).toBe(true);
    expect(s.wrist_velocity).toBeCloseTo(0.3);
    expect(s.hand_action).toBe("touching_face");
  });

  it("emits one sample per whole second and flushes the remainder", () => {
    const agg = new SecondAggregator(1000);
    const out: NonVerbalSample[] = [];
    for (let t = 1000; t < 3500; t += 66) {
      const s = agg.push(pf(t, face(0, 0)), null);
      if (s) out.push(s);
    }
    expect(out.map((s) => s.t)).toEqual([0, 1]);
    expect(agg.flush(null)?.t).toBe(2);
  });
});

describe("answer aggregation matches backend/services/interview/nonverbal.py", () => {
  type Case = { samples: NonVerbalSample[]; expected: { metrics: Record<string, unknown>; sub_scores: Record<string, number> } };
  const cases = Object.entries(fixtures).filter(([k]) => !k.startsWith("_")) as unknown as [string, Case][];

  it.each(cases)("%s", (_name, { samples, expected }) => {
    const result = analyzeAnswer(samples)!;
    expect(result.metrics).toEqual(expected.metrics);
    expect(result.subScores.eyeContact).toBeCloseTo(expected.sub_scores.eye_contact, 6);
    expect(result.subScores.posture).toBeCloseTo(expected.sub_scores.posture, 6);
    expect(result.subScores.fidget).toBeCloseTo(expected.sub_scores.fidget, 6);
    expect(result.subScores.stability).toBeCloseTo(expected.sub_scores.stability, 6);
    expect(result.subScores.expression).toBeCloseTo(expected.sub_scores.expression, 6);
  });

  it("returns null in verbal-only mode", () => {
    expect(analyzeAnswer([])).toBeNull();
  });
});

describe("score", () => {
  it("uses the published weights", () => {
    // 0.35*80 + 0.25*100 + 0.20*90 + 0.10*100 + 0.10*75 = 88.5
    expect(
      bodyLanguageScore({ eyeContactPct: 80, postureProblemShare: 0, fidgetPct: 10, headVariance: 0, expression: "neutral" }),
    ).toBe(88.5);
  });

  it("maps head movement to stability linearly between the thresholds", () => {
    expect(stabilityScore(0.01 ** 2)).toBe(100);
    expect(stabilityScore(0.035 ** 2)).toBeCloseTo(50);
    expect(stabilityScore(0.1 ** 2)).toBe(0);
  });
});
