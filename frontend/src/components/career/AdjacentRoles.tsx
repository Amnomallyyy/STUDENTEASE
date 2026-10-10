import { ArrowRight } from "lucide-react";
import { BAND_CLASSES, matchBand, pct } from "../../lib/format";
import type { AdjacentRole } from "../../types/profile";

interface Props {
  roles: AdjacentRole[];
  loading?: boolean;
  onPick: (role: string) => void;
}

/** "You did not know you were 80 % of a Business Analyst": the top roles the user already fits best. */
export default function AdjacentRoles({ roles, loading, onPick }: Props) {
  return (
    <div>
      <p className="label">Adjacent roles you already fit</p>
      {loading && roles.length === 0 ? (
        <p className="text-xs text-slate-400">Comparing against every role…</p>
      ) : roles.length === 0 ? (
        <p className="text-xs text-slate-400">No other roles scored yet.</p>
      ) : (
        <ul className="space-y-1">
          {roles.map((r) => (
            <li key={r.role}>
              <button
                type="button"
                onClick={() => onPick(r.role)}
                className="flex w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-left text-sm hover:border-brand-300 hover:bg-brand-50"
                title={`Switch the target role to ${r.role}`}
              >
                <span className="min-w-0 flex-1 truncate">{r.role}</span>
                <span className={`chip ${BAND_CLASSES[matchBand(r.match_pct)]}`}>{pct(r.match_pct)}</span>
                <ArrowRight className="h-4 w-4 text-slate-400" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
