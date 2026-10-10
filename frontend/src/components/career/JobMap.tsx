// Leaflet map with OpenStreetMap tiles (free, no key), clustered job pins coloured by match % and the
// user's location with the search radius. Clustering uses leaflet.markercluster directly (no wrapper).
import { useEffect } from "react";
import L from "leaflet";
import "leaflet.markercluster";
import { Circle, MapContainer, Marker, TileLayer, useMap } from "react-leaflet";
import { BAND_HEX, matchBand } from "../../lib/format";
import type { JobNearby } from "../../types/api";

interface Props {
  jobs: JobNearby[];
  center: { lat: number; lng: number };
  radiusKm: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const USER_ICON = L.divIcon({ className: "", html: '<span class="user-pin"></span>', iconSize: [16, 16], iconAnchor: [8, 8] });

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] ?? c);
}

export function pinIcon(matchPct: number, selected: boolean): L.DivIcon {
  const colour = BAND_HEX[matchBand(matchPct)];
  return L.divIcon({
    className: "",
    html: `<span class="job-pin${selected ? " selected" : ""}" style="background:${colour}"></span>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

export function zoomForRadius(radiusKm: number): number {
  if (radiusKm <= 5) return 13;
  if (radiusKm <= 10) return 12;
  if (radiusKm <= 25) return 11;
  return 10;
}

function ClusterLayer({ jobs, selectedId, onSelect }: Pick<Props, "jobs" | "selectedId" | "onSelect">) {
  const map = useMap();
  useEffect(() => {
    const group = L.markerClusterGroup({
      maxClusterRadius: 45,
      showCoverageOnHover: false,
      spiderfyOnMaxZoom: true,
      disableClusteringAtZoom: 14,
    });
    for (const job of jobs) {
      const marker = L.marker([job.lat, job.lng], {
        icon: pinIcon(job.match_pct, job.id === selectedId),
        title: `${job.title} · ${job.company}`,
        zIndexOffset: job.id === selectedId ? 1000 : 0,
      });
      marker.bindTooltip(
        `<strong>${escapeHtml(job.title)}</strong><br/>${escapeHtml(job.company)} · ${job.match_pct.toFixed(0)}%` +
          (job.missing.length ? `<br/><span style="color:#b91c1c">Missing: ${escapeHtml(job.missing.slice(0, 3).join(", "))}${
            job.missing.length > 3 ? "…" : ""
          }</span>` : ""),
        { direction: "top", offset: [0, -8] },
      );
      marker.on("click", () => onSelect(job.id));
      group.addLayer(marker);
    }
    map.addLayer(group);
    return () => {
      map.removeLayer(group);
    };
  }, [map, jobs, selectedId, onSelect]);
  return null;
}

function Viewport({ center, radiusKm, selected }: { center: Props["center"]; radiusKm: number; selected: JobNearby | null }) {
  const map = useMap();
  useEffect(() => {
    map.setView([center.lat, center.lng], zoomForRadius(radiusKm));
  }, [map, center.lat, center.lng, radiusKm]);
  useEffect(() => {
    if (selected) map.panTo([selected.lat, selected.lng], { animate: true });
  }, [map, selected]);
  return null;
}

export default function JobMap({ jobs, center, radiusKm, selectedId, onSelect }: Props) {
  const selected = jobs.find((j) => j.id === selectedId) ?? null;
  return (
    <MapContainer center={[center.lat, center.lng]} zoom={zoomForRadius(radiusKm)} scrollWheelZoom className="h-full w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Circle center={[center.lat, center.lng]} radius={radiusKm * 1000} pathOptions={{ color: "#1c57f0", weight: 1, fillOpacity: 0.04 }} />
      <Marker position={[center.lat, center.lng]} icon={USER_ICON} title="You" />
      <ClusterLayer jobs={jobs} selectedId={selectedId} onSelect={onSelect} />
      <Viewport center={center} radiusKm={radiusKm} selected={selected} />
    </MapContainer>
  );
}
