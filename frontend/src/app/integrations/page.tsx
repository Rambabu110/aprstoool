"use client";

import React, { useState, useEffect } from "react";
import {
  Network,
  RotateCw,
  Store,
  Activity,
  Bot,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { IntegrationOverviewResponse } from "@/types/api";
import { ErrorState } from "@/components/common/ErrorState";

export default function IntegrationsPage() {
  const [data, setData] = useState<IntegrationOverviewResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"sources" | "marketplaces" | "llm">("sources");
  
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadIntegrations() {
      setLoading(true);
      setError(null);
      try {
        const res = await apiClient.getIntegrationsOverview();
        setData(res);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load integrations");
      } finally {
        setLoading(false);
      }
    }
    loadIntegrations();
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center space-y-4">
        <RotateCw className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500">Loading Integration Management Center...</p>
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
              Integration Management Center
            </h1>
            <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
              <Network className="mr-1 h-3.5 w-3.5" />
              {data?.healthy_sources ?? 0} / {data?.total_sources ?? 0} Operational
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Real-time health status, telemetry probes, and configuration for research data sources and marketplace connectors.
          </p>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 shadow-sm"
        >
          <RotateCw className="h-3.5 w-3.5" />
          <span>Refresh Probes</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Tracked Sources</span>
          <p className="mt-2 text-2xl font-bold text-slate-900">{data?.total_sources ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Recorded in source_health</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Healthy Probes</span>
          <p className="mt-2 text-2xl font-bold text-emerald-600">{data?.healthy_sources ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Zero circuit-breaker trips</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Target Marketplaces</span>
          <p className="mt-2 text-2xl font-bold text-indigo-600">{data?.marketplaces.length ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">In marketplace_config</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">LLM Provider Status</span>
          <p className="mt-2 text-lg font-bold text-blue-600">
            {data?.llm_cluster.provider_configured ? "ONLINE" : "HEURISTIC"}
          </p>
          <p className="mt-1 text-xs text-slate-500">{data?.llm_cluster.provider_type}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab("sources")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "sources"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Activity className="h-4 w-4" />
            <span>Data Sources ({data?.sources.length ?? 0})</span>
          </button>
          <button
            onClick={() => setActiveTab("marketplaces")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "marketplaces"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Store className="h-4 w-4" />
            <span>Marketplace Policies ({data?.marketplaces.length ?? 0})</span>
          </button>
          <button
            onClick={() => setActiveTab("llm")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "llm"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Bot className="h-4 w-4" />
            <span>AI Cluster Config</span>
          </button>
        </nav>
      </div>

      {/* TAB 1: SOURCES */}
      {activeTab === "sources" && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3 font-semibold">Source Name</th>
                  <th className="px-6 py-3 font-semibold">Category</th>
                  <th className="px-6 py-3 font-semibold">Health Status</th>
                  <th className="px-6 py-3 font-semibold text-right">Latency</th>
                  <th className="px-6 py-3 font-semibold">Last Success</th>
                  <th className="px-6 py-3 font-semibold text-right">Failures</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {(data?.sources || []).map((s) => (
                  <tr key={s.source_name} className="hover:bg-slate-50">
                    <td className="px-6 py-4 font-bold text-slate-900">{s.source_name}</td>
                    <td className="px-6 py-4">
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                        {s.category}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                          s.status === "HEALTHY"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-amber-50 text-amber-700 border border-amber-200"
                        }`}
                      >
                        <span
                          className={`mr-1.5 h-1.5 w-1.5 rounded-full ${
                            s.status === "HEALTHY" ? "bg-emerald-500" : "bg-amber-500"
                          }`}
                        ></span>
                        {s.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-xs text-slate-700">
                      {s.latency_ms != null ? `${s.latency_ms.toFixed(0)} ms` : "—"}
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-500">{s.last_success || "Active"}</td>
                    <td className="px-6 py-4 text-right font-medium text-slate-900">
                      {s.consecutive_failures}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: MARKETPLACES */}
      {activeTab === "marketplaces" && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(data?.marketplaces || []).map((m) => (
            <div key={m.marketplace_id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div>
                  <h4 className="text-base font-bold text-slate-900">{m.name}</h4>
                  <span className="text-xs text-slate-400 font-mono">{m.marketplace_id}</span>
                </div>
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800">
                  {m.currency}
                </span>
              </div>

              <div className="mt-4 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Region:</span>
                  <strong className="text-slate-900">{m.region}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Minimum Margin Policy:</span>
                  <strong className="text-indigo-600">{m.min_margin_pct.toFixed(1)}%</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Maximum RTO / Return Cutoff:</span>
                  <strong className="text-rose-600">{m.max_return_rate_pct.toFixed(1)}%</strong>
                </div>
                <div className="flex justify-between border-t border-slate-100 pt-2">
                  <span className="text-slate-500">Active Routing:</span>
                  <strong className="text-emerald-700">ENABLED</strong>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 3: LLM CLUSTER */}
      {activeTab === "llm" && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
          <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <Bot className="h-5 w-5 text-indigo-600" />
            AI Intelligence Cluster Configuration
          </h3>
          <p className="text-xs text-slate-500">
            Governs model choice for adversarial debates, opportunity ranking, and supervisor oversight.
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 pt-2 text-xs">
            <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
              <span className="text-slate-500 font-medium">Default Research Model</span>
              <p className="mt-1 text-sm font-bold text-slate-900 font-mono">
                {data?.llm_cluster.default_model || "gemini-2.5-flash"}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">High-throughput reasoning model</p>
            </div>

            <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
              <span className="text-slate-500 font-medium">Supervisor & Arbiter Model</span>
              <p className="mt-1 text-sm font-bold text-slate-900 font-mono">
                {data?.llm_cluster.supervisor_model || "gemini-2.5-pro"}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">Adversarial arbiter and compliance watchdog</p>
            </div>

            <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
              <span className="text-slate-500 font-medium">Sampling Temperature</span>
              <p className="mt-1 text-sm font-bold text-slate-900 font-mono">
                {data?.llm_cluster.temperature ?? 0.2}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">Deterministic reasoning mode</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
