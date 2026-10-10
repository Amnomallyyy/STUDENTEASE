// Left column of the Career Map: role picker, match meter, keyword-vs-embedding toggle, have / partial /
// missing chips with market counts, category radar and adjacent roles.
import { BadgeCheck, Loader2, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { keywordMatch } from "../../lib/keywordMatch";
import { unverifiedMatches } from "../../lib/roleImpact";
import { useSessionStore } from "../../store/session";
import type { AdjacentRole, GapResponse, Role, Skill, SkillMatch } from "../../types/profile";
import AdjacentRoles from "./AdjacentRoles";
import MatchMeter from "./MatchMeter";
import RadarCoverage from "./RadarCoverage";
import SkillChips, { type ChipItem } from "./SkillChips";

interface Props {
  roles: Role[];
  role: string | null;
  onRoleChange: (role: string) => void;
  gap: GapResponse | null;
  userSkills: Skill[];
  adjacent: AdjacentRole[];
  loading: boolean;
  error: string | null;
  /** Sources the CV Analyzer has checked (profile.evidence_sources); empty until it has run. */
  evidenceSources: ("cv" | "github" | "linkedin" | "portfolio")[];
  /** Open the Analyzer at the anomaly for a CV-only skill. */
  onVerify: (skillName: string) => void;
}

const SOURCE_LABELS: Record<string, string> = { github: "GitHub", linkedin: "LinkedIn", portfolio: "your portfolio", cv: "CV" };

function isEvidenced(m: SkillMatch): boolean {
  return m.sources.some((s) => s === "github" || s === "linkedin" || s === "portfolio");
}

export function headline(gap: GapResponse): string {
  const top = gap.market_gaps[0];
  const base = `You match ${gap.match.match_pct.toFixed(0)}% of ${gap.role}.`;
  if (!top || top.jobs_total === 0) return base;
  return `${base} ${top.jobs_requiring} of ${top.jobs_total} nearby jobs ask for ${top.skill} – learn that first.`;
}

export default function GapPanel({ roles, role, onRoleChange, gap, userSkills, adjacent, loading, error, evidenceSources, onVerify }: Props) {
  const showKeyword = useSessionStore((s) => s.showKeywordMatch);
  const setShowKeyword = useSessionStore((s) => s.setShowKeywordMatch);

  const roleSkills = roles.find((r) => r.name === (gap?.role ?? role))?.skills ?? [];
  const keyword = showKeyword && roleSkills.length ? keywordMatch(userSkills, roleSkills) : null;
  const keywordMatched = new Set(keyword?.matched.map((m) => m.matched_to.toLowerCase()) ?? []);
  const marketCount = new Map(gap?.market_gaps.map((g) => [g.skill.toLowerCase(), g]) ?? []);

  const analyzed = evidenceSources.length > 0;
  const checked = evidenceSources.map((s) => SOURCE_LABELS[s] ?? s).join(" and ");
  const unverified = analyzed ? unverifiedMatches(gap?.match ?? null) : [];

  const have: ChipItem[] =
    gap?.match.matched.map((m) => {
      const verified = analyzed ? isEvidenced(m) : null;
      const backing = m.sources.filter((s) => s !== "cv").map((s) => SOURCE_LABELS[s] ?? s);
      return {
        name: m.matched_to,
        detail: m.name.toLowerCase() !== m.matched_to.toLowerCase() ? ` ≈ ${m.name}` : undefined,
        title:
          `Your "${m.name}" matched "${m.matched_to}" (cosine ${m.similarity.toFixed(2)})` +
          (verified === true ? ` · backed by ${backing.join(", ")}` : verified === false ? ` · CV only: click to see why` : ""),
        highlight: !!keyword && !keywordMatched.has(m.matched_to.toLowerCase()),
        verified,
        onClick: verified === false ? () => onVerify(m.name) : undefined,
      };
    }) ?? [];
  const partial: ChipItem[] =
    gap?.match.partial.map((m) => ({
      name: m.matched_to,
      detail: ` ~ ${m.name}`,
      title: `Partial: "${m.name}" vs "${m.matched_to}" (cosine ${m.similarity.toFixed(2)}, 0.65-0.80 band, no credit)`,
    })) ?? [];
  const missing: ChipItem[] =
    gap?.match.missing.map((s) => {
      const market = marketCount.get(s.name.toLowerCase());
      return {
        name: s.name,
        detail: market && market.jobs_total > 0 ? ` · ${market.jobs_requiring}/${market.jobs_total} jobs` : undefined,
        title: `${s.requirement ?? "required"} skill (weight ${s.weight})${
          market ? `; asked for by ${market.jobs_requiring} of the ${market.jobs_total} nearest jobs` : ""
        }`,
      };
    }) ?? [];
  const embeddingOnly = have.filter((h) => h.highlight);

  return (
    <div className="space-y-5">
      <div>
        <label className="label" htmlFor="target-role">
          Target role
        </label>
        <select
          id="target-role"
          className="input"
          value={gap?.role ?? role ?? ""}
          onChange={(e) => onRoleChange(e.target.value)}
        >
          <option value="" disabled>
            Choose a role…
          </option>
          {roles.map((r) => (
            <option key={r.id} value={r.name}>
              {r.name}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {loading && !gap && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Matching your skills against the role…
        </p>
      )}

      {gap && (
        <>
          <div className="flex flex-col items-center">
            <MatchMeter
              value={gap.match.match_pct}
              label={`Match for ${gap.role}`}
              secondary={
                keyword
                  ? { value: keyword.match_pct, label: "Keyword-only" }
                  : analyzed && gap.match.evidenced_pct !== null
                    ? { value: gap.match.evidenced_pct, label: `Evidenced by ${checked}` }
                    : undefined
              }
            />
            <p className="mt-2 text-center text-sm font-medium text-slate-800">{headline(gap)}</p>
            {analyzed && gap.match.evidenced_pct !== null ? (
              <p className="mt-1 text-center text-xs text-slate-600" data-testid="evidence-line">
                <BadgeCheck className="mr-1 inline h-3.5 w-3.5 text-green-700" aria-hidden />
                <strong>{gap.match.evidenced_pct.toFixed(0)}%</strong> of this match is backed by {checked}.
                {unverified.length > 0 && (
                  <>
                    {" "}
                    {unverified.length} matched skill{unverified.length === 1 ? "" : "s"} rest{unverified.length === 1 ? "s" : ""} on the CV
                    alone:{" "}
                    <Link to="/analyzer" className="font-medium text-brand-700 underline">
                      see the fixes
                    </Link>
                    .
                  </>
                )}
              </p>
            ) : (
              <p className="mt-1 text-center text-xs text-slate-500" data-testid="evidence-line">
                <ShieldCheck className="mr-1 inline h-3.5 w-3.5 text-slate-400" aria-hidden />
                How much of this is backed by evidence?{" "}
                <Link to="/analyzer" className="font-medium text-brand-700 underline">
                  Run the CV Analyzer
                </Link>
                .
              </p>
            )}
          </div>

          <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 p-3 text-xs text-slate-600">
            <input
              type="checkbox"
              className="mt-0.5 accent-brand-600"
              checked={showKeyword}
              onChange={(e) => setShowKeyword(e.target.checked)}
            />
            <span>
              <span className="font-medium text-slate-800">Compare with keyword-only matching.</span> Embeddings match
              "PostgreSQL" to "SQL" or "Data viz" to "Tableau"; exact keywords do not.
              {keyword && embeddingOnly.length > 0 && (
                <span className="mt-1 block text-brand-700">
                  Only the embedding matcher caught: {embeddingOnly.map((h) => `${h.name}${h.detail ?? ""}`).join(", ")}.
                </span>
              )}
              {keyword && embeddingOnly.length === 0 && (
                <span className="mt-1 block">Both matchers agree on this role.</span>
              )}
            </span>
          </label>

          <SkillChips title="You have" items={have} variant="have" empty="No role skills matched yet" />
          <SkillChips title="Partial (0.65-0.80, no credit)" items={partial} variant="partial" empty="No partial matches" />
          <SkillChips title="Missing" items={missing} variant="missing" empty="Nothing missing" />

          <RadarCoverage roleSkills={roleSkills} matched={gap.match.matched} partial={gap.match.partial} />
        </>
      )}

      <AdjacentRoles roles={adjacent} loading={loading} onPick={onRoleChange} />
    </div>
  );
}
