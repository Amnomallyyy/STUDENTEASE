import { describe, expect, it } from "vitest";
import { km, matchBand, pct, rankScore } from "../lib/format";

describe("matchBand", () => {
  it("uses the README thresholds: green >= 75, amber 50-74, red < 50", () => {
    expect(matchBand(75)).toBe("green");
    expect(matchBand(74.9)).toBe("amber");
    expect(matchBand(50)).toBe("amber");
    expect(matchBand(49.9)).toBe("red");
  });
});

describe("rankScore", () => {
  it("blends match % and nearness with the given weight (default 70/30)", () => {
    expect(rankScore(80, 0, 25, 0.7)).toBeCloseTo(0.7 * 80 + 0.3 * 100);
    expect(rankScore(80, 25, 25, 0.7)).toBeCloseTo(0.7 * 80);
    expect(rankScore(80, 50, 25, 0.7)).toBeCloseTo(0.7 * 80); // never below zero nearness
    expect(rankScore(60, 5, 25, 1)).toBe(60);
  });
});

describe("pct / km", () => {
  it("formats numbers and dashes for missing values", () => {
    expect(pct(65.4)).toBe("65%");
    expect(pct(null)).toBe("–");
    expect(km(4.25)).toBe("4.3 km");
    expect(km(12.6)).toBe("13 km");
  });
});
