import { useEffect } from "react";
import { LocateFixed, Loader2 } from "lucide-react";
import { CITIES } from "../lib/cities";
import { useGeolocation } from "../hooks/useGeolocation";
import type { Location } from "../types/profile";

interface Props {
  value: Location | null;
  onChange: (location: Location | null) => void;
  compact?: boolean;
}

/** "Use my location" (browser Geolocation API) or one of the three cities the job dataset covers. */
export default function LocationPicker({ value, onChange, compact }: Props) {
  const geo = useGeolocation();

  useEffect(() => {
    if (geo.status === "ok" && geo.lat !== undefined && geo.lng !== undefined) {
      onChange({ lat: geo.lat, lng: geo.lng, city: "" });
    }
    // onChange is stable enough from callers; re-running on status alone avoids loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo.status, geo.lat, geo.lng]);

  const selectedCity = value?.city ?? "";
  const usingGeo = !!value && !value.city;

  return (
    <div className={compact ? "flex flex-wrap items-center gap-2" : "space-y-2"}>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={`btn-secondary text-xs ${usingGeo ? "border-brand-500 bg-brand-50 text-brand-700" : ""}`}
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
            className={`btn-secondary text-xs ${
              selectedCity === city.name ? "border-brand-500 bg-brand-50 text-brand-700" : ""
            }`}
            onClick={() => onChange({ lat: city.lat, lng: city.lng, city: city.name })}
          >
            {city.name}
          </button>
        ))}
      </div>
      {!compact && (
        <p className="text-xs text-slate-500">
          {value
            ? usingGeo
              ? `Using your location (${value.lat.toFixed(3)}, ${value.lng.toFixed(3)}).`
              : `Searching around ${value.city}.`
            : "Pick a city or share your location to see nearby jobs. The job dataset covers Karachi, Lahore and Islamabad."}
          {geo.status === "error" && <span className="text-red-600"> {geo.error}</span>}
        </p>
      )}
    </div>
  );
}
