import { useCallback, useState } from "react";

export interface GeoState {
  status: "idle" | "loading" | "ok" | "error";
  lat?: number;
  lng?: number;
  error?: string;
}

/** Browser Geolocation API wrapper: call request() from a user action (browsers require a gesture). */
export function useGeolocation() {
  const [state, setState] = useState<GeoState>({ status: "idle" });

  const request = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setState({ status: "error", error: "Geolocation is not supported by this browser." });
      return;
    }
    setState({ status: "loading" });
    navigator.geolocation.getCurrentPosition(
      (pos) => setState({ status: "ok", lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) => setState({ status: "error", error: err.message || "Location permission was denied." }),
      { timeout: 10_000, maximumAge: 5 * 60_000 },
    );
  }, []);

  return { ...state, request };
}
