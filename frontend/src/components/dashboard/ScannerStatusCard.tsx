import React from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ScannerStatus } from "@/types/api";

interface ScannerStatusCardProps {
  scanner: ScannerStatus;
}

export const ScannerStatusCard: React.FC<ScannerStatusCardProps> = ({ scanner }) => {
  const isRunning = scanner.status.toLowerCase() === "running";
  const steps = ["1 Collect", "2 Score", "3 AI review", "4 Update lists"];

  return (
    <Card className="flex flex-col justify-between space-y-5">
      {/* Title & Status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <h2 className="text-base font-semibold text-slate-900">Scanner status</h2>
          <Badge
            variant={isRunning ? "success" : "default"}
            className="text-xs"
          >
            {scanner.status}
          </Badge>
        </div>
      </div>

      <p className="text-xs text-slate-500 -mt-3">
        Collecting and scoring products from connected sources ({scanner.current_niche || "Standby"})
      </p>

      {/* Progress Bar & Next Run */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-indigo-700">
            {scanner.progress_pct}% complete
          </span>
          <span className="text-slate-400">
            {scanner.next_run_in_min ? `Next run in ${scanner.next_run_in_min} min` : "Scheduled daemon cycle"}
          </span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
          <div
            className="bg-indigo-600 h-2.5 rounded-full transition-all duration-500 ease-out shadow-xs shadow-indigo-600/30"
            style={{ width: `${Math.min(100, Math.max(5, scanner.progress_pct))}%` }}
          />
        </div>
      </div>

      {/* Workflow Step Pills */}
      <div className="flex items-center gap-1.5 flex-wrap text-xs">
        {steps.map((step, idx) => {
          const isCurrent = idx === 1; // 2 Score
          const isCompleted = idx === 0; // 1 Collect
          return (
            <React.Fragment key={step}>
              <span
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                  isCurrent
                    ? "bg-indigo-600 text-white font-semibold shadow-xs"
                    : isCompleted
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-slate-100 text-slate-600 border border-slate-200"
                }`}
              >
                {step}
              </span>
              {idx < steps.length - 1 && (
                <span className="text-slate-300 font-bold">&gt;</span>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* 4 Metric Counters Row */}
      <div className="grid grid-cols-4 gap-2 pt-3 border-t border-slate-100 text-center">
        <div>
          <div className="text-[11px] text-slate-400 font-medium">Scanned</div>
          <div className="text-lg font-bold text-slate-900">
            {scanner.scanned_count.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-medium">New found</div>
          <div className="text-lg font-bold text-emerald-600">
            {scanner.new_found.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-medium">Gates run</div>
          <div className="text-lg font-bold text-slate-900">
            {scanner.gates_run.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-medium">Errors</div>
          <div className="text-lg font-bold text-rose-600">
            {scanner.errors.toLocaleString()}
          </div>
        </div>
      </div>
    </Card>
  );
};
