// Career Map: gap panel | job map + ranked list + job detail | 4-week roadmap. One screen answers
// "how far am I from the role, who near me is hiring, what do I learn first".
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import GapPanel from "../components/career/GapPanel";
import JobDetail from "../components/career/JobDetail";
import JobList, { type RankedJob } from "../components/career/JobList";
import JobMap from "../components/career/JobMap";
import MapFilters from "../components/career/MapFilters";
import RoadmapTimeline from "../components/career/RoadmapTimeline";
import LocationPicker from "../components/LocationPicker";
import { api, ApiError, errorMessage } from "../lib/api";
import { rankScore } from "../lib/format";
import { hasCV, useProfileStore } from "../store/profile";
import { useSessionStore } from "../store/session";
import type { JobNearby } from "../types/api";
import type { AdjacentRole, GapResponse, Location, Roadmap, Role } from "../types/profile";

export default function CareerMap() {
  const navigate = useNavigate();
  const profile = useProfileStore((s) => s.profile);
  const setProfile = useProfileStore((s) => s.setProfile);
  const merge = useProfileStore((s) => s.merge);

  const sessionRole = useSessionStore((s) => s.role);
  const setSessionRole = useSessionStore((s) => s.setRole);
  const radiusKm = useSessionStore((s) => s.radiusKm);
  const minMatch = useSessionStore((s) => s.minMatch);
  const keyword = useSessionStore((s) => s.keyword);
  const matchWeight = useSessionStore((s) => s.matchWeight);
  const pinnedJobId = useSessionStore((s) => s.pinnedJobId);
  const setPinnedJobId = useSessionStore((s) => s.setPinnedJobId);
  const selectedJobId = useSessionStore((s) => s.selectedJobId);
  const setSelectedJobId = useSessionStore((s) => s.setSelectedJobId);
  const setServerExpired = useSessionStore((s) => s.setServerExpired);

  const [roles, setRoles] = useState<Role[]>([]);
  const [gap, setGap] = useState<GapResponse | null>(null);
  const [adjacent, setAdjacent] = useState<AdjacentRole[]>([]);
  const [jobs, setJobs] = useState<JobNearby[]>([]);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(profile?.roadmap ?? null);
  const [gapLoading, setGapLoading] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [roadmapLoading, setRoadmapLoading] = useState(false);
  const [gapError, setGapError] = useState<string | null>(null);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [roadmapError, setRoadmapError] = useState<string | null>(null);
  const [roadmapNonce, setRoadmapNonce] = useState(0);

  const role = sessionRole ?? profile?.target_role ?? null;
  const location = profile?.location ?? null;
  const lat = location?.lat ?? null;
  const lng = location?.lng ?? null;

  const fail = useCallback(
    (err: unknown, set: (message: string) => void) => {
      if (err instanceof ApiError && err.status === 409) setServerExpired(true);
      set(errorMessage(err));
    },
    [setServerExpired],
  );

  useEffect(() => {
    api.roles().then(setRoles).catch(() => setRoles([]));
  }, []);

  // Gap + adjacent roles: re-run when the role, the radius or the location changes.
  useEffect(() => {
    if (!hasCV(profile) || !role) return;
    let cancelled = false;
    setGapLoading(true);
    setGapError(null);
    api
      .gap({ role, radius_km: radiusKm, lat, lng })
      .then((result) => {
        if (cancelled) return;
        setGap(result);
        merge({ target_role: result.role, gap: result.match, market_gaps: result.market_gaps, jobs_nearby: result.jobs_nearby });
        return api.adjacent({ role: result.role, limit: 3 }).then((list) => !cancelled && setAdjacent(list));
      })
      .catch((err) => !cancelled && fail(err, setGapError))
      .finally(() => !cancelled && setGapLoading(false));
    return () => {
      cancelled = true;
    };
    // profile identity changes on every merge; depend on the inputs that matter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, radiusKm, lat, lng]);

  // Jobs for the map: every listing within the radius (filters apply client-side).
  useEffect(() => {
    if (!hasCV(profile) || lat === null || lng === null) return;
    let cancelled = false;
    setJobsLoading(true);
    setJobsError(null);
    api
      .jobsNearby({ lat, lng, radius: radiusKm, limit: 200 })
      .then((list) => !cancelled && setJobs(list))
      .catch((err) => !cancelled && fail(err, setJobsError))
      .finally(() => !cancelled && setJobsLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, lng, radiusKm]);

  // Roadmap: depends on the role, the radius and the pinned job.
  useEffect(() => {
    if (!hasCV(profile) || !role) return;
    let cancelled = false;
    setRoadmapLoading(true);
    setRoadmapError(null);
    api
      .roadmap({ role, pinned_job_id: pinnedJobId, radius_km: radiusKm })
      .then((plan) => {
        if (cancelled) return;
        setRoadmap(plan);
        merge({ roadmap: plan });
      })
      .catch((err) => !cancelled && fail(err, setRoadmapError))
      .finally(() => !cancelled && setRoadmapLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, radiusKm, pinnedJobId, roadmapNonce]);

  const ranked = useMemo<RankedJob[]>(() => {
    const needle = keyword.trim().toLowerCase();
    return jobs
      .filter((j) => j.match_pct >= minMatch)
      .filter(
        (j) =>
          !needle ||
          `${j.title} ${j.company} ${j.city} ${j.matched.join(" ")} ${j.missing.join(" ")}`.toLowerCase().includes(needle),
      )
      .map((j) => ({ ...j, score: rankScore(j.match_pct, j.distance_km, radiusKm, matchWeight) }))
      .sort((a, b) => b.score - a.score || a.distance_km - b.distance_km);
  }, [jobs, minMatch, keyword, radiusKm, matchWeight]);

  const selectedJob = jobs.find((j) => j.id === selectedJobId) ?? null;
  const pinnedJob = jobs.find((j) => j.id === pinnedJobId) ?? null;

  async function changeLocation(next: Location | null) {
    if (!next) return;
    try {
      setProfile(await api.patchProfile({ location: next }));
    } catch (err) {
      fail(err, setJobsError);
    }
  }

  if (!hasCV(profile)) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-2xl font-bold">Career Map</h1>
        <p className="mt-2 text-slate-600">Upload a CV first; the map scores every nearby job against your skills.</p>
        <Link to="/upload" className="btn-primary mt-6">
          Upload a CV
        </Link>
      </div>
    );
  }

  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[320px_minmax(0,1fr)_320px]">
      <section className="card p-4" aria-label="Skill gap">
        <GapPanel
          roles={roles}
          role={role}
          onRoleChange={(name) => setSessionRole(name)}
          gap={gap}
          userSkills={profile.skills}
          adjacent={adjacent}
          loading={gapLoading}
          error={gapError}
          evidenceSources={profile.evidence_sources ?? []}
          onVerify={(name) => navigate(`/analyzer?claim=${encodeURIComponent(name)}`)}
        />
      </section>

      <section className="flex min-w-0 flex-col gap-3" aria-label="Nearby jobs">
        <div className="card p-3">
          <div className="flex flex-wrap items-center gap-3">
            <LocationPicker value={location} onChange={changeLocation} compact />
            {jobsLoading && <Loader2 className="h-4 w-4 animate-spin text-brand-600" aria-label="Loading jobs" />}
          </div>
          <div className="mt-3">
            <MapFilters count={ranked.length} total={jobs.length} />
          </div>
        </div>

        {jobsError && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{jobsError}</p>}

        {location ? (
          <div className="card h-[420px] overflow-hidden">
            <JobMap jobs={ranked} center={location} radiusKm={radiusKm} selectedId={selectedJobId} onSelect={setSelectedJobId} />
          </div>
        ) : (
          <div className="card flex h-[200px] items-center justify-center p-4 text-center text-sm text-slate-500">
            Pick a city or share your location to see who nearby is hiring for this role.
          </div>
        )}

        {selectedJob && (
          <JobDetail
            job={selectedJob}
            pinned={pinnedJobId === selectedJob.id}
            onPin={() => setPinnedJobId(selectedJob.id)}
            onUnpin={() => setPinnedJobId(null)}
            onClose={() => setSelectedJobId(null)}
          />
        )}

        <div className="card max-h-[420px] overflow-y-auto">
          <div className="sticky top-0 border-b border-slate-100 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Ranked jobs · pins green ≥ 75%, amber 50-74%, red &lt; 50%
          </div>
          <JobList jobs={ranked} selectedId={selectedJobId} pinnedId={pinnedJobId} onSelect={setSelectedJobId} />
        </div>
      </section>

      <section className="card p-4 xl:max-h-[calc(100vh-6rem)] xl:sticky xl:top-4" aria-label="Roadmap">
        <RoadmapTimeline
          roadmap={roadmap}
          role={gap?.role ?? role}
          loading={roadmapLoading}
          error={roadmapError}
          pinnedJob={pinnedJob}
          onRegenerate={() => setRoadmapNonce((n) => n + 1)}
          onUnpin={() => setPinnedJobId(null)}
        />
      </section>
    </div>
  );
}
