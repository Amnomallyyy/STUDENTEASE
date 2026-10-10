// Interview endpoints (M3). Uses the shared API_URL from lib/api.ts so there is one backend address.

import type { AnswerResult, InterviewQuestion, InterviewReport } from "../types/profile";
import { API_URL } from "./api";
import { withSession } from "./session";
import type { NonVerbalSample } from "../vision/types";

export const API_BASE: string = API_URL;

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, withSession(init));
  } catch {
    throw new ApiError(`Can't reach the CareerLens backend at ${API_BASE}. Is it running? (uvicorn backend.main:app)`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    throw new ApiError(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export function startInterview(role: string, count = 3): Promise<InterviewQuestion[]> {
  return request<InterviewQuestion[]>("/interview/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, count }),
  });
}

export interface AnswerSubmission {
  questionId: string;
  transcript: string;
  /** 0 for a typed answer. */
  durationS: number;
  /** [] when the camera was off. */
  samples: NonVerbalSample[];
  /** Recorded answer audio for the Whisper pass; omitted for typed answers. */
  audio?: Blob | null;
}

export function submitAnswer(a: AnswerSubmission): Promise<AnswerResult> {
  const form = new FormData();
  form.append("question_id", a.questionId);
  form.append("transcript", a.transcript);
  form.append("duration_s", String(Math.max(0, a.durationS)));
  form.append("samples", JSON.stringify(a.samples));
  if (a.audio && a.audio.size > 0) form.append("audio", a.audio, `answer.${a.audio.type.includes("mp4") ? "mp4" : "webm"}`);
  return request<AnswerResult>("/interview/answer", { method: "POST", body: form });
}

/** Whisper text for a few seconds of audio, for live filler counting; null when no Whisper is configured. */
export async function transcribeClip(clip: Blob): Promise<string | null> {
  const form = new FormData();
  form.append("audio", clip, `clip.${clip.type.includes("mp4") ? "mp4" : "webm"}`);
  const r = await request<{ text: string | null }>("/interview/transcribe", { method: "POST", body: form });
  return r.text;
}

export function getReport(): Promise<InterviewReport> {
  return request<InterviewReport>("/interview/report");
}
