// Keyword-only matching, shown beside the embedding matcher to prove the difference live:
// "PostgreSQL" vs "SQL" or "Data Viz" vs "Tableau" are misses here and matches for the embeddings.
// Mirrors the weighting rule of backend/services/matcher.py (match % = weighted matched / weighted total)
// but a required skill only counts when a user skill has exactly the same normalised name.

export interface KeywordHit {
  name: string;
  matched_to: string;
}

export interface KeywordMatchResult {
  match_pct: number;
  matched: KeywordHit[];
  missing: string[];
}

interface Named {
  name: string;
}

interface Weighted extends Named {
  weight?: number;
}

/** Lower-case, strip punctuation except + # . (C++, C#, .NET), collapse spaces. */
export function normalise(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9+#.\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function keywordMatch(userSkills: readonly Named[], targetSkills: readonly Weighted[]): KeywordMatchResult {
  const have = new Map<string, string>();
  for (const skill of userSkills) {
    const key = normalise(skill.name);
    if (key && !have.has(key)) have.set(key, skill.name);
  }

  let total = 0;
  let got = 0;
  const matched: KeywordHit[] = [];
  const missing: string[] = [];
  for (const target of targetSkills) {
    const weight = target.weight ?? 1;
    total += weight;
    const hit = have.get(normalise(target.name));
    if (hit !== undefined) {
      got += weight;
      matched.push({ name: hit, matched_to: target.name });
    } else {
      missing.push(target.name);
    }
  }
  const match_pct = total > 0 ? Math.round((1000 * got) / total) / 10 : 0;
  return { match_pct, matched, missing };
}
