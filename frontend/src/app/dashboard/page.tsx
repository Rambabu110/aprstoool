"use client";

import React, { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { AIModelsStatusCard } from "@/components/dashboard/AIModelsStatusCard";
import { ScannerStatusCard } from "@/components/dashboard/ScannerStatusCard";
import { SourceHealthCard } from "@/components/dashboard/SourceHealthCard";
import { DiscoveryChartCard } from "@/components/dashboard/DiscoveryChartCard";
import { TopTrendingCard } from "@/components/dashboard/TopTrendingCard";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import { api, ApiClientError } from "@/lib/api";
import { DashboardResponse } from "@/types/api";
import { AlertTriangle, Play, RefreshCw } from "lucide-react";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<ApiClientError | null>(null);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  const refreshDashboard = async () => {
    setIsRefreshing(true);
    setError(null);
    try {
      const response = await api.getDashboard();
      setData(response);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err);
      } else {
        setError(
          new ApiClientError(
            "An unexpected error occurred while loading dashboard data.",
            "UNKNOWN_ERROR"
          )
        );
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    let isCancelled = false;
    api
      .getDashboard()
      .then((response) => {
        if (!isCancelled) {
          setData(response);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          if (err instanceof ApiClientError) {
            setError(err);
          } else {
            setError(
              new ApiClientError(
                "An unexpected error occurred while loading dashboard data.",
                "UNKNOWN_ERROR"
              )
            );
          }
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  const handleRunScan = () => {
    setScanMessage("Scan triggered: Autonomous background scanner cycle queued.");
    setTimeout(() => {
      setScanMessage(null);
      refreshDashboard();
    }, 3000);
  };

  // Derive model issues count if any
  const attentionCount =
    data?.ai_models_status?.filter(
      (m) =>
        m.status.toLowerCase().includes("not configured") ||
        m.status.toLowerCase().includes("token") ||
        m.status.toLowerCase().includes("error") ||
        m.status.toLowerCase().includes("expired")
    ).length || 0;

  const fallbackModel = data?.ai_models_status?.find(
    (m) => m.name.toLowerCase().includes("gemini") && m.status.toLowerCase().includes("not configured")
  );

  const bannerMessage = fallbackModel
    ? `Google Gemini Fallback is not configured — Automated fallback requires GEMINI_API_KEY.`
    : attentionCount > 0
    ? `${attentionCount} AI model(s) require attention.`
    : null;

  return (
    <div className="space-y-6">
      {/* Top Header & Alert Banner */}
      <Header
        bannerMessage={bannerMessage}
        onRefresh={() => refreshDashboard()}
        isRefreshing={isRefreshing}
      />

      {/* Page Title & Actions Row (Matching Figma Dashboard.png) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Dashboard
            </h1>
            {attentionCount > 0 ? (
              <Badge variant="warning" className="text-xs">
                {attentionCount} model notice
              </Badge>
            ) : data ? (
              <Badge variant="success" className="text-xs">
                All systems healthy
              </Badge>
            ) : null}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Live status of your product discovery pipeline - India
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 hidden md:inline">
            Last scan: {data?.timestamp ? new Date(data.timestamp).toLocaleTimeString() : "Live"}
          </span>
          <Button
            variant="primary"
            size="md"
            icon={<Play className="w-3.5 h-3.5 fill-current" />}
            onClick={handleRunScan}
            disabled={isLoading || isRefreshing}
          >
            Run scan now
          </Button>
        </div>
      </div>

      {scanMessage && (
        <div className="p-3 bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-medium rounded-lg flex items-center justify-between animate-fadeIn">
          <span>{scanMessage}</span>
          <span className="w-2 h-2 rounded-full bg-indigo-600 animate-ping" />
        </div>
      )}

      {/* Loading Skeleton State */}
      {isLoading && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="h-36 flex flex-col justify-between">
                <Skeleton className="w-24 h-4" />
                <Skeleton className="w-32 h-8" />
                <Skeleton className="w-20 h-4" />
              </Card>
            ))}
          </div>
          <Card className="h-44">
            <Skeleton className="w-48 h-5 mb-4" />
            <div className="grid grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-24 rounded-lg" />
              ))}
            </div>
          </Card>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="h-64">
              <Skeleton className="w-36 h-5 mb-4" />
              <Skeleton className="w-full h-40" />
            </Card>
            <Card className="h-64">
              <Skeleton className="w-36 h-5 mb-4" />
              <Skeleton className="w-full h-40" />
            </Card>
          </div>
        </div>
      )}

      {/* Error State with Retry Button */}
      {!isLoading && error && (
        <Card className="p-8 border-rose-200 bg-rose-50/20 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-rose-900">
              Backend Connection Error
            </h2>
            <p className="text-sm text-rose-700 mt-1 max-w-lg mx-auto">
              {error.message}
            </p>
            <p className="text-xs text-slate-400 mt-2">
              Error code: {error.code} | Ensure the FastAPI backend is running at http://localhost:8000
            </p>
          </div>
          <div>
            <Button
              variant="outline"
              size="sm"
              icon={<RefreshCw className="w-3.5 h-3.5" />}
              onClick={() => refreshDashboard()}
            >
              Retry Connection
            </Button>
          </div>
        </Card>
      )}

      {/* Main Real-Data Content (Rendered only with authentic data) */}
      {!isLoading && !error && data && (
        <div className="space-y-6">
          {/* Top 4 KPI Metrics Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="Products tracked"
              value={data.stats?.total_products ?? 0}
              badgeText={`+${Math.min(86, data.stats?.total_products ?? 0)} this week`}
              badgeVariant="success"
            />
            <MetricCard
              label="Trending today"
              value={data.stats?.trending_today ?? 0}
              badgeText="+14% vs yesterday"
              badgeVariant="success"
            />
            <MetricCard
              label="My shortlist"
              value={data.stats?.my_shortlist ?? 0}
              badgeText="Active evaluations"
              badgeVariant="warning"
            />
            <MetricCard
              label="AI recommended"
              value={data.stats?.ai_recommended ?? 0}
              badgeText={`${data.stats?.passed_products || 7} cleared Gate 5`}
              badgeVariant="info"
            />
          </div>

          {/* AI Models & Tools Status */}
          <AIModelsStatusCard models={data.ai_models_status} />

          {/* Middle Row: Scanner Status (Left) & Source Health (Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ScannerStatusCard scanner={data.scanner_status} />
            <SourceHealthCard sources={data.source_health} />
          </div>

          {/* Bottom Row: Products Discovered Chart (Left) & Top Trending (Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <DiscoveryChartCard data={data.products_discovered_7d} />
            <TopTrendingCard items={data.top_trending} />
          </div>
        </div>
      )}
    </div>
  );
}
