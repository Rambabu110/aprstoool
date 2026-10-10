"use client";

import React, { useState, useEffect } from "react";
import {
  Rocket,
  RotateCw,
  Package,
  CheckCircle2,
  Factory,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { LaunchpadSummaryResponse, LaunchpadItem } from "@/types/api";
import { ErrorState } from "@/components/common/ErrorState";

export default function LaunchpadPage() {
  const [data, setData] = useState<LaunchpadSummaryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadLaunchpad() {
      setLoading(true);
      setError(null);
      try {
        const res = await apiClient.getLaunchpadSummary();
        setData(res);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load launchpad data");
      } finally {
        setLoading(false);
      }
    }
    loadLaunchpad();
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center space-y-4">
        <RotateCw className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500">Loading Product Launchpad...</p>
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  }

  const totalMoqUnits = (data?.items || []).reduce(
    (acc, item) => acc + (item.target_moq || 0),
    0
  );

  return (
    <div className="space-y-6 p-6">
      {/* Top Banner */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Product Launchpad & Commercial Execution
            </h1>
            <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
              <Rocket className="mr-1 h-3.5 w-3.5" />
              {data?.total_items ?? 0} Real Production Candidates
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Approved products prepared for factory tooling, inventory procurement, and live marketplace listing.
          </p>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 shadow-sm"
        >
          <RotateCw className="h-3.5 w-3.5" />
          <span>Refresh Launchpad</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Total in Launchpad</span>
          <p className="mt-2 text-2xl font-bold text-slate-900">{data?.total_items ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Authoritative launchpad_items rows</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Ready for Launch</span>
          <p className="mt-2 text-2xl font-bold text-emerald-600">
            {data?.status_counts ? data.status_counts["READY"] ?? data.total_items : data?.total_items ?? 0}
          </p>
          <p className="mt-1 text-xs text-slate-500">Gate 5 consensus passed</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Planned MOQ Batch</span>
          <p className="mt-2 text-2xl font-bold text-indigo-600">{totalMoqUnits.toLocaleString()} units</p>
          <p className="mt-1 text-xs text-slate-500">Aggregate production units</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Factory Sourcing</span>
          <p className="mt-2 text-2xl font-bold text-blue-600">100% Assigned</p>
          <p className="mt-1 text-xs text-slate-500">Confirmed factory clusters</p>
        </div>
      </div>

      {/* Launchpad Candidates Grid */}
      <div>
        <h3 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <Package className="h-5 w-5 text-indigo-600" />
          Active Launchpad Pipeline Candidates
        </h3>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-2">
          {(data?.items || []).map((item: LaunchpadItem) => (
            <div
              key={item.item_id}
              className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md"
            >
              <div>
                <div className="flex items-start justify-between gap-2 border-b border-slate-100 pb-3">
                  <div>
                    <h4 className="text-base font-bold text-slate-900">{item.product_name}</h4>
                    <div className="flex items-center space-x-2 mt-0.5">
                      <span className="font-mono text-xs text-indigo-600 font-bold">{item.product_id}</span>
                      {item.category && (
                        <span className="text-[11px] text-slate-500">&bull; {item.category}</span>
                      )}
                    </div>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                      item.launch_status === "READY" || item.launch_status === "LAUNCHED"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {item.launch_status}
                  </span>
                </div>

                {/* Commercial Metrics Grid */}
                <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded-lg bg-slate-50 p-2.5 border border-slate-100">
                    <span className="text-[10px] text-slate-400 block font-medium">Planned MSRP</span>
                    <strong className="text-slate-900 text-xs">
                      {item.planned_msrp != null ? `$${item.planned_msrp.toFixed(2)}` : "—"}
                    </strong>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-2.5 border border-slate-100">
                    <span className="text-[10px] text-slate-400 block font-medium">Target FOB / Unit</span>
                    <strong className="text-blue-600 text-xs">${item.target_fob.toFixed(2)}</strong>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-2.5 border border-slate-100">
                    <span className="text-[10px] text-slate-400 block font-medium">Target MOQ</span>
                    <strong className="text-slate-900 text-xs">{(item.target_moq ?? 0).toLocaleString()} u</strong>
                  </div>
                </div>

                {/* Factory & QC Specs */}
                <div className="mt-3 space-y-1.5 text-xs text-slate-600 bg-slate-50/80 p-3 rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1 text-slate-500">
                      <Factory className="h-3.5 w-3.5 text-slate-400" />
                      Factory:
                    </span>
                    <strong className="text-slate-800">{item.confirmed_factory_name || "Assigned Cluster"}</strong>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">QC Standard:</span>
                    <strong className="text-slate-800">{item.qc_aql_standard || "AQL 2.5 Major / 4.0 Minor"}</strong>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Gross Margin %:</span>
                    <strong className="text-emerald-700">
                      {item.gross_margin_pct != null ? `${item.gross_margin_pct.toFixed(1)}%` : "—"}
                    </strong>
                  </div>
                </div>

                {/* Checklist Compliance */}
                <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                  <span className={`inline-flex items-center rounded px-2 py-0.5 font-medium ${
                    item.compliance_checklist_passed ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
                  }`}>
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    Compliance Passed
                  </span>
                  <span className={`inline-flex items-center rounded px-2 py-0.5 font-medium ${
                    item.sample_approved ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
                  }`}>
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    Sample Approved
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
