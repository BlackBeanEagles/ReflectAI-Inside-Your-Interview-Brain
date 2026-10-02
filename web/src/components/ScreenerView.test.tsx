import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ScreenerView from "./ScreenerView";

const kw = (keyword: string, weight = 1) => ({ keyword, weight });

describe("ScreenerView", () => {
  it("highlights matched keywords where they appear in the résumé", () => {
    const { container } = render(
      <ScreenerView
        text="Built services in Python and C++."
        matched={[kw("python"), kw("c++")]}
        missing={[]}
      />,
    );
    const marks = [...container.querySelectorAll("mark")].map((m) => m.textContent);
    expect(marks).toEqual(["Python", "C++"]);
  });

  it("lists missing keywords heaviest first", () => {
    render(
      <ScreenerView text="Python." matched={[kw("python")]} missing={[kw("docker", 2), kw("kubernetes", 9)]} />,
    );
    const items = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toEqual(["kubernetes", "docker"]);
  });

  it("says why there is no marked-up copy for an uploaded PDF instead of faking one", () => {
    const { container } = render(
      <ScreenerView text={null} matched={[kw("python")]} missing={[kw("docker")]} />,
    );
    expect(screen.getByText(/only available for pasted text/i)).toBeInTheDocument();
    expect(container.querySelector("mark")).toBeNull();
    expect(screen.getByText("docker")).toBeInTheDocument();
  });

  it("reports the match count", () => {
    render(<ScreenerView text="Python." matched={[kw("python")]} missing={[kw("go"), kw("rust")]} />);
    expect(screen.getByText(/1 of 3 keywords/)).toBeInTheDocument();
  });
});

describe("labels and highlighting from the scorer", () => {
  it("shows the posting's wording, not the normalised key", () => {
    render(
      <ScreenerView
        text="Python."
        matched={[]}
        missing={[{ keyword: "redi", weight: 2, label: "Redis", found_as: [] }]}
      />,
    );
    expect(screen.getByText("Redis")).toBeInTheDocument();
    expect(screen.queryByText("redi")).not.toBeInTheDocument();
  });

  it("highlights the résumé's own wording, including through a synonym", () => {
    const { container } = render(
      <ScreenerView
        text="Skills: PostgreSQL"
        matched={[{ keyword: "postgresql", weight: 2, label: "Postgres", found_as: ["PostgreSQL"] }]}
        missing={[]}
      />,
    );
    expect([...container.querySelectorAll("mark")].map((m) => m.textContent)).toEqual(["PostgreSQL"]);
  });

  it("caps the missing list but still counts everything", () => {
    const missing = Array.from({ length: 20 }, (_, i) => ({ keyword: `tool${i}`, weight: 20 - i }));
    render(<ScreenerView text="x" matched={[]} missing={missing} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(12);
    expect(screen.getByText(/and 8 lower-weighted terms/)).toBeInTheDocument();
    expect(screen.getByText(/0 of 20 keywords/)).toBeInTheDocument();
  });
});
