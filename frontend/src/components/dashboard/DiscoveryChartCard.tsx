import React from "react";
import { Card } from "@/components/ui/Card";
import { DiscoveryDayMetric } from "@/types/api";

interface DiscoveryChartCardProps {
  data: DiscoveryDayMetric[];
}

export const DiscoveryChartCard: React.FC<DiscoveryChartCardProps> = ({ data }) => {
  const maxCount = Math.max(...data.map((d) => d.count), 1);

  const formatDayLabel = (dateStr: string) => {
    try {
      const parts = dateStr.split("-");
      if (parts.length === 3) {
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const monthIdx = parseInt(parts[1], 10) - 1;
        return `${monthNames[monthIdx] || parts[1]} ${parts[2]}`;
      }
      return dateStr;
    } catch {
      return dateStr;
    }
  };

  return (
    <Card className="flex flex-col justify-between space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <h2 className="text-base font-semibold text-slate-900">
          Products discovered - last 7 days
        </h2>
        <span className="text-xs text-slate-400">Daily velocity</span>
      </div>

      {/* Bar Chart Area */}
      <div className="h-44 pt-4 flex items-end justify-between gap-3 px-2">
        {data.map((day, idx) => {
          const heightPercent = Math.max(12, Math.round((day.count / maxCount) * 100));
          const isLast = idx === data.length - 1;

          return (
            <div
              key={day.date}
              className="flex-1 flex flex-col items-center gap-2 h-full justify-end group cursor-default"
            >
              {/* Tooltip / Count on hover */}
              <div className="opacity-0 group-hover:opacity-100 transition-opacity text-[11px] font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded shadow-xs">
                {day.count}
              </div>

              {/* Bar */}
              <div className="w-full max-w-[48px] bg-slate-100 rounded-t-lg overflow-hidden flex items-end h-full">
                <div
                  style={{ height: `${heightPercent}%` }}
                  className={`w-full rounded-t-lg transition-all duration-500 ease-out ${
                    isLast
                      ? "bg-indigo-600 shadow-sm shadow-indigo-600/30"
                      : "bg-indigo-200 hover:bg-indigo-300"
                  }`}
                />
              </div>

              {/* Day Label */}
              <span
                className={`text-[11px] font-medium tracking-tight whitespace-nowrap ${
                  isLast ? "text-indigo-600 font-bold" : "text-slate-400"
                }`}
              >
                {formatDayLabel(day.date)}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
