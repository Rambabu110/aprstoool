import React from "react";
import { Card } from "@/components/ui/Card";
import { Badge, BadgeVariant } from "@/components/ui/Badge";
import { SourceHealthItem } from "@/types/api";

interface SourceHealthCardProps {
  sources: SourceHealthItem[];
}

export const SourceHealthCard: React.FC<SourceHealthCardProps> = ({ sources }) => {
  return (
    <Card className="flex flex-col justify-between space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <h2 className="text-base font-semibold text-slate-900">Source health</h2>
        <span className="text-xs text-slate-400">{sources.length} sources registered</span>
      </div>

      {/* Sources List */}
      <div className="space-y-3 divide-y divide-slate-100 max-h-[280px] overflow-y-auto pr-1">
        {sources.map((source) => {
          let badgeVariant: BadgeVariant = "default";
          let dotColor = "bg-slate-400";
          const statusLower = source.status.toLowerCase();

          if (statusLower === "ok" || statusLower === "online") {
            badgeVariant = "success";
            dotColor = "bg-emerald-500";
          } else if (statusLower === "delayed") {
            badgeVariant = "warning";
            dotColor = "bg-amber-500";
          } else if (statusLower === "error" || statusLower === "degraded") {
            badgeVariant = "danger";
            dotColor = "bg-rose-500";
          }

          return (
            <div
              key={source.source_name}
              className="pt-2.5 first:pt-0 flex items-center justify-between"
            >
              <div className="flex items-center gap-2.5 truncate pr-2">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
                <span className="text-sm font-medium text-slate-800 truncate">
                  {source.source_name}
                </span>
              </div>

              <div className="flex items-center gap-3 flex-shrink-0">
                <span className="text-xs text-slate-400">
                  {source.success_rate_pct != null
                    ? `${source.success_rate_pct}% success`
                    : source.last_checked || "Live"}
                </span>
                <Badge variant={badgeVariant} className="text-[11px] font-semibold min-w-[38px] justify-center">
                  {source.status}
                </Badge>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
