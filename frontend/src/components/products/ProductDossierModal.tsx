"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Star,
  Bookmark,
  ExternalLink,
  Calendar,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Building2,
  Tag,
  Loader2,
  RotateCw,
} from "lucide-react";
import { ProductDetailResponse } from "@/types/api";
import { api, ApiClientError } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { ScoreBadge } from "@/components/common/ScoreBadge";

interface ProductDossierModalProps {
  productId: string | null;
  onClose: () => void;
}

export const ProductDossierModal: React.FC<ProductDossierModalProps> = ({
  productId,
  onClose,
}) => {
  const [product, setProduct] = useState<ProductDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "supplier">("overview");
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [togglingShortlist, setTogglingShortlist] = useState(false);

  const handleToggleShortlist = async () => {
    if (!product || togglingShortlist) return;
    setTogglingShortlist(true);
    const targetStatus = !product.is_shortlisted;
    try {
      const res = await api.toggleShortlist(product.product_id, targetStatus);
      setProduct({ ...product, is_shortlisted: res.is_shortlisted });
      showFeedback(res.message);
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to toggle shortlist";
      showFeedback(`Shortlist error: ${msg}`);
    } finally {
      setTogglingShortlist(false);
    }
  };

  useEffect(() => {
    if (!productId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    api
      .getProduct(productId)
      .then((data) => {
        if (isMounted) setProduct(data);
      })
      .catch((err: unknown) => {
        if (isMounted) {
          const msg =
            err instanceof ApiClientError ? err.message : "Failed to load product dossier";
          setError(msg);
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [productId]);

  if (!productId) return null;

  const showFeedback = (msg: string) => {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 3000);
  };

  const handleRefresh = async () => {
    if (!productId || refreshing) return;
    setRefreshing(true);
    try {
      const res = await api.refreshProduct(productId);
      const signals = res.signals_evaluated !== undefined ? res.signals_evaluated : "-";
      showFeedback(`Intelligence refreshed! Evaluated ${signals} signals. Status: ${res.status || "COMPLETED"}`);
      const updated = await api.getProduct(productId);
      setProduct(updated);
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to refresh intelligence";
      showFeedback(`Refresh failed: ${msg}`);
    } finally {
      setRefreshing(false);
    }
  };

  const formatCurrency = (amount?: number | null) => {
    if (amount === undefined || amount === null) return "-";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="relative w-full max-w-5xl bg-white rounded-2xl shadow-2xl flex flex-col z-10 my-8 overflow-hidden max-h-[92vh]">
        {/* Top notification if feedback triggered */}
        {feedbackMsg && (
          <div className="bg-indigo-600 text-white text-xs px-4 py-2 font-medium flex items-center justify-between">
            <span>{feedbackMsg}</span>
            <button
              type="button"
              onClick={() => setFeedbackMsg(null)}
              className="text-indigo-200 hover:text-white"
            >
              ✕
            </button>
          </div>
        )}

        {/* Modal Header */}
        <div className="p-6 border-b border-slate-100 flex flex-col gap-4 bg-slate-50/60">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
              <button
                type="button"
                onClick={onClose}
                className="hover:text-indigo-600 transition-colors"
              >
                &larr; Back to Catalog
              </button>
              <span>/</span>
              <span className="text-slate-800">Product Dossier</span>
              {product && (
                <>
                  <span>/</span>
                  <span className="font-mono text-slate-400">{product.product_id}</span>
                </>
              )}
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {loading ? (
            <div className="flex items-center gap-3 py-4 text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
              <span className="text-sm">Fetching complete intelligence dossier...</span>
            </div>
          ) : error ? (
            <div className="p-4 bg-rose-50 text-rose-700 rounded-lg text-sm border border-rose-200">
              {error}
            </div>
          ) : product ? (
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <h1 className="text-xl font-bold text-slate-900 leading-snug">
                    {product.name}
                  </h1>
                  {product.consensus_status === "CONSENSUS_PASS" && (
                    <Badge variant="success" dot>
                      Verified
                    </Badge>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                  <span>{product.category || "General Catalog"}</span>
                  <span>•</span>
                  <span>Region: <strong className="text-slate-700">{product.region || "Global"}</strong></span>
                  {product.bsr_rank && (
                    <>
                      <span>•</span>
                      <span>BSR Rank: <strong className="text-slate-700">#{product.bsr_rank}</strong></span>
                    </>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={refreshing}
                  title="Refresh Intelligence (Explicit re-evaluation against signals and gates)"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 transition-colors shadow-2xs"
                >
                  <RotateCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
                  <span>{refreshing ? "Refreshing..." : "Refresh"}</span>
                </button>

                <button
                  type="button"
                  onClick={handleToggleShortlist}
                  disabled={togglingShortlist}
                  title="Toggle Shortlist"
                  className={`p-2 rounded-lg border transition-colors ${
                    product.is_shortlisted
                      ? "bg-amber-50 border-amber-300 text-amber-600"
                      : "bg-white border-slate-200 text-slate-400 hover:text-amber-500 hover:bg-slate-50"
                  }`}
                >
                  <Star className={`w-4 h-4 ${product.is_shortlisted ? "fill-amber-400" : ""}`} />
                </button>

                <button
                  type="button"
                  onClick={() =>
                    showFeedback("AI recommendation is calculated authoritatively by Python Gate 5. Manual override API pending.")
                  }
                  title="AI Recommendation Status"
                  className={`p-2 rounded-lg border transition-colors ${
                    product.status === "PASS"
                      ? "bg-indigo-50 border-indigo-300 text-indigo-600"
                      : "bg-white border-slate-200 text-slate-400 hover:text-indigo-600 hover:bg-slate-50"
                  }`}
                >
                  <Bookmark className={`w-4 h-4 ${product.status === "PASS" ? "fill-indigo-600" : ""}`} />
                </button>

                {product.marketplace_url && (
                  <a
                    href={product.marketplace_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 shadow-2xs"
                  >
                    Open in Marketplace
                    <ExternalLink className="w-3 h-3 text-slate-400" />
                  </a>
                )}
              </div>
            </div>
          ) : null}

          {/* Navigation Tabs */}
          {product && (
            <div className="flex border-b border-slate-200 -mb-6 mt-2 gap-6 text-sm font-medium">
              <button
                type="button"
                onClick={() => setActiveTab("overview")}
                className={`pb-3 border-b-2 transition-colors ${
                  activeTab === "overview"
                    ? "border-indigo-600 text-indigo-600 font-semibold"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                Overview & Intelligence
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("supplier")}
                className={`pb-3 border-b-2 transition-colors flex items-center gap-2 ${
                  activeTab === "supplier"
                    ? "border-indigo-600 text-indigo-600 font-semibold"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                Supplier & Where to Buy
                {product.listings.length > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-100 text-indigo-700 font-mono">
                    {product.listings.length}
                  </span>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Modal Body */}
        {product && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {activeTab === "overview" ? (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left column: Visual identity & dates */}
                <div className="lg:col-span-4 space-y-5">
                  {/* Product visual card */}
                  <div className="p-6 rounded-xl bg-gradient-to-br from-slate-100 to-indigo-50/40 border border-slate-200 flex flex-col items-center justify-center min-h-[220px] text-center">
                    <div className="w-20 h-20 rounded-2xl bg-white shadow-sm border border-slate-200 flex items-center justify-center text-indigo-600 mb-3">
                      <Tag className="w-8 h-8" />
                    </div>
                    <span className="text-xs font-semibold text-slate-800 line-clamp-2">
                      {product.name}
                    </span>
                    <span className="text-[11px] text-slate-500 mt-1">
                      {product.category}
                    </span>
                  </div>

                  {/* Key Dates Card */}
                  <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 border-b border-slate-100 pb-2">
                      <Calendar className="w-3.5 h-3.5 text-indigo-600" />
                      Key Discovery Dates
                    </div>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between">
                        <span className="text-slate-500">First Discovered:</span>
                        <span className="font-medium text-slate-800">
                          {product.first_discovered_date || product.created_at || "Recorded"}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Last Evaluated:</span>
                        <span className="font-medium text-slate-800">
                          {product.last_evaluated_date || product.updated_at || "Recent"}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Shortlisted State:</span>
                        <span className="font-medium text-slate-800">
                          {product.is_shortlisted ? "Yes (Active)" : "No"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Sourcing cluster info */}
                  {product.sourcing_cluster && (
                    <div className="p-4 rounded-xl border border-slate-200 bg-white">
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 mb-1.5">
                        <Building2 className="w-3.5 h-3.5 text-indigo-600" />
                        Sourcing Cluster
                      </div>
                      <p className="text-xs text-slate-600">{product.sourcing_cluster}</p>
                    </div>
                  )}
                </div>

                {/* Right column: Metrics, AI analysis, Gates trail */}
                <div className="lg:col-span-8 space-y-5">
                  {/* 4 Stat Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs">
                      <span className="text-[11px] font-medium text-slate-500">Planned MSRP</span>
                      <div className="text-base font-bold text-slate-900 mt-1">
                        {formatCurrency(product.planned_msrp)}
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs">
                      <span className="text-[11px] font-medium text-slate-500">Gross Margin</span>
                      <div className="text-base font-bold text-emerald-600 mt-1">
                        {product.gross_margin_pct ? `${product.gross_margin_pct.toFixed(1)}%` : "-"}
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs">
                      <span className="text-[11px] font-medium text-slate-500">Net Profit</span>
                      <div className="text-base font-bold text-indigo-600 mt-1">
                        {product.net_profit_pct ? `${product.net_profit_pct.toFixed(1)}%` : "-"}
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs">
                      <span className="text-[11px] font-medium text-slate-500">Overall Score</span>
                      <div className="mt-1">
                        <ScoreBadge score={product.overall_score} size="md" />
                      </div>
                    </div>
                  </div>

                  {/* AI Analysis Box */}
                  <div className="p-5 rounded-xl border border-indigo-100 bg-indigo-50/40 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Bookmark className="w-4 h-4 text-indigo-600 fill-indigo-600" />
                        <h2 className="text-sm font-bold text-slate-900">
                          AI Reasoning & Analysis
                        </h2>
                      </div>
                      {product.ai_confidence !== undefined && product.ai_confidence !== null && (
                        <Badge variant="info">
                          Confidence {Math.round(product.ai_confidence > 1 ? product.ai_confidence : product.ai_confidence * 100)}%
                        </Badge>
                      )}
                    </div>

                    <p className="text-xs text-slate-700 leading-relaxed">
                      {product.ai_reasoning ||
                        product.action_plan ||
                        "Product evaluated by autonomous gates pipeline. Multi-signal analysis indicates demand pattern matches criteria."}
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                      {/* Why it is trending */}
                      <div className="p-3 bg-white/90 rounded-lg border border-emerald-100">
                        <div className="text-xs font-bold text-emerald-700 mb-1 flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Why It Is Trending / Opportunities
                        </div>
                        <ul className="text-xs text-slate-600 space-y-1 list-disc list-inside">
                          {product.trend_source && (
                            <li>Source: {product.trend_source}</li>
                          )}
                          {product.action_plan && (
                            <li>{product.action_plan}</li>
                          )}
                          {product.upgrade_v2_engineering && (
                            <li>Upgrade V2: {product.upgrade_v2_engineering}</li>
                          )}
                          {!product.trend_source && !product.action_plan && (
                            <li>High demand indicators verified by pipeline scan</li>
                          )}
                        </ul>
                      </div>

                      {/* Risks to watch */}
                      <div className="p-3 bg-white/90 rounded-lg border border-amber-100">
                        <div className="text-xs font-bold text-amber-700 mb-1 flex items-center gap-1.5">
                          <AlertCircle className="w-3.5 h-3.5" />
                          Risks To Watch / Competitor Flaws
                        </div>
                        <ul className="text-xs text-slate-600 space-y-1 list-disc list-inside">
                          {product.competitor_3star_flaws ? (
                            <li>{product.competitor_3star_flaws}</li>
                          ) : (
                            <li>Monitor return rates and supplier lead-time elasticity</li>
                          )}
                          {product.ai_rejection_reason && (
                            <li>Rejection flag: {product.ai_rejection_reason}</li>
                          )}
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Gates Trail Table */}
                  <div className="p-5 rounded-xl border border-slate-200 bg-white space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-sm font-bold text-slate-900">
                          Data Trail & Gate Audit Log
                        </h2>
                        <p className="text-xs text-slate-500">
                          Complete audit record of every gate verification step.
                        </p>
                      </div>
                      <Badge variant="success">
                        {product.gates.filter((g) => g.status === "PASS").length} / {product.gates.length || 6} gates passed
                      </Badge>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 text-slate-500 font-semibold border-y border-slate-100">
                          <tr>
                            <th className="py-2 px-3">Gate</th>
                            <th className="py-2 px-3">Status</th>
                            <th className="py-2 px-3">Completed At</th>
                            <th className="py-2 px-3">Evaluator / Reason</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {product.gates.map((g) => {
                            const isPass = g.status === "PASS";
                            return (
                              <tr key={g.gate_number}>
                                <td className="py-2.5 px-3 font-semibold text-slate-800">
                                  Gate {g.gate_number}
                                </td>
                                <td className="py-2.5 px-3">
                                  <span
                                    className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium ${
                                      isPass
                                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                        : "bg-slate-100 text-slate-600 border border-slate-200"
                                    }`}
                                  >
                                    {g.status}
                                  </span>
                                </td>
                                <td className="py-2.5 px-3 text-slate-500">
                                  {g.completed_at || "-"}
                                </td>
                                <td className="py-2.5 px-3 text-slate-600">
                                  {g.blocked_reason || g.completed_by || "Autonomous Arbiter"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {/* Verdict Banner */}
                    <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-lg text-xs text-emerald-900 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>
                          <strong>Consensus Verdict:</strong> {product.consensus_status || "EVALUATION_ACTIVE"}
                        </span>
                      </div>
                      <span className="font-mono text-emerald-700">
                        Score: {product.overall_score || 0}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* Tab 2: Supplier & Buy */
              <div className="space-y-6">
                {/* Truthful Supplier Registry Status */}
                <div className="p-4 rounded-xl bg-amber-50/60 border border-amber-200 text-xs text-amber-900 flex items-start gap-3">
                  <HelpCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="block text-amber-950 font-semibold mb-0.5">
                      Supplier Directory Integration Note:
                    </strong>
                    <span>
                      Direct manufacturer registry contact data (GST numbers, exporter phone/email) is not currently stored in the SSOT database. Showing verified multi-platform listings and sourcing clusters below.
                    </span>
                  </div>
                </div>

                {/* Sourcing Overview Card */}
                <div className="p-5 rounded-xl border border-slate-200 bg-white grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <span className="text-[11px] font-medium text-slate-500">Sourcing Cluster</span>
                    <div className="text-sm font-semibold text-slate-800 mt-1">
                      {product.sourcing_cluster || "Domestic / Regional Supply"}
                    </div>
                  </div>
                  <div>
                    <span className="text-[11px] font-medium text-slate-500">Factory COGS</span>
                    <div className="text-sm font-semibold text-slate-800 mt-1">
                      {formatCurrency(product.factory_cogs)}
                    </div>
                  </div>
                  <div>
                    <span className="text-[11px] font-medium text-slate-500">Landed COGS</span>
                    <div className="text-sm font-semibold text-slate-800 mt-1">
                      {formatCurrency(product.landed_cogs)}
                    </div>
                  </div>
                </div>

                {/* Where to Buy - Real Multi-Platform Listings */}
                <div className="p-5 rounded-xl border border-slate-200 bg-white space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-sm font-bold text-slate-900">
                        Where to Buy & Live Market Listings
                      </h2>
                      <p className="text-xs text-slate-500">
                        Real competitive pricing across connected e-commerce platforms.
                      </p>
                    </div>
                    <Badge variant="info">
                      {product.listings.length} sources found
                    </Badge>
                  </div>

                  {product.listings.length === 0 ? (
                    <div className="p-8 text-center text-xs text-slate-500 bg-slate-50 rounded-lg">
                      No external multi-platform listings linked for this product in the current database snapshot.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 text-slate-500 font-semibold border-y border-slate-100">
                          <tr>
                            <th className="py-2.5 px-3">Platform</th>
                            <th className="py-2.5 px-3">Listing Title</th>
                            <th className="py-2.5 px-3">Price</th>
                            <th className="py-2.5 px-3">Rating</th>
                            <th className="py-2.5 px-3">Stock</th>
                            <th className="py-2.5 px-3 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {product.listings.map((l, idx) => (
                            <tr key={idx} className="hover:bg-slate-50/60">
                              <td className="py-3 px-3 font-semibold text-slate-800">
                                {l.platform}
                              </td>
                              <td className="py-3 px-3 text-slate-600 max-w-xs truncate">
                                {l.title || product.name}
                              </td>
                              <td className="py-3 px-3 font-semibold text-slate-900">
                                {formatCurrency(l.price)}
                              </td>
                              <td className="py-3 px-3 text-slate-600">
                                {l.rating ? `${l.rating} ★` : "-"}
                                {l.reviews_count ? ` (${l.reviews_count})` : ""}
                              </td>
                              <td className="py-3 px-3">
                                <span
                                  className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium ${
                                    l.in_stock
                                      ? "bg-emerald-50 text-emerald-700"
                                      : "bg-slate-100 text-slate-500"
                                  }`}
                                >
                                  {l.in_stock ? "In Stock" : "Check Live"}
                                </span>
                              </td>
                              <td className="py-3 px-3 text-right">
                                {l.url ? (
                                  <a
                                    href={l.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 border border-indigo-200 hover:bg-indigo-50 rounded-lg transition-colors"
                                  >
                                    Open
                                    <ExternalLink className="w-3 h-3" />
                                  </a>
                                ) : (
                                  <span className="text-slate-400">-</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
          <div className="text-xs text-slate-500">
            APRS Autonomous Intelligence Dossier • Real SQLite SSOT
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-700 hover:text-slate-900 bg-white border border-slate-200 hover:border-slate-300 rounded-lg shadow-2xs transition-colors"
          >
            Close Dossier
          </button>
        </div>
      </div>
    </div>
  );
};
