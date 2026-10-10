import { RADIUS_OPTIONS, useSessionStore } from "../../store/session";

interface Props {
  count: number;
  total: number;
}

/** Radius (5 / 10 / 25 km), minimum match %, keyword and the match-vs-distance ranking blend (default 70/30). */
export default function MapFilters({ count, total }: Props) {
  const radiusKm = useSessionStore((s) => s.radiusKm);
  const setRadiusKm = useSessionStore((s) => s.setRadiusKm);
  const minMatch = useSessionStore((s) => s.minMatch);
  const setMinMatch = useSessionStore((s) => s.setMinMatch);
  const keyword = useSessionStore((s) => s.keyword);
  const setKeyword = useSessionStore((s) => s.setKeyword);
  const matchWeight = useSessionStore((s) => s.matchWeight);
  const setMatchWeight = useSessionStore((s) => s.setMatchWeight);
  const custom = !(RADIUS_OPTIONS as readonly number[]).includes(radiusKm);

  return (
    <div className="flex flex-wrap items-end gap-x-5 gap-y-3 text-sm">
      <div>
        <p className="label">Radius</p>
        <div className="flex gap-1" role="radiogroup" aria-label="Radius">
          {RADIUS_OPTIONS.map((r) => (
            <button
              key={r}
              type="button"
              role="radio"
              aria-checked={radiusKm === r}
              onClick={() => setRadiusKm(r)}
              className={`rounded-md border px-2.5 py-1 text-xs font-medium ${
                radiusKm === r ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {r} km
            </button>
          ))}
          {custom && (
            <span className="rounded-md border border-brand-500 bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
              {radiusKm} km
            </span>
          )}
        </div>
      </div>

      <div>
        <label className="label" htmlFor="min-match">
          Min match {minMatch}%
        </label>
        <input
          id="min-match"
          type="range"
          min={0}
          max={100}
          step={5}
          value={minMatch}
          onChange={(e) => setMinMatch(Number(e.target.value))}
          className="w-32 accent-brand-600"
        />
      </div>

      <div>
        <label className="label" htmlFor="keyword">
          Keyword
        </label>
        <input
          id="keyword"
          className="input w-40 py-1"
          placeholder="title, company, skill"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
      </div>

      <div>
        <label className="label" htmlFor="blend">
          Rank: match {Math.round(matchWeight * 100)} / distance {Math.round((1 - matchWeight) * 100)}
        </label>
        <input
          id="blend"
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={matchWeight}
          onChange={(e) => setMatchWeight(Number(e.target.value))}
          className="w-32 accent-brand-600"
          title="Blend of match % and distance used to rank the list (default 70/30)"
        />
      </div>

      <p className="ml-auto text-xs text-slate-500">
        {count} of {total} jobs shown
      </p>
    </div>
  );
}
