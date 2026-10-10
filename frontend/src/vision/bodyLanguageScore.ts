// Body-language score (0-100) from the five sub-scores. Weights are in thresholds.ts and are shown
// in the UI tooltip; backend/services/interview/nonverbal.py computes the same thing server-side.

import { clamp } from "./metrics";
import { EXPRESSION_SCORES, THRESHOLDS, WEIGHTS } from "./thresholds";
import type { ExpressionLabel, SubScores } from "./types";

export interface ScoreInputs {
  eyeContactPct: number;
  /** Share of seconds (0..1) with any posture problem: out of frame, tilted shoulders or slouching. */
  postureProblemShare: number;
  fidgetPct: number;
  /** Variance of nose position (var_x + var_y). */
  headVariance: number;
  expression: ExpressionLabel;
}

export function stabilityScore(headVariance: number): number {
  const std = Math.sqrt(Math.max(0, headVariance));
  const { stableStd, unstableStd } = THRESHOLDS;
  return 100 * clamp(1 - (std - stableStd) / (unstableStd - stableStd), 0, 1);
}

export function subScores(inputs: ScoreInputs): SubScores {
  return {
    eyeContact: clamp(inputs.eyeContactPct, 0, 100),
    posture: 100 * clamp(1 - inputs.postureProblemShare, 0, 1),
    fidget: clamp(100 - inputs.fidgetPct, 0, 100),
    stability: stabilityScore(inputs.headVariance),
    expression: EXPRESSION_SCORES[inputs.expression],
  };
}

export function weightedScore(s: SubScores): number {
  const total =
    WEIGHTS.eyeContact * s.eyeContact +
    WEIGHTS.posture * s.posture +
    WEIGHTS.fidget * s.fidget +
    WEIGHTS.stability * s.stability +
    WEIGHTS.expression * s.expression;
  return round(clamp(total, 0, 100), 1);
}

export function bodyLanguageScore(inputs: ScoreInputs): number {
  return weightedScore(subScores(inputs));
}

export function round(v: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(v * f) / f;
}
