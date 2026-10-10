import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ScoreTile from "../components/ScoreTile";
import ProgressSteps from "../components/ProgressSteps";

describe("ScoreTile", () => {
  it("renders the label, value and sub-text and links to the module", () => {
    render(
      <MemoryRouter>
        <ScoreTile label="Role match" value="65%" sub="3 skills missing" to="/career" band="amber" />
      </MemoryRouter>,
    );
    expect(screen.getByText("Role match")).toBeInTheDocument();
    expect(screen.getByText("65%")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/career");
  });
});

describe("ProgressSteps", () => {
  it("marks earlier steps done, the current one active and shows an error", () => {
    render(<ProgressSteps steps={["Read", "Extract", "Match"]} current={1} error="LLM unavailable" />);
    expect(screen.getByText("LLM unavailable")).toBeInTheDocument();
    expect(screen.getByText("Match")).toHaveClass("text-slate-400");
  });
});
