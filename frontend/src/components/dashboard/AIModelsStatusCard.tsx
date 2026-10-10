import React from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { AIModelStatusItem } from "@/types/api";

interface AIModelsStatusCardProps {
  models: AIModelStatusItem[];
}

export const AIModelsStatusCard: React.FC<AIModelsStatusCardProps> = ({ models }) => {
  const attentionCount = models.filter(
    (m) =>
      m.status.toLowerCase().includes("not configured") ||
      m.status.toLowerCase().includes("token") ||
      m.status.toLowerCase().includes("error") ||
      m.status.toLowerCase().includes("expired")
  ).length;

  return (
    <Card id="ai-models-section" className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2.5">
          <h2 className="text-base font-semibold text-slate-900">
            AI models &amp; tools status
          </h2>
          {attentionCount > 0 ? (
            <Badge variant="danger" className="text-xs">
              {attentionCount} need attention
            </Badge>
          ) : (
            <Badge variant="success" className="text-xs">
              All systems active
            </Badge>
          )}
        </div>
        <span className="text-xs text-slate-400">
          Checked recently
        </span>
      </div>

      {/* Grid of Models */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {models.map((model) => {
          const isError =
            model.status.toLowerCase().includes("not configured") ||
            model.status.toLowerCase().includes("token") ||
            model.status.toLowerCase().includes("error") ||
            model.status.toLowerCase().includes("expired");

          const isRunning = model.status.toLowerCase() === "running";

          return (
            <div
              key={model.name}
              className={`p-3.5 rounded-xl border transition-all ${
                isError
                  ? "border-rose-200/90 bg-rose-50/20"
                  : "border-slate-200/70 bg-white"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2 truncate pr-2">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      isError
                        ? "bg-rose-500"
                        : isRunning
                        ? "bg-emerald-500"
                        : "bg-amber-400"
                    }`}
                  />
                  <span className="text-sm font-semibold text-slate-900 truncate">
                    {model.name}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 font-medium flex-shrink-0">
                  {model.provider || "AI"}
                </span>
              </div>

              <div className="text-[11px] text-slate-400 mb-2 truncate">
                {model.role || "Reasoning & Inference"}
              </div>

              <div className="mb-2">
                <Badge
                  variant={isError ? "danger" : isRunning ? "success" : "warning"}
                  className="text-[11px]"
                >
                  {model.status}
                </Badge>
              </div>

              <div className="text-xs text-slate-500 min-h-[32px] line-clamp-2">
                {model.affects || "Operational with zero active bottlenecks"}
              </div>

              {isError && (
                <div className="mt-3 pt-2 border-t border-rose-100">
                  <button
                    onClick={() => {
                      alert(`Fix action for ${model.name}: Configure API key in .env or manage credentials.`);
                    }}
                    className="w-full py-1 px-2.5 text-xs font-medium text-rose-700 bg-white border border-rose-200 rounded-md hover:bg-rose-50 transition-colors cursor-pointer text-center"
                  >
                    Fix now
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
};
