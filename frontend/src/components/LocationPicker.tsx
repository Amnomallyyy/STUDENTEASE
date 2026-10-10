import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { LocateFixed, Loader2, Search } from "lucide-react";
import { CITIES } from "../lib/cities";
import { api, errorMessage } from "../lib/api";
import { useGeolocation } from "../hooks/useGeolocation";
import type { Location } from "../types/profile";

interface Props {
  value: Location | null;
  onChange: (location: Location | null) => void;
  compact?: boolean;
}

/**
 * Where to look for jobs: any city or area typed in (resolved through OpenStreetMap), the browser's
 * location, or one of the quick-pick cities. The place name is what the job search is run against.
 */
export default function LocationPicker({ value, onChange, compact }: Props) {
  const geo = useGeolocation();
  const [query, setQuery] = useState("");
  const [looking, setLooking] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  useEffect(() => {
    if (geo.status === "ok" && geo.lat !== undefined && geo.lng !== undefined) {
      onChange({ lat: geo.lat, lng: geo.lng, city: "" });
    }
    // onChange is stable enough from callers; re-running on status alone avoids loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo.status, geo.lat, geo.lng]);

  const selectedCity = value?.city ?? "";
  const usingGeo = !!value && !value.city;

  // Not a <form>: the picker sits inside the upload form, and forms cannot nest.
  async function lookUp(event?: FormEvent | KeyboardEvent) {
    event?.preventDefault();
    const q = query.trim();
    if (!q) return;
    setLookupError(null);
    setLooking(true);
    try {
      const place = await api.place(q);
      onChange({ lat: place.lat, lng: place.lng, city: place.city || q });
      setQuery("");
    } catch (err) {
      setLookupError(errorMessage(err));
    } finally {
      setLooking(false);
    }
  }

  return (
    <div className={compact ? "flex flex-wrap items-center gap-2" : "space-y-2"}>
      <div className="flex items-center gap-1.5" role="search" aria-label="Job location">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" aria-hidden />
          <input
            className={`input pl-8 ${compact ? "w-44 py-1.5 text-xs" : "w-64"}`}
            placeholder="City or area, e.g. Lahore"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void lookUp(e);
            }}
            disabled={looking}
            aria-label="City or area"
          />
        </div>
        <button type="button" className="btn-secondary text-xs" disabled={!query.trim() || looking} onClick={() => lookUp()}>
          {looking ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : "Set"}
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={`btn-secondary text-xs ${usingGeo ? "bg-brand-600 text-white" : ""}`}
          onClick={geo.request}
          disabled={geo.status === "loading"}
        >
          {geo.status === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <LocateFixed className="h-4 w-4" aria-hidden />
          )}
          Use my location
        </button>
        {CITIES.map((city) => (
          <button
            key={city.name}
            type="button"
            className={`btn-secondary text-xs ${selectedCity === city.name ? "bg-brand-600 text-white" : ""}`}
            onClick={() => onChange({ lat: city.lat, lng: city.lng, city: city.name })}
          >
            {city.name}
          </button>
        ))}
      </div>
      {(lookupError || !compact) && (
        <p className="text-xs text-slate-600">
          {lookupError ? (
            <span className="text-red-600">{lookupError}</span>
          ) : value ? (
            usingGeo ? (
              `Using your location (${value.lat.toFixed(3)}, ${value.lng.toFixed(3)}).`
            ) : (
              `Searching jobs in ${value.city}.`
            )
          ) : (
            "Type any city or area, share your location, or pick a city. Jobs are real postings from LinkedIn, Indeed and other boards."
          )}
          {geo.status === "error" && <span className="text-red-600"> {geo.error}</span>}
        </p>
      )}
    </div>
  );
}
