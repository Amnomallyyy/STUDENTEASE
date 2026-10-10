import { describe, expect, it } from "vitest";
import { keywordMatch, normalise } from "../lib/keywordMatch";

describe("normalise", () => {
  it("lower-cases, keeps + # . and collapses spaces", () => {
    expect(normalise("  C++  ")).toBe("c++");
    expect(normalise("C#")).toBe("c#");
    expect(normalise(".NET Core")).toBe(".net core");
    expect(normalise("Node.js / Express")).toBe("node.js express");
  });
});

describe("keywordMatch", () => {
  const role = [
    { name: "SQL", weight: 3 },
    { name: "Python", weight: 3 },
    { name: "Tableau", weight: 2 },
    { name: "Communication", weight: 1 },
  ];

  it("counts only exact (normalised) name matches, weighted", () => {
    const result = keywordMatch([{ name: "python" }, { name: "PostgreSQL" }, { name: "Data viz" }], role);
    // Only Python (3 of 9) matches by keyword: PostgreSQL != SQL, Data viz != Tableau.
    expect(result.match_pct).toBe(33.3);
    expect(result.matched).toEqual([{ name: "python", matched_to: "Python" }]);
    expect(result.missing).toEqual(["SQL", "Tableau", "Communication"]);
  });

  it("gives 100 when every required skill is present and 0 when none", () => {
    expect(keywordMatch(role, role).match_pct).toBe(100);
    expect(keywordMatch([], role).match_pct).toBe(0);
    expect(keywordMatch([{ name: "SQL" }], []).match_pct).toBe(0);
  });

  it("defaults a missing weight to 1", () => {
    const result = keywordMatch([{ name: "SQL" }], [{ name: "SQL" }, { name: "Excel" }]);
    expect(result.match_pct).toBe(50);
  });
});
