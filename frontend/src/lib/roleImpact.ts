// What an Analyzer finding means for the target-role match. Both inputs come from the backend (the role's
// weighted skills and the current MatchResult), so the sentence is plain arithmetic on their numbers.
import type { Anomaly, MatchResult, Role, Skill, SkillMatch } from "../types/profile";

const SKILL_KINDS = new Set(["unsupported_claim", "overclaim", "missed_strength"]);

function key(name: string): string {
  return name.trim().toLowerCase();
}

/** The role skill a claim refers to: by name, or through the pair the matcher made (claim -> matched_to). */
export function roleSkillFor(claim: string, role: Role, match: MatchResult | null): Skill | null {
  const wanted = key(claim);
  const direct = role.skills.find((s) => key(s.name) === wanted);
  if (direct) return direct;
  const pairs: SkillMatch[] = [...(match?.matched ?? []), ...(match?.partial ?? [])];
  const pair = pairs.find((m) => key(m.name) === wanted);
  return pair ? (role.skills.find((s) => key(s.name) === key(pair.matched_to)) ?? null) : null;
}

/** Share of the role's total weight one skill carries, as a whole percentage. */
export function skillShare(skill: Skill, role: Role): number {
  const total = role.skills.reduce((sum, s) => sum + s.weight, 0);
  return total > 0 ? Math.round((100 * skill.weight) / total) : 0;
}

/** One sentence for an anomaly card, or null when the finding is not about a skill or no role is set. */
export function roleImpact(anomaly: Anomaly, role: Role | null, match: MatchResult | null): string | null {
  if (!role || role.skills.length === 0 || !SKILL_KINDS.has(anomaly.kind)) return null;
  const skill = roleSkillFor(anomaly.claim, role, match);
  if (!skill) return `Not a ${role.name} skill, so it does not change your match.`;
  const share = skillShare(skill, role);
  const counted = !!match?.matched.some((m) => key(m.matched_to) === key(skill.name));
  if (anomaly.kind === "missed_strength") {
    return counted
      ? `Now counted in your ${role.name} match: worth ${share}% of the score.`
      : `A ${role.name} skill worth ${share}% of the match once it is on your CV.`;
  }
  return counted
    ? `Counts for ${share}% of your ${role.name} match without any evidence behind it.`
    : `A ${role.name} skill worth ${share}% of the match, currently not matched.`;
}

/** Matched role skills with no GitHub or LinkedIn backing (only meaningful once the Analyzer has run). */
export function unverifiedMatches(match: MatchResult | null): SkillMatch[] {
  return (match?.matched ?? []).filter((m) => !m.sources.some((s) => s === "github" || s === "linkedin" || s === "portfolio"));
}
