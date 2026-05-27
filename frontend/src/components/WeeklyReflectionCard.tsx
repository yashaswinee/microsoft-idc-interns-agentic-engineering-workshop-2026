import { useEffect, useState } from "react";

import { getWeeklyReflection } from "../lib/api";
import type { WeeklyReflection } from "../lib/types";

const TREND_WORDS: Record<string, string> = {
  improving: "Trending up",
  declining: "Trending down",
  flat: "Holding steady",
  insufficient_data: "Not enough data yet",
};

export default function WeeklyReflectionCard() {
  const [data, setData] = useState<WeeklyReflection | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getWeeklyReflection()
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 text-sm text-gray-400">
        Loading weekly reflection…
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const handleCopy = async () => {
    if (!data.share_text) return;
    try {
      await navigator.clipboard.writeText(data.share_text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard may be unavailable (older browsers / insecure contexts);
      // we silently swallow so the UI stays calm.
    }
  };

  const trendWord = TREND_WORDS[data.trend.label] ?? data.trend.label;
  const isTough = data.mode === "tough";
  const cardClassName = isTough
    ? "bg-amber-50/40 rounded-xl border border-amber-100 p-5 space-y-4"
    : "bg-white rounded-xl border border-gray-200 p-5 space-y-4";

  return (
    <section
      aria-label="Weekly reflection"
      data-mode={data.mode}
      className={cardClassName}
    >
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">
            Weekly Reflection
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            {data.window.start} → {data.window.end}
          </p>
        </div>
        {data.share_text && (
          <button
            type="button"
            onClick={handleCopy}
            className="text-xs px-3 py-1.5 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer"
          >
            {copied ? "Copied!" : "Copy summary"}
          </button>
        )}
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
          <p className="text-sm font-semibold text-gray-700 mt-2">
            {trendWord}
          </p>
        </div>
      </div>

      {(data.best_day || data.worst_day) && (
        <div className="grid grid-cols-2 gap-3 text-sm">
          {data.best_day && (
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider">
                Best day
              </p>
              <p className="text-gray-700 mt-0.5">
                {data.best_day.date} · {data.best_day.avg_mood}/5
              </p>
            </div>
          )}
          {data.worst_day && (
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider">
                Toughest day
              </p>
              <p className="text-gray-700 mt-0.5">
                {data.worst_day.date} · {data.worst_day.avg_mood}/5
              </p>
            </div>
          )}
        </div>
      )}

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
        <p className="text-sm text-gray-700 leading-relaxed">
          {data.narrative}
        </p>
      )}

      {data.suggestion && (
        <p className="text-sm text-pulse-700 leading-relaxed">
          {data.suggestion}
        </p>
      )}

      {data.reflection_prompt && (
        <div className="border-t border-gray-100 pt-3">
          <p className="text-[10px] text-gray-400 uppercase tracking-wider">
            Reflection prompt
          </p>
          <p className="text-sm text-gray-700 italic mt-1">
            {data.reflection_prompt}
          </p>
        </div>
      )}
    </section>
  );
}
