import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import WeeklyReflectionCard from "../src/components/WeeklyReflectionCard";
import type { WeeklyReflection } from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  getWeeklyReflection: vi.fn(),
  api: {
    reflection: { weekly: vi.fn() },
  },
}));

import { getWeeklyReflection } from "../src/lib/api";

const mockedGet = getWeeklyReflection as unknown as ReturnType<typeof vi.fn>;

const fakeReflection: WeeklyReflection = {
  window: { start: "2026-04-09", end: "2026-04-15" },
  entry_count: 7,
  days_with_entries: 7,
  mode: "normal",
  avg_mood: 3.6,
  avg_energy: 6.0,
  trend: { label: "improving", slope: 0.21 },
  best_day: { date: "2026-04-13", avg_mood: 4.5 },
  worst_day: { date: "2026-04-10", avg_mood: 2.5 },
  top_tags: [
    { tag: "sleep", count: 3 },
    { tag: "exercise", count: 2 },
  ],
  narrative: "Your mood trended upward across the week — something is working.",
  suggestion: null,
  reflection_prompt: "What would you do differently next week?",
  share_text:
    "Pulse — week of 2026-04-09 to 2026-04-15\nAvg mood 3.6/5 · Avg energy 6.0/10\nTrend: trending up\nBest day: 2026-04-13\nToughest day: 2026-04-10\nTop tags: sleep, exercise\nYour mood trended upward across the week — something is working.\n— Shared from Pulse",
};

describe("WeeklyReflectionCard", () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedGet.mockResolvedValue(fakeReflection);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders narrative, best/worst day, top tags, and reflection prompt", async () => {
    render(<WeeklyReflectionCard />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Your mood trended upward across the week — something is working."
        )
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/2026-04-13/)).toBeInTheDocument();
    expect(screen.getByText(/2026-04-10/)).toBeInTheDocument();
    expect(screen.getByText("sleep")).toBeInTheDocument();
    expect(screen.getByText("exercise")).toBeInTheDocument();
    expect(
      screen.getByText("What would you do differently next week?")
    ).toBeInTheDocument();
  });

  it("copies share_text to the clipboard when Copy summary is clicked", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(<WeeklyReflectionCard />);

    const button = await screen.findByRole("button", { name: /copy summary/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledTimes(1);
    });
    expect(writeText).toHaveBeenCalledWith(fakeReflection.share_text);
  });

  it("renders empty mode: shows the empty-state prompt and hides the Copy button", async () => {
    const emptyReflection: WeeklyReflection = {
      window: { start: "2026-04-09", end: "2026-04-15" },
      entry_count: 0,
      days_with_entries: 0,
      mode: "empty",
      avg_mood: null,
      avg_energy: null,
      trend: { label: "insufficient_data", slope: null },
      best_day: null,
      worst_day: null,
      top_tags: [],
      narrative: null,
      suggestion: null,
      reflection_prompt:
        "No entries in the past 7 days. Start with how you're feeling right now.",
      share_text: null,
    };
    mockedGet.mockReset();
    mockedGet.mockResolvedValue(emptyReflection);

    render(<WeeklyReflectionCard />);

    await waitFor(() => {
      expect(
        screen.getByText(emptyReflection.reflection_prompt!)
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: /copy summary/i })
    ).not.toBeInTheDocument();
  });

  it("renders sparse mode: hides best/worst section, keeps Copy button", async () => {
    const sparseReflection: WeeklyReflection = {
      window: { start: "2026-04-09", end: "2026-04-15" },
      entry_count: 2,
      days_with_entries: 2,
      mode: "sparse",
      avg_mood: 3.5,
      avg_energy: 6.0,
      trend: { label: "insufficient_data", slope: null },
      best_day: null,
      worst_day: null,
      top_tags: [{ tag: "sleep", count: 2 }],
      narrative:
        "A quiet week in the log — even a few entries help paint a picture.",
      suggestion: null,
      reflection_prompt: "What stood out about the moments you did capture?",
      share_text:
        "Pulse — week of 2026-04-09 to 2026-04-15\nAvg mood 3.5/5 · Avg energy 6.0/10\nTrend: not enough data yet\nTop tags: sleep\nA quiet week in the log — even a few entries help paint a picture.\n— Shared from Pulse",
    };
    mockedGet.mockReset();
    mockedGet.mockResolvedValue(sparseReflection);

    render(<WeeklyReflectionCard />);

    await waitFor(() => {
      expect(screen.getByText(sparseReflection.narrative!)).toBeInTheDocument();
    });
    expect(screen.queryByText(/best day/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/toughest day/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /copy summary/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(sparseReflection.reflection_prompt!)
    ).toBeInTheDocument();
  });

  it("renders tough mode: shows the suggestion and contains no forbidden substrings", async () => {
    const toughReflection: WeeklyReflection = {
      window: { start: "2026-04-09", end: "2026-04-15" },
      entry_count: 7,
      days_with_entries: 7,
      mode: "tough",
      avg_mood: 2.0,
      avg_energy: 4.0,
      trend: { label: "flat", slope: 0.0 },
      best_day: { date: "2026-04-14", avg_mood: 2.5 },
      worst_day: { date: "2026-04-10", avg_mood: 1.5 },
      top_tags: [{ tag: "outdoors", count: 3 }],
      narrative:
        "It's been a heavier stretch — small steps still count from here.",
      suggestion:
        "You logged outdoors often this stretch — one more this week, if you can?",
      reflection_prompt:
        "What's one small thing that helped, even a little?",
      share_text:
        "Pulse — week of 2026-04-09 to 2026-04-15\nAvg mood 2.0/5 · Avg energy 4.0/10\nTrend: holding steady\nTop tags: outdoors\nIt's been a heavier stretch — small steps still count from here.\n— Shared from Pulse",
    };
    mockedGet.mockReset();
    mockedGet.mockResolvedValue(toughReflection);

    const { container } = render(<WeeklyReflectionCard />);

    await waitFor(() => {
      expect(screen.getByText(toughReflection.suggestion!)).toBeInTheDocument();
    });
    expect(screen.getByText(toughReflection.narrative!)).toBeInTheDocument();
    expect(
      screen.getByText(toughReflection.reflection_prompt!)
    ).toBeInTheDocument();

    const lowered = (container.textContent || "").toLowerCase();
    for (const forbidden of ["worst", "lowest", "rough week", "bad week"]) {
      expect(lowered).not.toContain(forbidden);
    }
  });
});
