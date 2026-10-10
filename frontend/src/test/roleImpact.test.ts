import { describe, expect, it } from "vitest";
import { roleImpact, roleSkillFor, skillShare, unverifiedMatches } from "../lib/roleImpact";
import type { Anomaly, MatchResult, Role, Skill } from "../types/profile";

function skill(name: string, weight: number): Skill {
  return { name, category: "tool", evidence: [], sources: [], years: null, confidence: 1, weight, requirement: null };
}

const role: Role = { id: "data-analyst", name: "Data Analyst", skills: [skill("SQL", 3), skill("Python", 3), skill("Tableau", 1), skill("Git", 1)] };

const match: MatchResult = {
  match_pct: 75,
  evidenced_pct: 37.5,
  matched: [
    { name: "PostgreSQL", matched_to: "SQL", similarity: 0.9, sources: ["cv"] },
    { name: "Python", matched_to: "Python", similarity: 1, sources: ["cv", "github"] },
  ],
  partial: [],
  missing: [skill("Tableau", 1), skill("Git", 1)],
};

function anomaly(kind: string, claim: string): Anomaly {
  return { id: `${kind}:${claim}`, kind, claim, evidence: "", severity: 2, suggested_fix: "" };
}

describe("roleImpact", () => {
  it("finds the role skill directly or through the matcher's pairing", () => {
    expect(roleSkillFor("python", role, match)?.name).toBe("Python");
    expect(roleSkillFor("PostgreSQL", role, match)?.name).toBe("SQL");
    expect(roleSkillFor("Docker", role, match)).toBeNull();
  });

  it("computes a skill's share of the role weight", () => {
    expect(skillShare(skill("SQL", 3), role)).toBe(38); // 3 of 8
    expect(skillShare(skill("Git", 1), role)).toBe(13);
  });

  it("explains an unsupported claim that is counted in the match", () => {
    expect(roleImpact(anomaly("unsupported_claim", "PostgreSQL"), role, match)).toBe(
      "Counts for 38% of your Data Analyst match without any evidence behind it.",
    );
  });

  it("explains a missed strength and a claim outside the role", () => {
    expect(roleImpact(anomaly("missed_strength", "Python"), role, match)).toBe(
      "Now counted in your Data Analyst match: worth 38% of the score.",
    );
    expect(roleImpact(anomaly("missed_strength", "Git"), role, match)).toBe(
      "A Data Analyst skill worth 13% of the match once it is on your CV.",
    );
    expect(roleImpact(anomaly("overclaim", "Docker"), role, match)).toBe("Not a Data Analyst skill, so it does not change your match.");
  });

  it("says nothing for non-skill findings or without a role", () => {
    expect(roleImpact(anomaly("inconsistency", "Data Intern"), role, match)).toBeNull();
    expect(roleImpact(anomaly("overclaim", "Docker"), null, match)).toBeNull();
  });

  it("lists matched skills with no external backing", () => {
    expect(unverifiedMatches(match).map((m) => m.matched_to)).toEqual(["SQL"]);
    expect(unverifiedMatches(null)).toEqual([]);
  });
});
