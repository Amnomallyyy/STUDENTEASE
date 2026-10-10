import { BAND_HEX, matchBand } from "../../lib/format";

interface Props {
  value: number;
  label?: string;
  size?: number;
  /** Optional second ring (e.g. the keyword-only match) drawn inside the first. */
  secondary?: { value: number; label: string };
}

/** SVG ring showing a 0-100 match %, coloured by band (green >= 75, amber 50-74, red < 50). */
export default function MatchMeter({ value, label, size = 140, secondary }: Props) {
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value));
  const band = matchBand(clamped);
  const innerRadius = radius - stroke - 4;
  const innerCirc = 2 * Math.PI * innerRadius;
  const secondaryClamped = secondary ? Math.max(0, Math.min(100, secondary.value)) : 0;

  return (
    <div className="flex flex-col items-center" role="img" aria-label={`${label ?? "Match"} ${clamped.toFixed(0)} percent`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={BAND_HEX[band]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 600ms ease" }}
        />
        {secondary && (
          <>
            <circle cx={size / 2} cy={size / 2} r={innerRadius} fill="none" stroke="#f1f5f9" strokeWidth={6} />
            <circle
              cx={size / 2}
              cy={size / 2}
              r={innerRadius}
              fill="none"
              stroke="#94a3b8"
              strokeWidth={6}
              strokeLinecap="round"
              strokeDasharray={innerCirc}
              strokeDashoffset={innerCirc * (1 - secondaryClamped / 100)}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          </>
        )}
        <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="fill-slate-900" fontSize={size / 4.5} fontWeight={700}>
          {clamped.toFixed(0)}%
        </text>
      </svg>
      {label && <p className="mt-1 text-center text-sm font-medium text-slate-700">{label}</p>}
      {secondary && (
        <p className="text-xs text-slate-500">
          <span className="inline-block h-2 w-2 rounded-full bg-slate-400" /> {secondary.label}: {secondaryClamped.toFixed(0)}%
        </p>
      )}
    </div>
  );
}
