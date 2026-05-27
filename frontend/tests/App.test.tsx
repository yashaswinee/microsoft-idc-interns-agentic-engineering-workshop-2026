import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import App from "../src/App";

// Mock API calls used by pages
vi.mock("../src/lib/api", () => ({
  getWeeklyReflection: vi.fn().mockResolvedValue(null),
  api: {
    stats: {
      daily: vi.fn().mockResolvedValue([]),
      weekly: vi.fn().mockResolvedValue([]),
      heatmap: vi.fn().mockResolvedValue([]),
    },
    entries: {
      list: vi.fn().mockResolvedValue([]),
      create: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue(undefined),
    },
    reflection: {
      weekly: vi.fn().mockResolvedValue(null),
    },
    tags: vi.fn().mockResolvedValue({ predefined: [], custom: [] }),
  },
}));

describe("App routing", () => {
  it("renders Dashboard on /", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    });
  });

  it("renders Log Entry page on /log", async () => {
    render(
      <MemoryRouter initialEntries={["/log"]}>
        <App />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Log Entry" })).toBeInTheDocument();
    });
  });

  it("renders History page on /history", async () => {
    render(
      <MemoryRouter initialEntries={["/history"]}>
        <App />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "History" })).toBeInTheDocument();
    });
  });

  it("renders navigation in layout", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText("Pulse")).toBeInTheDocument();
  });
});
