export type MatchBand = "green" | "amber" | "red";

/** Pins and meters: green >= 75 %, amber 50-74 %, red < 50 % (README, "Job ranking"). */
export function matchBand(value: number): MatchBand {
  if (value >= 75) return "green";
  if (value >= 50) return "amber";
  return "red";
}

export const BAND_HEX: Record<MatchBand, string> = { green: "#16a34a", amber: "#d97706", red: "#dc2626" };

export const BAND_CLASSES: Record<MatchBand, string> = {
  green: "bg-green-100 text-green-800 border-green-300",
  amber: "bg-amber-100 text-amber-800 border-amber-300",
  red: "bg-red-100 text-red-800 border-red-300",
};

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return `${value.toFixed(digits)}%`;
}

export function km(value: number): string {
  return value < 10 ? `${value.toFixed(1)} km` : `${Math.round(value)} km`;
}

/** Blend of match % and nearness (default 70/30) used to rank the job list; higher is better. */
export function rankScore(matchPct: number, distanceKm: number, radiusKm: number, matchWeight: number): number {
  const nearness = Math.max(0, 1 - distanceKm / Math.max(radiusKm, 0.1)) * 100;
  return matchWeight * matchPct + (1 - matchWeight) * nearness;
}

export function titleCase(text: string): string {
  return text.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
