import type {
  DailyStat,
  Entry,
  EntryCreate,
  HeatmapDay,
  TagsResponse,
  WeeklyReflection,
  WeeklyStat,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  entries: {
    list: (startDate?: string, endDate?: string) => {
      const params = new URLSearchParams();
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      const qs = params.toString();
      return request<Entry[]>(`/entries${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<Entry>(`/entries/${id}`),
    create: (data: EntryCreate) =>
      request<Entry>("/entries", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<void>(`/entries/${id}`, { method: "DELETE" }),
  },
  stats: {
    daily: () => request<DailyStat[]>("/stats/daily"),
    weekly: () => request<WeeklyStat[]>("/stats/weekly"),
    heatmap: () => request<HeatmapDay[]>("/stats/heatmap"),
  },
  reflection: {
    weekly: () => request<WeeklyReflection>("/reflection/weekly"),
  },
  tags: () => request<TagsResponse>("/tags"),
};

export const getWeeklyReflection = () => api.reflection.weekly();
