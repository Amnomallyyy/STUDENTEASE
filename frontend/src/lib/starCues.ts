// Live STAR checklist: ticks an element when a cue phrase appears in the live transcript.
// Same cue lists as backend/services/interview/star.py's offline fallback. The final, scored STAR
// result comes from the backend (LLM with verified quotes) after the answer is submitted.

export type StarKey = "situation" | "task" | "action" | "result";
export const STAR_KEYS: StarKey[] = ["situation", "task", "action", "result"];

const CUES: Record<StarKey, string[]> = {
  situation: [
    "when i was", "while i was", "at my", "in my", "during my", "during a", "during the", "last year",
    "last semester", "at the time", "in my final year", "in my internship", "at university", "we had a",
    "there was a", "our team was", "i was working", "i worked at", "i was part of",
  ],
  task: [
    "i needed to", "i had to", "my task", "my goal", "my job was", "i was responsible", "i was asked to",
    "my role was", "the goal was", "the challenge was", "the problem was", "we needed to", "i wanted to",
    "the task was", "i was in charge",
  ],
  action: [
    "i built", "i created", "i wrote", "i designed", "i decided", "i used", "i led", "i implemented",
    "i analysed", "i analyzed", "i organised", "i organized", "i set up", "i started", "i spoke to",
    "i talked to", "i reached out", "i automated", "i cleaned", "i tested", "i fixed", "i developed",
    "i proposed", "i trained", "i researched", "i made", "i changed", "i coordinated", "so i",
    "i followed", "i asked", "i practised", "i practiced", "i read", "i watched", "i studied", "i contacted", "i reviewed", "i planned", "i broke", "i split", "i prepared", "i scheduled", "i collected", "i compared", "i presented", "i explained", "i suggested", "i negotiated", "i learned how", "i taught", "i worked with",
  ],
  result: [
    "as a result", "which led to", "this led to", "resulted in", "in the end", "the outcome", "reduced",
    "increased", "improved", "saved", "cut", "grew", "we won", "i learned", "i learnt", "the result",
    "finally", "eventually", "got a", "was praised", "received", "achieved", "percent", "%",
  ],
};

const PATTERNS: Record<StarKey, RegExp[]> = Object.fromEntries(
  STAR_KEYS.map((k) => [
    k,
    CUES[k].map((c) => (c === "%" ? /%/ : new RegExp(`(?<![a-z])${c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![a-z])`))),
  ]),
) as Record<StarKey, RegExp[]>;

/** Which STAR elements have a cue in the text so far. */
export function liveStar(text: string): Record<StarKey, boolean> {
  const s = ` ${text.toLowerCase().replace(/\s+/g, " ")} `;
  return Object.fromEntries(STAR_KEYS.map((k) => [k, PATTERNS[k].some((re) => re.test(s))])) as Record<StarKey, boolean>;
}
