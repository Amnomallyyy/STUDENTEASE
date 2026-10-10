import { render } from "@testing-library/react";
import { MiniMarkdown, parseBlocks } from "../lib/miniMarkdown";

const reply = `**First step:** Open the **Career Map** to see your gap.

- It will list matched, partial, and missing skills.
- You'll see the most in-demand abilities for jobs near you.

*Open the Career Map module to get started.*`;

describe("MiniMarkdown", () => {
  it("renders bold, italics and bullet lists without showing the markers", () => {
    const { container } = render(<MiniMarkdown text={reply} />);
    expect(container.textContent).not.toContain("**");
    expect(container.querySelectorAll("strong")).toHaveLength(2);
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.querySelector("em")?.textContent).toBe("Open the Career Map module to get started.");
  });

  it("groups numbered lists and keeps paragraphs apart", () => {
    const blocks = parseBlocks("Plan:\n1. SQL\n2. Tableau\n\nGood luck");
    expect(blocks.map((b) => b.kind)).toEqual(["p", "ol", "p"]);
  });

  it("leaves unfinished markers (mid-stream) and HTML as plain text", () => {
    const { container } = render(<MiniMarkdown text={"**Partial reply <b>x</b>"} />);
    expect(container.textContent).toBe("**Partial reply <b>x</b>");
    expect(container.querySelector("b")).toBeNull();
  });

  it("does not treat a multiplication-like asterisk with spaces as italics", () => {
    const { container } = render(<MiniMarkdown text={"2 * 3 * 4"} />);
    expect(container.querySelector("em")).toBeNull();
  });
});
