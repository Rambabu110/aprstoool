"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Bell,
} from "lucide-react";
import { api, apiClient, ApiClientError } from "@/lib/api";
import { OpportunityItem, OpportunityListResponse, AlertItem } from "@/types/api";
import { Pagination } from "@/components/common/Pagination";
import { ScoreBadge } from "@/components/common/ScoreBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ProductDossierModal } from "@/components/products/ProductDossierModal";
import { Button } from "@/components/ui/Button";

type TriStateFilter = "ALL" | "SURVIVES" | "KILLED" | "INSUFFICIENT_EVIDENCE";

export default function OpportunitiesPage() {
  // State
  const [data, setData] = useState<OpportunityListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [triStateFilter, setTriStateFilter] = useState<TriStateFilter>("ALL");
  const [selectedRegion, setSelectedRegion] = useState("all");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [currentPage, setCurrentPage] = useState(1);

  // Modal
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);

  // Alerts state
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [dismissingAlertId, setDismissingAlertId] = useState<number | null>(null);

  const pageSize = 25;

  const fetchOpportunities = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await api.getOpportunities({
        page: currentPage,
        pageSize,
        tri_state:
          triStateFilter === "ALL" ? undefined : triStateFilter,
        region: selectedRegion === "all" ? undefined : selectedRegion,
        category: selectedCategory === "all" ? undefined : selectedCategory,
      });
      setData(res);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError ? err.message : "Failed to load opportunities.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [currentPage, triStateFilter, selectedRegion, selectedCategory]);

  useEffect(() => {
    fetchOpportunities();
  }, [fetchOpportunities]);

  useEffect(() => {
    apiClient
      .getAlerts(10)
      .then((res) => {
        setAlerts(res.alerts || []);
      })
      .catch(() => {});
  }, []);

  const handleDismissAlert = async (alertId: number) => {
    setDismissingAlertId(alertId);
    try {
      await apiClient.dismissAlert(alertId);
      setAlerts((prev) => prev.filter((a) => a.alert_id !== alertId));
    } catch (err: unknown) {
      alert(`Could not dismiss alert: ${err instanceof Error ? err.message : "Error"}`);
    } finally {
      setDismissingAlertId(null);
    }
  };

  const formatCurrency = (val?: number | null) => {
    if (val === undefined || val === null) return "-";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  const renderTriStateBadge = (status: "SURVIVES" | "KILLED" | "INSUFFICIENT_EVIDENCE") => {
    switch (status) {
      case "SURVIVES":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" />
            SURVIVES
          </span>
        );
      case "KILLED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3.5 h-3.5" />
            KILLED
          </span>
        );
      case "INSUFFICIENT_EVIDENCE":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <HelpCircle className="w-3.5 h-3.5" />
            INSUFFICIENT EVIDENCE
          </span>
        );
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Opportunity Pipeline
            </h1>
            <span className="p-1 rounded-md bg-indigo-50 text-indigo-600">
              <ShieldAlert className="w-4 h-4" />
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Strict tri-state decision classification preserving SURVIVES, KILLED, and INSUFFICIENT_EVIDENCE
          </p>
        </div>

        {/* Counter cards */}
        {data && (
          <div className="flex items-center gap-2 text-xs">
            <span className="px-3 py-1 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 font-bold">
              Survives: {data.survives_count}
            </span>
            <span className="px-3 py-1 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 font-bold">
              Killed: {data.killed_count}
            </span>
            <span className="px-3 py-1 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 font-semibold">
              Pending: {data.insufficient_evidence_count}
            </span>
          </div>
        )}
      </div>

      {/* Opportunity Alert Center (Streamlit Parity) */}
      {alerts.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <div className="flex items-center gap-2">
              <Bell className="w-4 h-4 text-amber-500" />
              <h2 className="text-sm font-bold text-slate-900">
                Opportunity Alert Center ({alerts.length})
              </h2>
            </div>
            <span className="text-[11px] text-slate-400">
              Actionable margin alerts and kill switch triggers
            </span>
          </div>

          <div className="space-y-2.5">
            {alerts.map((al) => {
              const isHigh = al.severity === "HIGH" || al.severity === "CRITICAL";
              return (
                <div
                  key={al.alert_id}
                  className={`p-3.5 rounded-lg border text-xs space-y-1.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                    isHigh
                      ? "bg-rose-50/60 border-rose-200 text-rose-900"
                      : "bg-amber-50/50 border-amber-200 text-amber-900"
                  }`}
                >
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          isHigh ? "bg-rose-600 text-white" : "bg-amber-500 text-white"
                        }`}
                      >
                        {al.severity}
                      </span>
                      <strong className="text-slate-900 text-xs">{al.title}</strong>
                      <span className="text-slate-400 font-mono text-[10px]">{al.created_at}</span>
                    </div>
                    <p className="text-slate-700">
                      <strong>What Happened:</strong> {al.what_happened}
                    </p>
                    <p className="text-slate-600">
                      <strong>Why It Matters:</strong> {al.why_it_matters}
                    </p>
                    {al.recommended_action && (
                      <p className="text-emerald-700 font-medium">
                        <strong>Recommended:</strong> {al.recommended_action}
                      </p>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => handleDismissAlert(al.alert_id)}
                    disabled={dismissingAlertId === al.alert_id}
                    className="self-start sm:self-center px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors shrink-0 shadow-2xs disabled:opacity-50"
                  >
                    {dismissingAlertId === al.alert_id ? "Dismissing..." : "Acknowledge / Dismiss"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Container */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs overflow-hidden">
        {/* Tri-state Filter Pills */}
        <div className="p-6 pb-3 border-b border-slate-100 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setTriStateFilter("ALL");
                setCurrentPage(1);
              }}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                triStateFilter === "ALL"
                  ? "bg-slate-900 text-white shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              All Decisions ({data ? data.total : "..."})
            </button>

            <button
              type="button"
              onClick={() => {
                setTriStateFilter("SURVIVES");
                setCurrentPage(1);
              }}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                triStateFilter === "SURVIVES"
                  ? "bg-emerald-600 text-white shadow-xs"
                  : "bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100"
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              SURVIVES ({data ? data.survives_count : "..."})
            </button>

            <button
              type="button"
              onClick={() => {
                setTriStateFilter("KILLED");
                setCurrentPage(1);
              }}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                triStateFilter === "KILLED"
                  ? "bg-rose-600 text-white shadow-xs"
                  : "bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100"
              }`}
            >
              <XCircle className="w-3.5 h-3.5" />
              KILLED ({data ? data.killed_count : "..."})
            </button>

            <button
              type="button"
              onClick={() => {
                setTriStateFilter("INSUFFICIENT_EVIDENCE");
                setCurrentPage(1);
              }}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                triStateFilter === "INSUFFICIENT_EVIDENCE"
                  ? "bg-amber-600 text-white shadow-xs"
                  : "bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100"
              }`}
            >
              <HelpCircle className="w-3.5 h-3.5" />
              INSUFFICIENT EVIDENCE ({data ? data.insufficient_evidence_count : "..."})
            </button>
          </div>

          {/* Region and Category Dropdowns */}
          <div className="flex items-center gap-2">
            <select
              value={selectedRegion}
              onChange={(e) => {
                setSelectedRegion(e.target.value);
                setCurrentPage(1);
              }}
              aria-label="Filter by region"
              className="px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            >
              <option value="all">Region: All</option>
              <option value="India">Region: India</option>
              <option value="USA">Region: USA</option>
              <option value="Europe">Region: Europe</option>
              <option value="UK">Region: United Kingdom</option>
              <option value="GCC_MiddleEast">Region: GCC / Middle East</option>
            </select>

            <select
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                setCurrentPage(1);
              }}
              aria-label="Filter by category"
              className="px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            >
              <option value="all">Category: All</option>
              <option value="Home & Kitchen">Home &amp; Kitchen</option>
              <option value="Beauty & Grooming">Beauty &amp; Grooming</option>
              <option value="Electronics">Electronics</option>
            </select>
          </div>
        </div>

        {/* Opportunities Table */}
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 space-y-4">
              {[...Array(6)].map((_, i) => (
                <div
                  key={i}
                  className="h-12 bg-slate-100/70 rounded-lg animate-pulse"
                />
              ))}
            </div>
          ) : error ? (
            <div className="p-8">
              <ErrorState message={error} onRetry={fetchOpportunities} />
            </div>
          ) : !data || data.items.length === 0 ? (
            <div className="p-8">
              <EmptyState
                title="No opportunities found"
                description="No products matched this specific tri-state filter selection."
                actionLabel="View all opportunities"
                onAction={() => setTriStateFilter("ALL")}
              />
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/90 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-6">Candidate Product</th>
                  <th className="py-3 px-4">Decision State</th>
                  <th className="py-3 px-4">Current Gate</th>
                  <th className="py-3 px-4">Planned MSRP</th>
                  <th className="py-3 px-4">Score</th>
                  <th className="py-3 px-4">Arbiter Verdict / Action Plan</th>
                  <th className="py-3 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((item: OpportunityItem) => (
                  <tr
                    key={item.product_id}
                    className="hover:bg-slate-50/70 transition-colors group cursor-pointer"
                    onClick={() => setSelectedProductId(item.product_id)}
                  >
                    {/* Name */}
                    <td className="py-3.5 px-6">
                      <div className="max-w-xs">
                        <span className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-1 block">
                          {item.name}
                        </span>
                        <span className="text-[11px] text-slate-400">
                          {item.category || "General"} • {item.region || "Global"}
                        </span>
                      </div>
                    </td>

                    {/* Tri-state status */}
                    <td className="py-3.5 px-4">
                      {renderTriStateBadge(item.tri_state_status)}
                    </td>

                    {/* Current Gate */}
                    <td className="py-3.5 px-4">
                      <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                        Gate {item.current_gate} / 6
                      </span>
                    </td>

                    {/* Planned MSRP */}
                    <td className="py-3.5 px-4 font-semibold text-slate-900 font-mono">
                      {formatCurrency(item.planned_msrp)}
                    </td>

                    {/* Overall Score */}
                    <td className="py-3.5 px-4">
                      <ScoreBadge score={item.overall_score} size="md" />
                    </td>

                    {/* Arbiter Verdict / Action Plan */}
                    <td className="py-3.5 px-4 max-w-sm">
                      <p className="text-xs text-slate-700 line-clamp-2">
                        {item.action_plan ||
                          item.rejection_reason ||
                          item.arbiter_verdict ||
                          "Awaiting gate pipeline completion"}
                      </p>
                    </td>

                    {/* Action */}
                    <td className="py-3.5 px-6 text-right">
                      <Button
                        variant="primary"
                        size="xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedProductId(item.product_id);
                        }}
                        className="bg-indigo-600 hover:bg-indigo-700"
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer with Pagination */}
        {data && data.total > 0 && (
          <div className="border-t border-slate-200 px-6 bg-slate-50/50">
            <Pagination
              currentPage={currentPage}
              pageSize={pageSize}
              total={data.total}
              hasNext={data.has_next}
              onPageChange={(page) => setCurrentPage(page)}
              note="Strict tri-state classified opportunities"
            />
          </div>
        )}
      </div>

      {/* Product Dossier Modal */}
      <ProductDossierModal
        productId={selectedProductId}
        onClose={() => setSelectedProductId(null)}
      />
    </div>
  );
}
