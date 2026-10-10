import { BadgeCheck, CircleAlert } from "lucide-react";

export interface ChipItem {
  name: string;
  /** Small secondary text, e.g. "≈ SQL 0.87" for a partial match. */
  detail?: string;
  title?: string;
  highlight?: boolean;
  /** Evidence state once the Analyzer has run: true = backed by GitHub/LinkedIn, false = CV only. Omit/null = unknown. */
  verified?: boolean | null;
  /** Makes the chip a button (e.g. a CV-only skill that jumps to its anomaly in the Analyzer). */
  onClick?: () => void;
}

interface Props {
  title: string;
  items: ChipItem[];
  variant: "have" | "partial" | "missing" | "neutral";
  empty?: string;
}

const STYLES = {
  have: "border-green-300 bg-green-50 text-green-800",
  partial: "border-amber-300 bg-amber-50 text-amber-800",
  missing: "border-red-300 bg-red-50 text-red-800",
  neutral: "border-slate-300 bg-slate-50 text-slate-700",
};

function Badge({ verified }: { verified: boolean }) {
  return verified ? (
    <BadgeCheck className="h-3.5 w-3.5 text-green-700" aria-label="Backed by GitHub or LinkedIn" />
  ) : (
    <CircleAlert className="h-3.5 w-3.5 text-amber-600" aria-label="CV only: no external evidence" />
  );
}

export default function SkillChips({ title, items, variant, empty = "None" }: Props) {
  return (
    <div>
      <p className="label">
        {title} <span className="font-normal normal-case text-slate-400">({items.length})</span>
      </p>
      {items.length === 0 ? (
        <p className="text-xs text-slate-400">{empty}</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {items.map((item) => {
            const className = `chip ${STYLES[variant]} ${item.highlight ? "ring-2 ring-brand-400" : ""} ${
              item.verified === false ? "border-dashed" : ""
            } ${item.onClick ? "cursor-pointer hover:brightness-95" : ""}`;
            const content = (
              <>
                {item.verified !== undefined && item.verified !== null && <Badge verified={item.verified} />}
                {item.name}
                {item.detail && <span className="font-normal opacity-70">{item.detail}</span>}
              </>
            );
            return (
              <li key={item.name + (item.detail ?? "")}>
                {item.onClick ? (
                  <button type="button" className={className} title={item.title} onClick={item.onClick}>
                    {content}
                  </button>
                ) : (
                  <span className={className} title={item.title}>
                    {content}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
