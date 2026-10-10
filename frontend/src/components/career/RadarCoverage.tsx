import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";
import type { Skill, SkillCategory, SkillMatch } from "../../types/profile";
import { titleCase } from "../../lib/format";

interface Props {
  roleSkills: Skill[];
  matched: SkillMatch[];
  partial: SkillMatch[];
}

const CATEGORIES: SkillCategory[] = ["language", "tool", "framework", "soft_skill", "domain"];

export interface CoverageRow {
  category: string;
  coverage: number;
  partial: number;
  total: number;
}

/** Weighted share of the role's skills in each category that the user has (full) or nearly has (partial). */
export function coverageByCategory(roleSkills: Skill[], matched: SkillMatch[], partial: SkillMatch[]): CoverageRow[] {
  const matchedNames = new Set(matched.map((m) => m.matched_to.toLowerCase()));
  const partialNames = new Set(partial.map((m) => m.matched_to.toLowerCase()));
  return CATEGORIES.map((category) => {
    const skills = roleSkills.filter((s) => s.category === category);
    const total = skills.reduce((sum, s) => sum + (s.weight ?? 1), 0);
    const have = skills.filter((s) => matchedNames.has(s.name.toLowerCase())).reduce((sum, s) => sum + (s.weight ?? 1), 0);
    const near = skills.filter((s) => partialNames.has(s.name.toLowerCase())).reduce((sum, s) => sum + (s.weight ?? 1), 0);
    return {
      category: titleCase(category),
      coverage: total ? Math.round((100 * have) / total) : 0,
      partial: total ? Math.round((100 * (have + near)) / total) : 0,
      total: skills.length,
    };
  }).filter((row) => row.total > 0);
}

export default function RadarCoverage({ roleSkills, matched, partial }: Props) {
  const data = coverageByCategory(roleSkills, matched, partial);
  if (data.length < 3) return null;
  return (
    <div>
      <p className="label">Coverage by category</p>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="70%">
            <PolarGrid stroke="#e2e8f0" />
            <PolarAngleAxis dataKey="category" tick={{ fontSize: 11, fill: "#475569" }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
            <Radar name="With partial" dataKey="partial" stroke="#d97706" fill="#fbbf24" fillOpacity={0.15} />
            <Radar name="Matched" dataKey="coverage" stroke="#1c57f0" fill="#3277fb" fillOpacity={0.35} />
            <Tooltip formatter={(value: number) => `${value}%`} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
