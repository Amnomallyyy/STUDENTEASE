// Typed fetch wrapper for the CareerLens API (docs/api.md). Every call goes through request(), so errors
// always surface as ApiError with the FastAPI `detail` message, and the base URL lives in one place.
import type { AdjacentRole, ChatRequest, GapResponse, Job, Profile, ProfilePatch, Roadmap, Role } from "../types/profile";
import type { AnalyzerReport, BuiltWithItem, ChatEvent, Health, JobNearby } from "../types/api";

export const API_URL = ((import.meta.env.VITE_API_URL as string | undefined) || "http://127.0.0.1:8000").replace(
  /\/+$/,
  "",
);

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return String(err);
}

async function readDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ");
    }
    return JSON.stringify(body);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(0, `Cannot reach the CareerLens API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) throw new ApiError(res.status, await readDetail(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

type Param = string | number | boolean | null | undefined;

export function query(params: Record<string, Param>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export interface UploadOptions {
  target_role?: string | null;
  mode?: "student" | "job_seeker";
  lat?: number | null;
  lng?: number | null;
  city?: string;
}

export interface AnalyzerInput {
  github_username?: string;
  linkedin_text?: string;
  linkedin_export?: File | null;
}

export const api = {
  health: () => request<Health>("/health"),
  builtWith: () => request<BuiltWithItem[]>("/built-with"),

  getProfile: () => request<Profile>("/profile"),
  uploadCV: (file: File, opts: UploadOptions = {}) => {
    const form = new FormData();
    form.append("file", file, file.name);
    if (opts.target_role) form.append("target_role", opts.target_role);
    if (opts.mode) form.append("mode", opts.mode);
    if (opts.lat != null && opts.lng != null) {
      form.append("lat", String(opts.lat));
      form.append("lng", String(opts.lng));
    }
    if (opts.city) form.append("city", opts.city);
    return request<Profile>("/profile/cv", { method: "POST", body: form });
  },
  patchProfile: (patch: ProfilePatch) => request<Profile>("/profile", json("PATCH", patch)),
  deleteProfile: () => request<void>("/profile", { method: "DELETE" }),

  roles: () => request<Role[]>("/career/roles"),
  gap: (params: { role?: string | null; radius_km?: number; lat?: number | null; lng?: number | null }) =>
    request<GapResponse>(`/career/gap${query(params)}`),
  roadmap: (params: { role?: string | null; pinned_job_id?: string | null; radius_km?: number }) =>
    request<Roadmap>(`/career/roadmap${query(params)}`),
  adjacent: (params: { role?: string | null; limit?: number }) =>
    request<AdjacentRole[]>(`/career/adjacent${query(params)}`),

  jobsNearby: (params: {
    lat?: number | null;
    lng?: number | null;
    radius?: number;
    limit?: number;
    min_match?: number;
  }) => request<JobNearby[]>(`/jobs/nearby${query(params)}`),
  job: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}`),

  runAnalyzer: (input: AnalyzerInput) => {
    const form = new FormData();
    if (input.github_username?.trim()) form.append("github_username", input.github_username.trim());
    if (input.linkedin_text?.trim()) form.append("linkedin_text", input.linkedin_text.trim());
    if (input.linkedin_export) form.append("linkedin_export", input.linkedin_export, input.linkedin_export.name);
    return request<AnalyzerReport>("/analyzer/run", { method: "POST", body: form });
  },
  analyzerReport: (report_id?: string | null) => request<AnalyzerReport>(`/analyzer/report${query({ report_id })}`),

  /** POST /chat and call onEvent for every server-sent event until the stream ends. */
  chat: async (body: ChatRequest, onEvent: (event: ChatEvent) => void, signal?: AbortSignal): Promise<void> => {
    let res: Response;
    try {
      res = await fetch(`${API_URL}/chat`, { ...json("POST", body), signal });
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      throw new ApiError(0, `Cannot reach the CareerLens API at ${API_URL}. Is the backend running?`);
    }
    if (!res.ok) throw new ApiError(res.status, await readDetail(res));
    if (!res.body) throw new ApiError(res.status, "The chat response had no body.");
    try {
      for await (const data of parseSSE(res.body)) {
        let event: ChatEvent;
        try {
          event = JSON.parse(data) as ChatEvent;
        } catch {
          continue;
        }
        onEvent(event);
        if (event.type === "done") return;
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      throw err;
    }
  },
};

/** The `data:` payload of one SSE block (lines joined with \n), or null when the block carries no data. */
export function dataOf(block: string): string | null {
  const lines = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).replace(/^ /, ""));
  return lines.length ? lines.join("\n") : null;
}

/** Yield the data of each server-sent event as it arrives. Events are separated by a blank line. */
export async function* parseSSE(stream: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function* drain(final: boolean): Generator<string> {
    let index: number;
    while ((index = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const data = dataOf(block);
      if (data !== null) yield data;
    }
    if (final && buffer.trim()) {
      const data = dataOf(buffer);
      buffer = "";
      if (data !== null) yield data;
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      yield* drain(false);
    }
    buffer += decoder.decode().replace(/\r\n/g, "\n");
    yield* drain(true);
  } finally {
    reader.releaseLock();
  }
}
