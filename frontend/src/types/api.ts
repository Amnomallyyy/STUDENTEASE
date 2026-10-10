// Hand-written mirrors of backend/schemas/analyzer.py (not re-exported by backend.schemas, so absent from
// the generated profile.ts), the /health and /built-with payloads, and the /chat event stream (docs/api.md).
import type { Anomaly, ChatMessage, JobMatch, MatchResult } from "./profile";

export type SkillSource = "cv" | "github" | "linkedin" | "portfolio";

export interface SkillCluster {
  name: string;
  sources: SkillSource[];
  members: string[];
  mention_count: number;
}

export interface AnalyzerReport {
  report_id: string;
  anomalies: Anomaly[];
  integrity_score: number | null;
  clusters: SkillCluster[];
  sources: Partial<Record<SkillSource, number>>;
  github_username: string | null;
  /** The profile's target role when the run refreshed its gap, else null. */
  target_role: string | null;
  /** The target-role match recomputed with the merged skills; evidenced_pct counts external backing only. */
  match: MatchResult | null;
}

/** A scored job plus the listing fields the map needs for its pins (superset of JobMatch). */
export interface JobNearby extends JobMatch {
  company: string;
  title: string;
  city: string;
  lat: number;
  lng: number;
  synthetic: boolean;
  source_url: string | null;
  /** Board the posting was listed on (e.g. "LinkedIn", "Indeed"); empty for sample listings. */
  source_name: string;
  /** As the board states it, e.g. "5 days ago"; empty for sample listings. */
  posted_at: string;
}

/** GET /geo/place: a free-text place resolved to coordinates. */
export interface Place {
  lat: number;
  lng: number;
  name: string;
  city: string;
}

export interface BuiltWithItem {
  name: string;
  kind: string;
  licence: string;
  url: string;
}

export interface Health {
  status: string;
  llm_provider: string;
  embed_provider: string;
  data: { roles: number | null; jobs: number | null; resources: number | null };
}

export type ChatAction =
  | { type: "open_map"; radius_km: number; keyword: string | null }
  | { type: "open_career_map"; role: string }
  | { type: "open_interview"; role: string };

export type ChatEvent =
  | ChatAction
  | { type: "text"; delta: string }
  | { type: "done" }
  | { type: "error"; message: string };

/** A chat message as shown in the panel: the API shape plus the actions the answer triggered. */
export interface UIMessage extends ChatMessage {
  actions?: ChatAction[];
  error?: string;
}
