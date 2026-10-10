"use client";

import React, { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { HealthResponse } from "@/types/api";

interface HeaderProps {
  bannerMessage?: string | null;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  bannerMessage,
  onRefresh,
  isRefreshing = false,
}) => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [dismissBanner, setDismissBanner] = useState(false);

  useEffect(() => {
    let mounted = true;
    api
      .getHealth()
      .then((data) => {
        if (mounted) {
          setHealth(data);
          setHealthError(null);
        }
      })
      .catch((err) => {
        if (mounted) {
          setHealth(null);
          setHealthError(err.message || "Failed to reach backend");
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="w-full flex flex-col space-y-4 mb-6">
      {/* Top AI Status Banner (Matching Figma Dashboard.png) */}
      {bannerMessage && !dismissBanner && (
        <div className="w-full bg-rose-50 border border-rose-200 text-rose-800 rounded-xl p-4 flex items-start justify-between gap-4 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-rose-100 flex items-center justify-center flex-shrink-0 text-rose-600 mt-0.5">
              <AlertCircle className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-rose-900 leading-tight">
                {bannerMessage}
              </p>
              <p className="text-xs text-rose-700 mt-0.5">
                AI verification is paused. New products will show &quot;Gate not run&quot; until the token resets or a key is added.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={() => {
                const el = document.getElementById("ai-models-section");
                if (el) el.scrollIntoView({ behavior: "smooth" });
              }}
              className="px-3.5 py-1.5 text-xs font-medium text-rose-700 bg-white border border-rose-300 rounded-lg hover:bg-rose-50 transition-colors cursor-pointer shadow-xs"
            >
              View AI status
            </button>
            <button
              onClick={() => setDismissBanner(true)}
              className="p-1.5 text-rose-400 hover:text-rose-600 rounded-lg hover:bg-rose-100/50 cursor-pointer"
              title="Dismiss banner"
            >
              <span className="sr-only">Dismiss</span>
              &times;
            </button>
          </div>
        </div>
      )}

      {/* Connectivity & Actions Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {health ? (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              <span>FastAPI Connected ({health.database_mode?.toUpperCase() || "WAL"})</span>
            </div>
          ) : healthError ? (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
              <XCircle className="w-3.5 h-3.5 text-rose-500" />
              <span>API Offline (localhost:8000)</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
              <span className="w-2 h-2 rounded-full bg-slate-400 animate-ping" />
              <span>Checking API...</span>
            </div>
          )}
          <span className="text-xs text-slate-400 hidden sm:inline">
            Direct Access • Free Product Research
          </span>
        </div>

        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 hover:text-slate-900 transition-colors cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-indigo-600" : ""}`} />
            <span>{isRefreshing ? "Updating..." : "Refresh"}</span>
          </button>
        )}
      </div>
    </div>
  );
};
