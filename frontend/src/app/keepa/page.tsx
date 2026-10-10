"use client";

import React, { useState, useEffect } from "react";
import {
  RotateCw,
  CheckCircle2,
  Activity,
  Database,
  Info,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { KeepaTelemetryStatus } from "@/types/api";
import { ErrorState } from "@/components/common/ErrorState";

export default function KeepaPage() {
  const [data, setData] = useState<KeepaTelemetryStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadKeepa() {
      setLoading(true);
      setError(null);
      try {
        const res = await apiClient.getKeepaTelemetry();
        setData(res);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load Keepa telemetry");
      } finally {
        setLoading(false);
      }
    }
    loadKeepa();
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center space-y-4">
        <RotateCw className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500">Connecting to Keepa Telemetry Service...</p>
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  }

  return (
    <div className="space-y-6 p-6">
      {/* Top Banner */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Keepa & BSR Historical Telemetry
            </h1>
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                data?.configured
                  ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20"
                  : "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20"
              }`}
            >
              <Activity className="mr-1 h-3.5 w-3.5" />
              {data?.configured ? "Live API Connected" : "Stored Telemetry Active"}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Historical price stability, BSR sales rank, and buy box volatility analysis across product catalog.
          </p>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 shadow-sm"
        >
          <RotateCw className="h-3.5 w-3.5" />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {/* Integration Status Callout */}
      <div
        className={`rounded-xl border p-5 shadow-sm ${
          data?.configured
            ? "border-emerald-200 bg-emerald-50/60 text-emerald-900"
            : "border-slate-200 bg-white text-slate-800"
        }`}
      >
        <div className="flex items-start space-x-3">
          {data?.configured ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-600 mt-0.5" />
          ) : (
            <Info className="h-5 w-5 text-slate-500 mt-0.5" />
          )}
          <div>
            <h3 className="text-sm font-bold">
              {data?.configured ? "Keepa API In Sync" : "Keepa Live API Credentials Status"}
            </h3>
            <p className="mt-1 text-xs text-slate-600 leading-relaxed">
              {data?.status_message ||
                "Keepa API credentials not found in environment. Catalog utilizes historical price stability telemetry cached in SQLite."}
            </p>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Live API Key</span>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {data?.api_key_present ? "CONFIGURED" : "NOT SET"}
          </p>
          <p className="mt-1 text-xs text-slate-500">KEEPA_API_KEY env check</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Products with Telemetry</span>
          <p className="mt-2 text-2xl font-bold text-indigo-600">
            {data?.total_products_with_keepa_data ?? 0}
          </p>
          <p className="mt-1 text-xs text-slate-500">Stored in master_products</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Catalog Price Stability</span>
          <p className="mt-2 text-2xl font-bold text-emerald-600">
            {data?.average_price_stability ? `${data.average_price_stability.toFixed(1)}%` : "N/A"}
          </p>
          <p className="mt-1 text-xs text-slate-500">Average 90-day consistency</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Tokens Remaining</span>
          <p className="mt-2 text-2xl font-bold text-slate-700">
            {data?.tokens_left != null ? data.tokens_left : "—"}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {data?.configured ? "Live token bucket" : "Offline telemetry"}
          </p>
        </div>
      </div>

      {/* Historical Telemetry Architecture Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
          <Database className="h-5 w-5 text-indigo-600" />
          Keepa Telemetry Usage in Autonomous Pipeline
        </h3>
        <p className="text-xs text-slate-600 leading-relaxed">
          In APRS V6 Pro, Keepa telemetry feeds directly into Gate 1 (Demand Validation) and Gate 2 (Margin Volatility).
          When live API tokens are offline, the engine evaluates historical telemetry fields persisted in SQLite.
        </p>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 pt-2 text-xs">
          <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
            <span className="text-slate-500 font-medium">Metric 1: 90-Day Price Stability</span>
            <p className="mt-1 text-sm font-bold text-slate-900">keepa_price_stability &ge; 90.0%</p>
            <p className="mt-1 text-[11px] text-slate-500">
              Flags aggressive price wars or margin compression among incumbent sellers.
            </p>
          </div>

          <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
            <span className="text-slate-500 font-medium">Metric 2: Estimated Daily Velocity</span>
            <p className="mt-1 text-sm font-bold text-slate-900">BSR Rank &rarr; Units/Day Model</p>
            <p className="mt-1 text-[11px] text-slate-500">
              Converts Best Sellers Rank into verified volume velocity estimates.
            </p>
          </div>

          <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
            <span className="text-slate-500 font-medium">Metric 3: Domain & Geography</span>
            <p className="mt-1 text-sm font-bold text-slate-900">Domain ID: {data?.domain_id || 1} (Amazon.com)</p>
            <p className="mt-1 text-[11px] text-slate-500">
              Configured for USA and India marketplace telemetry ingestion.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
