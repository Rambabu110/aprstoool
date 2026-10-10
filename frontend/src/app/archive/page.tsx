"use client";

import React, { useState, useEffect } from "react";
import {
  RotateCw,
  Users,
  Calendar,
  Lock,
  Archive,
  RefreshCw,
  CheckCircle2,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { ArchiveOverviewResponse } from "@/types/api";
import { ErrorState } from "@/components/common/ErrorState";
import { ScoreBadge } from "@/components/common/ScoreBadge";

export default function ArchivePage() {
  const [data, setData] = useState<ArchiveOverviewResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"decisions" | "meetings" | "soft_deleted">("decisions");

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [restoreMessage, setRestoreMessage] = useState<string | null>(null);

  useEffect(() => {
    async function loadArchive() {
      setLoading(true);
      setError(null);
      try {
        const res = await apiClient.getArchiveOverview();
        setData(res);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load archive data");
      } finally {
        setLoading(false);
      }
    }
    loadArchive();
  }, []);

  const handleRestore = async (productId: string) => {
    setRestoringId(productId);
    setRestoreMessage(null);
    try {
      const res = await apiClient.restoreArchivedProduct(productId);
      setRestoreMessage(res.message);
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          archived_products: (prev.archived_products || []).filter((p) => p.product_id !== productId),
          total_soft_deleted: Math.max(0, (prev.total_soft_deleted ?? 1) - 1),
        };
      });
      setTimeout(() => setRestoreMessage(null), 5000);
    } catch (err: unknown) {
      alert(`Restore failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setRestoringId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center space-y-4">
        <RotateCw className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500">Loading Historical Archive &amp; Audit Trail...</p>
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
              Historical Records &amp; Cryptographic Archive
            </h1>
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700">
              <Lock className="mr-1 h-3 w-3 text-slate-500" />
              Immutable Snapshot Ledgers
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Cryptographically sealed decision ledger, multi-agent meeting transcripts, and soft-deleted recovery.
          </p>
        </div>
      </div>

      {restoreMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-xl flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{restoreMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setRestoreMessage(null)}
            className="text-emerald-600 hover:text-emerald-900 font-bold ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* KPI Overview Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Sealed Decision Snapshots</span>
          <p className="mt-2 text-2xl font-bold text-slate-900">{data?.total_archived_decisions ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Cryptographically frozen records</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Meeting Transcript Logs</span>
          <p className="mt-2 text-2xl font-bold text-indigo-600">{data?.total_meeting_logs ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Logged dialogue turns</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Historical Defect Clusters</span>
          <p className="mt-2 text-2xl font-bold text-blue-600">{data?.total_defect_clusters ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Tracked failure modes</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">Recoverable Soft-Deleted</span>
          <p className="mt-2 text-2xl font-bold text-amber-600">
            {data?.total_soft_deleted ?? (data?.archived_products?.length ?? 0)}
          </p>
          <p className="mt-1 text-xs text-slate-500">Products in recycle archive</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab("decisions")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "decisions"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Lock className="h-4 w-4" />
            <span>Frozen Decision Ledger ({data?.total_archived_decisions ?? 0})</span>
          </button>
          <button
            onClick={() => setActiveTab("meetings")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "meetings"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Users className="h-4 w-4" />
            <span>Multi-Agent Meeting Transcript Logs ({data?.total_meeting_logs ?? 0})</span>
          </button>
          <button
            onClick={() => setActiveTab("soft_deleted")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "soft_deleted"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Archive className="h-4 w-4" />
            <span>
              Soft-Deleted Products ({data?.total_soft_deleted ?? (data?.archived_products?.length ?? 0)})
            </span>
          </button>
        </nav>
      </div>

      {/* TAB 1: DECISION LEDGER */}
      {activeTab === "decisions" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 text-xs text-amber-900">
            <span className="font-bold">Authoritative Preservation Notice:</span> All decision ledger records are permanent cryptographic snapshots of the autonomous engine. Row mutations and synthetic inserts are strictly barred by schema policy.
          </div>

          <div className="space-y-4">
            {(data?.decision_ledger_records || []).map((dec) => (
              <div
                key={dec.decision_id}
                className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4"
              >
                <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center border-b border-slate-100 pb-4">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs font-bold text-slate-700">
                        #{dec.decision_id}
                      </span>
                      <h3 className="text-lg font-bold text-slate-900">{dec.product_name}</h3>
                      <span className="font-mono text-xs text-slate-400">({dec.product_id})</span>
                    </div>
                    <div className="mt-1 flex items-center space-x-3 text-xs text-slate-500">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5 text-slate-400" />
                        {dec.decision_timestamp}
                      </span>
                      <span>&bull;</span>
                      <span>Model: <strong>{dec.model_version}</strong></span>
                      <span>&bull;</span>
                      <span>Policy: <strong>{dec.policy_version || "V7.2"}</strong></span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-bold ${
                        dec.kill_status === "SURVIVES"
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {dec.kill_status}
                    </span>
                    <ScoreBadge score={dec.opportunity_score} size="md" />
                  </div>
                </div>

                {/* Metrics Grid */}
                <div>
                  <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                    Frozen Commercial Predictions
                  </h4>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 text-xs">
                    <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-medium">Daily Units</span>
                      <strong className="text-slate-900 text-sm">
                        {dec.metrics.predicted_daily_units != null ? String(dec.metrics.predicted_daily_units) : "—"} / day
                      </strong>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-medium">Selling Price</span>
                      <strong className="text-slate-900 text-sm">
                        {dec.metrics.predicted_selling_price != null ? `$${String(dec.metrics.predicted_selling_price)}` : "—"}
                      </strong>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-medium">Landed COGS</span>
                      <strong className="text-slate-900 text-sm">
                        {dec.metrics.predicted_cogs != null ? `$${String(dec.metrics.predicted_cogs)}` : "—"}
                      </strong>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-medium">Contribution Margin</span>
                      <strong className="text-emerald-600 text-sm">
                        {dec.metrics.predicted_cm_pct != null ? `${String(dec.metrics.predicted_cm_pct)}%` : "—"}
                      </strong>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-medium">Predicted CAC</span>
                      <strong className="text-slate-900 text-sm">
                        {dec.metrics.predicted_cac != null ? `$${String(dec.metrics.predicted_cac)}` : "—"}
                      </strong>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-medium">RTO Risk Reserve</span>
                      <strong className="text-slate-900 text-sm">
                        {dec.metrics.predicted_rto_pct != null ? `${String(dec.metrics.predicted_rto_pct)}%` : "—"}
                      </strong>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: MEETING AUDIT LOGS */}
      {activeTab === "meetings" && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
          <div className="border-b border-slate-200 px-6 py-4">
            <h3 className="text-base font-semibold text-slate-900">
              Genesis Multi-Agent Review Session Transcripts
            </h3>
            <p className="text-xs text-slate-500">
              Real-time audit log captured from meeting_audit_log table
            </p>
          </div>

          <div className="divide-y divide-slate-100 p-4 space-y-4">
            {(data?.meeting_audit_logs || []).map((m) => (
              <div key={m.message_id} className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-sm text-slate-900">{m.speaker_name}</span>
                    <span className="rounded bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-700 uppercase">
                      {m.speaker_role}
                    </span>
                    <span className="font-mono text-xs text-slate-400">({m.session_id})</span>
                  </div>
                  <span className="text-xs text-slate-400">{m.timestamp}</span>
                </div>

                {m.user_prompt && (
                  <p className="text-xs text-slate-500 italic bg-white p-2.5 rounded-sm border border-slate-100">
                    &quot;{m.user_prompt}&quot;
                  </p>
                )}

                <div className="text-xs text-slate-800 leading-relaxed font-sans bg-white p-3 rounded-lg border border-slate-200 shadow-2xs whitespace-pre-wrap">
                  {m.response_text}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: SOFT-DELETED PRODUCTS RECOVERY (Streamlit Parity) */}
      {activeTab === "soft_deleted" && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
          <div className="border-b border-slate-200 px-6 py-4 flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-900">
                Recycle Archive &amp; Soft-Deleted Products
              </h3>
              <p className="text-xs text-slate-500">
                Products marked as soft-deleted (is_deleted = 1). Restoring returns them to the active catalog without mutating historical evidence.
              </p>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
              {data?.archived_products?.length ?? 0} recoverable
            </span>
          </div>

          {!data?.archived_products || data.archived_products.length === 0 ? (
            <div className="p-16 text-center space-y-2">
              <Archive className="w-10 h-10 text-slate-300 mx-auto" />
              <h4 className="text-sm font-semibold text-slate-700">Zero Soft-Deleted Products</h4>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                No products are currently in the soft-deleted recycle archive. All active catalog products are retained in the master catalog.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 font-semibold text-slate-600">
                  <tr>
                    <th className="px-6 py-3">Product ID</th>
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Region</th>
                    <th className="px-4 py-3">Deletion Reason</th>
                    <th className="px-4 py-3">Deleted At</th>
                    <th className="px-6 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.archived_products.map((p) => (
                    <tr key={p.product_id} className="hover:bg-slate-50/70">
                      <td className="px-6 py-3.5 font-mono font-medium text-slate-900">
                        {p.product_id}
                      </td>
                      <td className="px-4 py-3.5 font-medium text-slate-800 max-w-xs truncate">
                        {p.name}
                      </td>
                      <td className="px-4 py-3.5 text-slate-600">{p.category || "—"}</td>
                      <td className="px-4 py-3.5 text-slate-600">{p.region || "—"}</td>
                      <td className="px-4 py-3.5 text-slate-500 italic max-w-xs truncate">
                        {p.delete_reason || "Archived by operator"}
                      </td>
                      <td className="px-4 py-3.5 text-slate-400 font-mono text-[11px]">
                        {p.soft_deleted_at || "—"}
                      </td>
                      <td className="px-6 py-3.5 text-right">
                        <button
                          type="button"
                          onClick={() => handleRestore(p.product_id)}
                          disabled={restoringId === p.product_id}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors disabled:opacity-50 shadow-2xs"
                        >
                          <RefreshCw
                            className={`w-3.5 h-3.5 ${restoringId === p.product_id ? "animate-spin" : ""}`}
                          />
                          <span>{restoringId === p.product_id ? "Restoring..." : "Restore Product"}</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
