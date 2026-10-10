// Home dashboard: one tile per module reading from the shared profile, the market headline, and the
// skills the extractor found.
import { Link } from "react-router-dom";
import { Briefcase, Map as MapIcon, Mic, ShieldCheck, Target } from "lucide-react";
import ScoreTile from "../components/ScoreTile";
import SkillChips from "../components/career/SkillChips";
import { matchBand, pct, titleCase } from "../lib/format";
import { hasCV, useProfileStore } from "../store/profile";

export default function Dashboard() {
  const profile = useProfileStore((s) => s.profile);

  if (!hasCV(profile)) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-2xl font-bold">No CV yet</h1>
        <p className="mt-2 text-slate-600">Upload a CV once and every module reads from it.</p>
        <Link to="/upload" className="btn-primary mt-6">
          Upload a CV
        </Link>
      </div>
    );
  }

  const strongJobs = profile.jobs_nearby.filter((j) => j.match_pct >= 75).length;
  const topGap = profile.market_gaps[0];
  const analyzed = (profile.evidence_sources ?? []).length > 0;
  const checked = (profile.evidence_sources ?? []).map((s) => (s === "github" ? "GitHub" : s === "linkedin" ? "LinkedIn" : s)).join(" and ");
  const byCategory = new Map<string, typeof profile.skills>();
  for (const skill of profile.skills) {
    byCategory.set(skill.category, [...(byCategory.get(skill.category) ?? []), skill]);
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Your dashboard</h1>
          <p className="mt-1 text-slate-600">
            {profile.target_role ? (
              <>
                Target role <strong>{profile.target_role}</strong>
                {profile.location?.city ? ` · ${profile.location.city}` : profile.location ? " · your location" : ""}
              </>
            ) : (
              "No target role yet: pick one on the Career Map."
            )}
          </p>
        </div>
        <Link to="/upload" className="btn-secondary text-xs">
          Upload a different CV
        </Link>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <ScoreTile
          label="Role match"
          value={pct(profile.gap?.match_pct)}
          sub={
            profile.gap
              ? profile.gap.evidenced_pct !== null && profile.gap.evidenced_pct !== undefined
                ? `${pct(profile.gap.evidenced_pct)} evidenced · ${profile.gap.missing.length} missing`
                : `${profile.gap.missing.length} skills missing`
              : "Pick a target role"
          }
          to="/career"
          band={profile.gap ? matchBand(profile.gap.match_pct) : "neutral"}
          icon={<Target className="h-5 w-5" aria-hidden />}
        />
        <ScoreTile
          label="Jobs you fit nearby"
          value={profile.jobs_nearby.length ? `${strongJobs} / ${profile.jobs_nearby.length}` : "–"}
          sub={profile.jobs_nearby.length ? "match ≥ 75% among the nearest 20" : "Share a location to see jobs"}
          to="/career"
          band={profile.jobs_nearby.length ? (strongJobs > 0 ? "green" : "amber") : "neutral"}
          icon={<Briefcase className="h-5 w-5" aria-hidden />}
        />
        <ScoreTile
          label="CV integrity"
          value={pct(profile.integrity_score)}
          sub={
            profile.integrity_score === null
              ? "Run the CV Analyzer"
              : `${profile.anomalies.length} anomal${profile.anomalies.length === 1 ? "y" : "ies"} found`
          }
          to="/analyzer"
          band={profile.integrity_score === null ? "neutral" : matchBand(profile.integrity_score)}
          icon={<ShieldCheck className="h-5 w-5" aria-hidden />}
        />
        <ScoreTile
          label="Interview readiness"
          value={profile.interview ? `${Math.round(profile.interview.readiness)}` : "–"}
          sub={
            profile.interview
              ? `verbal ${Math.round(profile.interview.verbal_score)} · non-verbal ${
                  profile.interview.non_verbal_score === null ? "n/a" : Math.round(profile.interview.non_verbal_score)
                }`
              : "Take the 3-question mock interview"
          }
          to="/interview"
          band={profile.interview ? matchBand(profile.interview.readiness) : "neutral"}
          icon={<Mic className="h-5 w-5" aria-hidden />}
        />
      </div>

      {topGap && topGap.jobs_total > 0 && (
        <div className="card mt-6 flex flex-wrap items-center gap-4 border-brand-200 bg-brand-50 p-4">
          <MapIcon className="h-6 w-6 shrink-0 text-brand-700" aria-hidden />
          <p className="flex-1 text-sm text-brand-900">
            <strong>{topGap.jobs_requiring}</strong> of <strong>{topGap.jobs_total}</strong> nearby jobs ask for{" "}
            <strong>{topGap.skill}</strong> – learn that first.
            {profile.market_gaps.length > 1 && (
              <span className="text-brand-800">
                {" "}
                Then {profile.market_gaps.slice(1, 4).map((g) => g.skill).join(", ")}.
              </span>
            )}
          </p>
          <Link to="/career" className="btn-primary text-xs">
            Open the Career Map
          </Link>
        </div>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="card p-4">
          <h2 className="text-sm font-semibold">
            {analyzed ? `Your skills (${profile.skills.length})` : `Skills found in your CV (${profile.skills.length})`}
          </h2>
          {analyzed && (
            <p className="mt-1 text-xs text-slate-500">
              Checked against {checked}: a tick means at least one of them backs the skill; a dashed chip is on the CV alone.{" "}
              <Link to="/analyzer" className="text-brand-700 underline">
                Open the Analyzer
              </Link>
            </p>
          )}
          <div className="mt-3 space-y-3">
            {[...byCategory.entries()].map(([category, skills]) => (
              <SkillChips
                key={category}
                title={titleCase(category)}
                items={skills.map((skill) => ({
                  name: skill.name,
                  verified: analyzed ? skill.sources.some((s) => s === "github" || s === "linkedin") : null,
                  title: analyzed ? `Sources: ${skill.sources.join(", ") || "cv"}` : undefined,
                }))}
                variant="neutral"
              />
            ))}
          </div>
        </div>
        <div className="space-y-4">
          <div className="card p-4">
            <h2 className="text-sm font-semibold">Projects ({profile.projects.length})</h2>
            <ul className="mt-2 space-y-2 text-sm">
              {profile.projects.slice(0, 5).map((p) => (
                <li key={p.name}>
                  <p className="font-medium text-slate-800">{p.name}</p>
                  <p className="text-xs text-slate-500">{p.skills.join(", ")}</p>
                </li>
              ))}
              {profile.projects.length === 0 && <li className="text-xs text-slate-400">None found</li>}
            </ul>
          </div>
          <div className="card p-4">
            <h2 className="text-sm font-semibold">Experience ({profile.experience.length})</h2>
            <ul className="mt-2 space-y-2 text-sm">
              {profile.experience.slice(0, 5).map((e) => (
                <li key={e.title + e.organisation}>
                  <p className="font-medium text-slate-800">
                    {e.title} · {e.organisation}
                  </p>
                  <p className="text-xs text-slate-500">{e.years !== null ? `${e.years} yr · ` : ""}{e.skills.join(", ")}</p>
                </li>
              ))}
              {profile.experience.length === 0 && <li className="text-xs text-slate-400">None found</li>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
