// Same cases as backend/tests/test_fillers.py and test_star_schema.py, so the live gauges agree with
// the scored result.
import { describe, expect, it } from "vitest";
import { countFillers, findFillers, wordCount } from "../fillers";
import { liveStar } from "../starCues";

describe("live filler counter", () => {
  it("counts always-fillers and phrases", () => {
    expect(countFillers("Um, I mean, it was basically, uh, kind of broken. You know? Actually it was.")).toEqual({
      um: 1,
      "i mean": 1,
      basically: 1,
      uh: 1,
      "kind of": 1,
      "you know": 1,
      actually: 1,
    });
  });

  it("counts like and so only as fillers", () => {
    expect(countFillers("I would like to say it looks like SQL. It was like, slow. And like we fixed it.").like).toBe(2);
    expect(countFillers("So, I built it so that it ran. It was so much faster. Then, so we shipped it.").so).toBe(2);
    expect(countFillers("I designed the schema and wrote the queries myself.")).toEqual({});
  });

  it("returns positions for highlighting, in order", () => {
    const text = "So, um, it worked";
    expect(findFillers(text).map((h) => text.slice(h.start, h.end))).toEqual(["So", "um"]);
    expect(wordCount("It's a 2-day job, isn't it?")).toBe(7);
  });
});

describe("live STAR checklist", () => {
  it("ticks elements as their cue phrases are heard", () => {
    const text =
      "Last year during my internship the report took two days. My task was to automate it. " +
      "I wrote a Python script. As a result, it took 10 minutes.";
    expect(liveStar(text)).toEqual({ situation: true, task: true, action: true, result: true });
    expect(liveStar("I like data.")).toEqual({ situation: false, task: false, action: false, result: false });
  });

  it("does not match cues inside other words", () => {
    expect(liveStar("The cutting-edge tool").result).toBe(false); // "cut" only as a word
  });
});
