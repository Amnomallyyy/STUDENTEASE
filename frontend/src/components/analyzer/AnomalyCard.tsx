import { AlertTriangle, Lightbulb, Target, Wrench } from "lucide-react";
import type { Anomaly } from "../../types/profile";

interface Props {
  anomaly: Anomaly;
  highlighted?: boolean;
  domId?: string;
  /** What this finding means for the target-role match (lib/roleImpact.ts); omitted when no role is set. */
  impact?: string | null;
}

/** Labels for the five deterministic rules in backend/services/evidence/anomalies.py. */
export const KIND_LABELS: Record<string, { label: string; group: string; tone: string }> = {
  unsupported_claim: { label: "Unsupported claim", group: "Claimed but not evidenced", tone: "text-red-700 bg-red-50 border-red-200" },
  overclaim: { label: "Overclaim", group: "Claimed but not evidenced", tone: "text-red-700 bg-red-50 border-red-200" },
  weak_evidence: { label: "Weak evidence", group: "Claimed but not evidenced", tone: "text-amber-700 bg-amber-50 border-amber-200" },
  missed_strength: { label: "Missed strength", group: "Evidenced but not claimed", tone: "text-blue-700 bg-blue-50 border-blue-200" },
  inconsistency: { label: "Inconsistency", group: "Inconsistent", tone: "text-amber-700 bg-amber-50 border-amber-200" },
};

export function kindInfo(kind: string) {
  return KIND_LABELS[kind] ?? { label: kind.replace(/_/g, " "), group: "Other", tone: "text-slate-700 bg-slate-50 border-slate-200" };
}

export default function AnomalyCard({ anomaly, highlighted, domId, impact }: Props) {
  const info = kindInfo(anomaly.kind);
  return (
    <article
      id={domId}
      className={`card p-4 transition ${highlighted ? "ring-2 ring-amber-400" : ""}`}
      aria-label={`${info.label}: ${anomaly.claim}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={`chip ${info.tone}`}>
          <AlertTriangle className="h-3 w-3" aria-hidden />
          {info.label}
        </span>
        <span className="text-xs text-slate-500" title="Severity 1-3">
          Severity{" "}
          {Array.from({ length: 3 }, (_, i) => (
            <span key={i} className={i < anomaly.severity ? "text-red-500" : "text-slate-300"}>
              ●
            </span>
          ))}
        </span>
      </div>
      <h3 className="mt-2 text-sm font-semibold text-slate-900">{anomaly.claim}</h3>
      {anomaly.evidence && (
        <p className="mt-1 text-sm text-slate-600">
          <span className="font-medium text-slate-700">Evidence: </span>
          {anomaly.evidence}
        </p>
      )}
      {impact && (
        <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-600" data-testid="role-impact">
          <Target className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden />
          <span>{impact}</span>
        </p>
      )}
      {anomaly.suggested_fix && (
        <div className="mt-3 flex gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-900">
          <Wrench className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <p>{anomaly.suggested_fix}</p>
        </div>
      )}
      {!anomaly.suggested_fix && (
        <p className="mt-3 flex items-center gap-1 text-xs text-slate-400">
          <Lightbulb className="h-3 w-3" aria-hidden /> No fix suggested (LLM unavailable).
        </p>
      )}
    </article>
  );
}
