import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import type { MatchBand } from "../lib/format";

interface Props {
  label: string;
  value: string;
  sub?: string;
  to?: string;
  band?: MatchBand | "neutral";
  icon?: ReactNode;
}

const RING: Record<MatchBand | "neutral", string> = {
  green: "border-green-200 bg-green-50 text-green-700",
  amber: "border-amber-200 bg-amber-50 text-amber-700",
  red: "border-red-200 bg-red-50 text-red-700",
  neutral: "border-slate-200 bg-slate-50 text-slate-500",
};

export default function ScoreTile({ label, value, sub, to, band = "neutral", icon }: Props) {
  const body = (
    <div className="card flex h-full items-start gap-4 p-4">
      <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border ${RING[band]}`}>
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
        {sub && <p className="mt-0.5 truncate text-xs text-slate-500">{sub}</p>}
      </div>
      {to && <ArrowUpRight className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />}
    </div>
  );
  return to ? (
    <Link to={to} className="block rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-300">
      {body}
    </Link>
  ) : (
    body
  );
}
