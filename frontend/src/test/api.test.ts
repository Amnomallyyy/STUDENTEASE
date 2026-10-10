import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, dataOf, parseSSE, query } from "../lib/api";
import type { ChatEvent } from "../types/api";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<string[]> {
  const out: string[] = [];
  for await (const data of parseSSE(stream)) out.push(data);
  return out;
}

describe("dataOf", () => {
  it("returns the data lines of a block and ignores comments", () => {
    expect(dataOf('data: {"a":1}')).toBe('{"a":1}');
    expect(dataOf(": keep-alive")).toBeNull();
    expect(dataOf("data: one\ndata: two")).toBe("one\ntwo");
  });
});

describe("parseSSE", () => {
  it("yields one payload per blank-line-separated event, across chunk boundaries", async () => {
    const chunks = ['data: {"type":"text","delta":"Hel', 'lo"}\n\ndata: {"type":"do', 'ne"}\n\n'];
    expect(await collect(streamOf(chunks))).toEqual(['{"type":"text","delta":"Hello"}', '{"type":"done"}']);
  });

  it("handles CRLF separators and a trailing event without a final blank line", async () => {
    expect(await collect(streamOf(["data: a\r\n\r\ndata: b"]))).toEqual(["a", "b"]);
  });
});

describe("query", () => {
  it("drops null, undefined and empty values", () => {
    expect(query({ role: "Data Analyst", radius_km: 25, lat: null, lng: undefined, keyword: "" })).toBe(
      "?role=Data+Analyst&radius_km=25",
    );
    expect(query({})).toBe("");
  });
});

describe("api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("turns a FastAPI error body into an ApiError with its detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "Upload a CV first." }), { status: 409 })),
    );
    const err = await api.getProfile().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 409, detail: "Upload a CV first." });
  });

  it("streams chat events in order and stops at done", async () => {
    const body = ['data: {"type":"open_map","radius_km":10,"keyword":null}\n\n', 'data: {"type":"text","delta":"Hi"}\n\n', 'data: {"type":"done"}\n\n'];
    vi.stubGlobal("fetch", vi.fn(async () => new Response(streamOf(body), { status: 200 })));
    const events: ChatEvent[] = [];
    await api.chat({ message: "jobs?", history: [] }, (e) => events.push(e));
    expect(events.map((e) => e.type)).toEqual(["open_map", "text", "done"]);
  });
});
