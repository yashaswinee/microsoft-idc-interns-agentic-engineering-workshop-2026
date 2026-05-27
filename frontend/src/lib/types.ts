export interface Entry {
  id: string;
  mood: number;
  energy: number;
  note: string | null;
  tags: string[];
  timestamp: string;
}

export interface EntryCreate {
  mood: number;
  energy: number;
  note?: string;
  tags: string[];
}

export interface DailyStat {
  date: string;
  avg_mood: number | null;
  avg_energy: number | null;
  count: number;
}

export interface WeeklyStat {
  week_start: string;
  avg_mood: number | null;
  avg_energy: number | null;
  count: number;
}

export interface HeatmapDay {
  date: string;
  avg_mood: number | null;
  count: number;
}

export interface ReflectionWindow {
  start: string;
  end: string;
}

export interface TrendInfo {
  label: string;
  slope: number | null;
}

export interface DayAverage {
  date: string;
  avg_mood: number;
}

export interface TagCount {
  tag: string;
  count: number;
}

export interface WeeklyReflection {
  window: ReflectionWindow;
  entry_count: number;
  days_with_entries: number;
  mode: string;
  avg_mood: number | null;
  avg_energy: number | null;
  trend: TrendInfo;
  best_day: DayAverage | null;
  worst_day: DayAverage | null;
  top_tags: TagCount[];
  narrative: string | null;
  suggestion: string | null;
  reflection_prompt: string | null;
  share_text: string | null;
}

export interface TagsResponse {
  predefined: string[];
  custom: string[];
}

export const MOOD_EMOJIS: Record<number, string> = {
  1: "😢",
  2: "😕",
  3: "😐",
  4: "🙂",
  5: "😄",
};

export const MOOD_LABELS: Record<number, string> = {
  1: "Awful",
  2: "Bad",
  3: "Okay",
  4: "Good",
  5: "Great",
};
