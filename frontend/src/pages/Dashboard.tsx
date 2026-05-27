import { useEffect, useState } from "react";
import CalendarHeatmap from "../components/CalendarHeatmap";
import EntryCard from "../components/EntryCard";
import TimelineChart from "../components/TimelineChart";
import WeeklyReflectionCard from "../components/WeeklyReflectionCard";
import { api } from "../lib/api";
import type { DailyStat, Entry, HeatmapDay } from "../lib/types";
import { MOOD_EMOJIS } from "../lib/types";

export default function Dashboard() {
  const [daily, setDaily] = useState<DailyStat[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapDay[]>([]);
  const [recent, setRecent] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.stats.daily(), api.stats.heatmap(), api.entries.list()])
      .then(([d, h, e]) => {
        setDaily(d);
        setHeatmap(h);
        setRecent(e.slice(0, 5));
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading your pulse...
      </div>
    );
  }

  // Today's summary
  const today = new Date().toISOString().slice(0, 10);
  const todayEntries = recent.filter(
    (e) => e.timestamp.slice(0, 10) === today
  );
  const avgMoodToday =
    todayEntries.length > 0
      ? Math.round(
          todayEntries.reduce((s, e) => s + e.mood, 0) / todayEntries.length
        )
      : null;
  const avgEnergyToday =
    todayEntries.length > 0
      ? Math.round(
          (todayEntries.reduce((s, e) => s + e.energy, 0) /
            todayEntries.length) *
            10
        ) / 10
      : null;

  return (
    <div className="space-y-6">
      {/* Weekly reflection digest (mounted above existing content) */}
      <WeeklyReflectionCard />

      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">
          Your mood & energy at a glance
        </p>
      </div>

      {/* Today's summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <p className="text-xs text-gray-400 uppercase tracking-wider">
            Today's Mood
          </p>
          <p className="text-4xl mt-2">
            {avgMoodToday ? MOOD_EMOJIS[avgMoodToday] : "—"}
          </p>
          <p className="text-sm text-gray-500 mt-1">
            {avgMoodToday ? `${avgMoodToday}/5` : "No entries yet"}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <p className="text-xs text-gray-400 uppercase tracking-wider">
            Today's Energy
          </p>
          <p className="text-4xl mt-2 font-bold text-emerald-500">
            {avgEnergyToday ?? "—"}
          </p>
          <p className="text-sm text-gray-500 mt-1">
            {avgEnergyToday ? `out of 10` : "No entries yet"}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <p className="text-xs text-gray-400 uppercase tracking-wider">
            Entries Today
          </p>
          <p className="text-4xl mt-2 font-bold text-pulse-600">
            {todayEntries.length}
          </p>
          <p className="text-sm text-gray-500 mt-1">
            {todayEntries.length === 0 ? "Time to log!" : "Keep it up"}
          </p>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TimelineChart data={daily} title="Last 14 Days — Daily Averages" />
        <CalendarHeatmap data={heatmap} />
      </div>

      {/* Recent entries */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          Recent Entries
        </h2>
        {recent.length === 0 ? (
          <p className="text-gray-400 text-sm">
            No entries yet. Start by logging your first mood!
          </p>
        ) : (
          <div className="space-y-3">
            {recent.map((entry) => (
              <EntryCard key={entry.id} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
