// Live filler counter: the same rules as backend/services/interview/fillers.py (the backend's count
// is the one that is scored; this one only drives the live gauge and transcript highlighting).

const ALWAYS = ["um", "uh", "er", "erm", "uhm", "you know", "basically", "actually", "literally", "i mean", "kind of", "sort of"];
const ALWAYS_RE = new RegExp(`\\b(${[...ALWAYS].sort((a, b) => b.length - a.length).join("|")})\\b`, "gi");
const WORD_RE = /[A-Za-z']+/g;
const LIKE_AFTER = new Set(["and", "but", "was", "is", "were", "it's", "its", "um", "uh", "er", "erm", "just"]);
const SO_NOT_BEFORE = new Set(["that", "much", "many", "far", "long"]);

export interface FillerHit {
  start: number;
  end: number;
  word: string;
}

/** Every filler occurrence with its position, for highlighting. */
export function findFillers(text: string): FillerHit[] {
  const hits: FillerHit[] = [];
  for (const m of text.matchAll(ALWAYS_RE)) hits.push({ start: m.index!, end: m.index! + m[0].length, word: m[1].toLowerCase() });
  const words = [...text.matchAll(WORD_RE)];
  words.forEach((m, i) => {
    const w = m[0].toLowerCase();
    const start = m.index!;
    const end = start + m[0].length;
    const before = text.slice(0, start).trimEnd();
    const after = text.slice(end).trimStart();
    const prev = i ? words[i - 1][0].toLowerCase() : "";
    const next = i + 1 < words.length ? words[i + 1][0].toLowerCase() : "";
    if (w === "like" && (before.endsWith(",") || after.startsWith(",") || (LIKE_AFTER.has(prev) && !/[.!?]$/.test(before))))
      hits.push({ start, end, word: "like" });
    else if (w === "so" && (!before || /[.!?,;]$/.test(before)) && !SO_NOT_BEFORE.has(next)) hits.push({ start, end, word: "so" });
  });
  return hits.sort((a, b) => a.start - b.start);
}

export function countFillers(text: string): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const h of findFillers(text)) counts[h.word] = (counts[h.word] ?? 0) + 1;
  return counts;
}

export function wordCount(text: string): number {
  return (text.match(/[A-Za-z0-9']+/g) ?? []).length;
}
