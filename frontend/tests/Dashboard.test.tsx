import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Dashboard from "../src/pages/Dashboard";

vi.mock("../src/lib/api", () => ({
  getWeeklyReflection: vi.fn().mockResolvedValue(null),
  api: {
    stats: {
      daily: vi.fn().mockResolvedValue([]),
      heatmap: vi.fn().mockResolvedValue([]),
    },
    entries: {
      list: vi.fn().mockResolvedValue([]),
    },
    reflection: {
      weekly: vi.fn().mockResolvedValue(null),
    },
  },
}));

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );
}

describe("Dashboard", () => {
  it("shows loading state initially", () => {
    renderDashboard();
    expect(screen.getByText("Loading your pulse...")).toBeInTheDocument();
  });

  it("renders the dashboard heading after loading", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
    });
  });

  it("shows 'No entries yet' message when no entries exist", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(
        screen.getByText("No entries yet. Start by logging your first mood!")
      ).toBeInTheDocument();
    });
  });

  it("shows summary cards after loading", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Today's Mood")).toBeInTheDocument();
      expect(screen.getByText("Today's Energy")).toBeInTheDocument();
      expect(screen.getByText("Entries Today")).toBeInTheDocument();
    });
  });
});
