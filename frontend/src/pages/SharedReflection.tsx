import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getSharedReflection } from "../lib/api";
import type { WeeklyReflection } from "../lib/types";

const TREND_WORDS: Record<string, string> = {
  improving: "Trending up",
  declining: "Trending down",
  flat: "Holding steady",
  insufficient_data: "Not enough data yet",
};

export default function SharedReflection() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<WeeklyReflection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    getSharedReflection(id)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch(() => {
        if (!cancelled) setError("This shared reflection could not be found.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="text-sm text-gray-400 p-6">Loading shared reflection…</div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 text-sm text-gray-600">
        {error ?? "Not found."}
      </div>
    );
  }

  const trendWord = TREND_WORDS[data.trend.label] ?? data.trend.label;

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6 space-y-4 max-w-2xl">
      <header>
        <p className="text-xs text-gray-400 uppercase tracking-wider">
          Shared weekly reflection
        </p>
        <h1 className="text-xl font-semibold text-gray-800 mt-1">
          {data.window.start} → {data.window.end}
        </h1>
      </header>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-[10px] text-gray-400 uppercase tracking-wider">
            Avg mood
          </p>
          <p className="text-xl font-bold text-gray-800 mt-1">
            {data.avg_mood ?? "—"}
          </p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-[10px] text-gray-400 uppercase tracking-wider">
            Avg energy
          </p>
          <p className="text-xl font-bold text-emerald-600 mt-1">
            {data.avg_energy ?? "—"}
          </p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-[10px] text-gray-400 uppercase tracking-wider">
            Trend
          </p>
          <p className="text-sm font-semibold text-gray-700 mt-2">{trendWord}</p>
        </div>
      </div>

      {data.top_tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.top_tags.map((t) => (
            <span
              key={t.tag}
              className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full"
            >
              {t.tag}
            </span>
          ))}
        </div>
      )}

      {data.narrative && (
        <p className="text-sm text-gray-700 leading-relaxed">{data.narrative}</p>
      )}

      {data.share_text && (
        <pre className="bg-gray-50 border border-gray-100 rounded-lg p-3 text-xs text-gray-700 whitespace-pre-wrap font-sans">
          {data.share_text}
        </pre>
      )}
    </section>
  );
}
