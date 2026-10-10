import { describe, expect, it } from "vitest";
import { coverageByCategory } from "../components/career/RadarCoverage";
import { chipTone } from "../pages/Analyzer";
import { headline } from "../components/career/GapPanel";
import type { GapResponse, Skill } from "../types/profile";

const skill = (name: string, category: Skill["category"], weight = 1): Skill => ({
  name,
  category,
  evidence: [],
  sources: [],
  years: null,
  confidence: 1,
  weight,
  requirement: "core",
});

describe("coverageByCategory", () => {
  it("computes weighted coverage per category from matched and partial names", () => {
    const role = [skill("SQL", "language", 3), skill("Python", "language", 1), skill("Excel", "tool", 2), skill("Communication", "soft_skill")];
    const rows = coverageByCategory(
      role,
      [{ name: "PostgreSQL", matched_to: "SQL", similarity: 0.9, sources: [] }],
      [{ name: "Jupyter", matched_to: "Python", similarity: 0.7, sources: [] }],
    );
    const language = rows.find((r) => r.category === "Language")!;
    expect(language.coverage).toBe(75); // 3 of 4 weight matched
    expect(language.partial).toBe(100); // + Python partial
    expect(rows.find((r) => r.category === "Tool")!.coverage).toBe(0);
    expect(rows.map((r) => r.category)).toEqual(["Language", "Tool", "Soft Skill"]);
  });
});

describe("chipTone", () => {
  it("is green in every provided source, amber in one, blue otherwise", () => {
    const cluster = { name: "Python", sources: ["cv", "github"] as const, members: ["Python"], mention_count: 2 };
    expect(chipTone({ ...cluster, sources: ["cv", "github", "linkedin"] }, 3)).toBe("green");
    expect(chipTone({ ...cluster, sources: ["cv", "github"] }, 2)).toBe("green");
    expect(chipTone({ ...cluster, sources: ["cv", "github"] }, 3)).toBe("blue");
    expect(chipTone({ ...cluster, sources: ["cv"] }, 3)).toBe("amber");
  });
});

describe("headline", () => {
  it("names the top market gap when nearby jobs exist", () => {
    const gap: GapResponse = {
      role: "Data Analyst",
      match: { match_pct: 65.4, evidenced_pct: null, matched: [], partial: [], missing: [] },
      market_gaps: [{ skill: "SQL", jobs_requiring: 14, jobs_total: 20, priority: 3 }],
      jobs_nearby: [],
    };
    expect(headline(gap)).toBe("You match 65% of Data Analyst. 14 of 20 nearby jobs ask for SQL – learn that first.");
    expect(headline({ ...gap, market_gaps: [] })).toBe("You match 65% of Data Analyst.");
  });
});
