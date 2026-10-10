// AUTO-GENERATED from backend/schemas by `python -m backend.schemas.generate_ts`.
// Do not edit by hand: change the Pydantic models and regenerate.

export interface AdjacentRole {
  role: string;
  match_pct: number;
}

export interface Anomaly {
  id: string;
  kind: string;
  claim: string;
  evidence: string;
  severity: number;
  suggested_fix: string;
}

export interface AnswerResult {
  question: InterviewQuestion;
  transcript: string;
  verbal: VerbalMetrics;
  non_verbal: NonVerbalMetrics | null;
  verbal_score: number;
  rewritten_answer: string;
  coaching_notes: string[];
  content_feedback: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  message: string;
  history?: ChatMessage[];
}

export interface Experience {
  title: string;
  organisation: string;
  summary: string;
  years: number | null;
  skills: string[];
}

export interface ExtractedCV {
  skills: Skill[];
  projects: Project[];
  experience: Experience[];
}

export interface GapResponse {
  role: string;
  match: MatchResult;
  market_gaps: MarketGap[];
  jobs_nearby: JobMatch[];
}

export interface InterviewQuestion {
  id: string;
  text: string;
  kind: "behavioural" | "technical" | "situational";
}

export interface InterviewReport {
  role: string;
  answers: AnswerResult[];
  verbal_score: number;
  non_verbal_score: number | null;
  readiness: number;
  verbal_weight: number;
  non_verbal_weight: number;
  fix_first: string;
}

export interface Job {
  id: string;
  company: string;
  title: string;
  city: string;
  lat: number;
  lng: number;
  requirements_text: string;
  required_skills: Skill[];
  source_url: string | null;
  source_name: string;
  posted_at: string;
  synthetic: boolean;
}

export interface JobMatch {
  id: string;
  match_pct: number;
  matched: string[];
  missing: string[];
  distance_km: number;
}

export interface Location {
  lat: number;
  lng: number;
  city: string;
}

export interface MarketGap {
  skill: string;
  jobs_requiring: number;
  jobs_total: number;
  priority: number;
}

export interface MatchResult {
  match_pct: number;
  evidenced_pct: number | null;
  matched: SkillMatch[];
  partial: SkillMatch[];
  missing: Skill[];
}

export interface NonVerbalMetrics {
  eye_contact_pct: number;
  head_stability: number;
  posture_flags: ("slouching" | "leaning_out_of_frame" | "shoulders_tilted")[];
  fidget_pct: number;
  expression_label: "neutral" | "engaged" | "tense";
  nod_count: number;
  body_language_score: number;
  hand_actions: Record<string, number>;
}

export interface NonVerbalSample {
  t: number;
  head_yaw_deg: number;
  head_pitch_deg: number;
  nose_x: number;
  nose_y: number;
  shoulder_tilt_deg: number;
  forward_lean: number;
  wrist_velocity: number;
  smile: number;
  brow: number;
  nodded: boolean;
  eye_contact_frac: number | null;
  face_detected: boolean;
  pose_detected: boolean;
  hands_visible: boolean;
  tension: number | null;
  hand_action: "covering_mouth" | "touching_face" | "touching_head" | "fiddling" | "restless" | "fist" | "gesturing" | "resting" | null;
}

export interface Profile {
  mode: UserMode;
  target_role: string | null;
  location: Location | null;
  skills: Skill[];
  projects: Project[];
  experience: Experience[];
  gap: MatchResult | null;
  market_gaps: MarketGap[];
  jobs_nearby: JobMatch[];
  roadmap: Roadmap | null;
  anomalies: Anomaly[];
  integrity_score: number | null;
  evidence_sources: ("cv" | "github" | "linkedin" | "portfolio")[];
  interview: InterviewReport | null;
}

export interface ProfilePatch {
  mode?: UserMode | null;
  target_role?: string | null;
  location?: Location | null;
}

export interface Project {
  name: string;
  description: string;
  skills: string[];
  url: string | null;
}

export interface Resource {
  title: string;
  url: string;
  hours: number;
}

export interface Roadmap {
  weeks: RoadmapWeek[];
  pinned_job_id: string | null;
}

export interface RoadmapTask {
  title: string;
  skill: string;
  resource_url: string | null;
  hours: number;
  done: boolean;
}

export interface RoadmapWeek {
  week: number;
  focus: string;
  tasks: RoadmapTask[];
}

export interface Role {
  id: string;
  name: string;
  skills: Skill[];
}

export interface Skill {
  name: string;
  category: SkillCategory;
  evidence: string[];
  sources: ("cv" | "github" | "linkedin" | "portfolio")[];
  years: number | null;
  confidence: number;
  weight: number;
  requirement: "core" | "preferred" | null;
}

export type SkillCategory = "language" | "tool" | "framework" | "soft_skill" | "domain";

export interface SkillMatch {
  name: string;
  matched_to: string;
  similarity: number;
  sources: ("cv" | "github" | "linkedin" | "portfolio")[];
}

export interface StarElement {
  present: boolean;
  evidence_span: string;
  strength: number;
}

export interface StarScore {
  situation: StarElement;
  task: StarElement;
  action: StarElement;
  result: StarElement;
  source: "llm" | "rules";
}

export type UserMode = "student" | "job_seeker";

export interface VerbalMetrics {
  word_count: number;
  duration_s: number;
  wpm: number;
  pace_band: "slow" | "within" | "fast" | "unknown";
  filler_counts: Record<string, number>;
  fillers_per_100_words: number;
  star: StarScore;
  relevance: number | null;
  concise: boolean;
  component_scores: Record<string, number>;
}
