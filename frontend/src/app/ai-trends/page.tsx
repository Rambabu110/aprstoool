"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles,
  SlidersHorizontal,
  AlertTriangle,
  Star,
} from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import { ProductSummary, ProductListResponse } from "@/types/api";
import { PlatformFilterBar } from "@/components/common/PlatformFilterBar";
import { FilterBar } from "@/components/common/FilterBar";
import { Pagination } from "@/components/common/Pagination";
import { GateBadge } from "@/components/common/GateBadge";
import { MarketplaceBadge } from "@/components/common/MarketplaceBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { CustomizeLogicDrawer, LogicConfig } from "@/components/common/CustomizeLogicDrawer";
import { ProductDossierModal } from "@/components/products/ProductDossierModal";
import { Button } from "@/components/ui/Button";

export default function AITrendsPage() {
  // State
  const [verifiedData, setVerifiedData] = useState<ProductListResponse | null>(null);
  const [unverifiedData, setUnverifiedData] = useState<ProductListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active view tab: "verified" | "unverified"
  const [activeTab, setActiveTab] = useState<"verified" | "unverified">("verified");

  // Filters
  const [selectedSource, setSelectedSource] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRegion, setSelectedRegion] = useState("all");
  const [selectedSort, setSelectedSort] = useState("score_desc");
  const [currentPage, setCurrentPage] = useState(1);

  // Modals & Drawers
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const pageSize = 15;

  const showFeedback = (msg: string) => {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 3500);
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    let sort_by = "overall_score";
    let sort_order: "asc" | "desc" = "desc";
    if (selectedSort === "date_desc") {
      sort_by = "created_at";
      sort_order = "desc";
    } else if (selectedSort === "price_asc") {
      sort_by = "planned_msrp";
      sort_order = "asc";
    } else if (selectedSort === "price_desc") {
      sort_by = "planned_msrp";
      sort_order = "desc";
    }

    try {
      // Query verified products (status=PASS) and unverified products (status=PENDING)
      const [verifiedRes, unverifiedRes] = await Promise.all([
        api.getProducts({
          page: activeTab === "verified" ? currentPage : 1,
          pageSize,
          status: "PASS",
          region: selectedRegion === "all" ? undefined : selectedRegion,
          search: searchQuery.trim() ? searchQuery.trim() : undefined,
          sort_by,
          sort_order,
        }),
        api.getProducts({
          page: activeTab === "unverified" ? currentPage : 1,
          pageSize,
          status: "PENDING",
          region: selectedRegion === "all" ? undefined : selectedRegion,
          search: searchQuery.trim() ? searchQuery.trim() : undefined,
          sort_by,
          sort_order,
        }),
      ]);

      setVerifiedData(verifiedRes);
      setUnverifiedData(unverifiedRes);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError ? err.message : "Failed to load AI intelligence data.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [activeTab, currentPage, selectedRegion, searchQuery, selectedSort]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleResetFilters = () => {
    setSelectedSource("all");
    setSearchQuery("");
    setSelectedRegion("all");
    setSelectedSort("score_desc");
    setCurrentPage(1);
  };

  const formatCurrency = (val?: number | null) => {
    if (val === undefined || val === null) return "-";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return "-";
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "2-digit",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  const currentDisplayData =
    activeTab === "verified" ? verifiedData : unverifiedData;

  return (
    <div className="space-y-5">
      {/* Feedback Toast */}
      {feedbackMsg && (
        <div className="bg-indigo-600 text-white text-xs px-4 py-2.5 rounded-lg shadow-md flex items-center justify-between">
          <span>{feedbackMsg}</span>
          <button
            type="button"
            onClick={() => setFeedbackMsg(null)}
            className="text-indigo-200 hover:text-white ml-4 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* Header matching Figma */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              AI Trending Page
            </h1>
            <span className="p-1 rounded-md bg-indigo-50 text-indigo-600">
              <Sparkles className="w-4 h-4" />
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Trending products found and verified by APRS intelligence pipeline
          </p>
        </div>

        {/* Top Right Controls */}
        <div className="flex items-center gap-2.5">
          <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200/80 text-xs font-medium hidden md:inline-flex">
            Logic: AI multi-signal velocity
          </span>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsDrawerOpen(true)}
            icon={<SlidersHorizontal className="w-3.5 h-3.5" />}
            className="bg-indigo-600 hover:bg-indigo-700"
          >
            Customize logic
          </Button>
        </div>
      </div>

      {/* Main Container Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs overflow-hidden">
        {/* Source Pills Bar */}
        <div className="px-6 pt-3">
          <PlatformFilterBar
            selectedSource={selectedSource}
            onSelectSource={(src) => {
              setSelectedSource(src);
              setCurrentPage(1);
            }}
            onAddSourceClick={() =>
              showFeedback("Custom scraper crawler integration is available in the Integrations module.")
            }
          />
        </div>

        {/* Tabs: Verified by APRS vs Not Verified */}
        <div className="px-6 flex items-center gap-6 border-b border-slate-200 text-xs font-semibold">
          <button
            type="button"
            onClick={() => {
              setActiveTab("verified");
              setCurrentPage(1);
            }}
            className={`py-3 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "verified"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Verified by APRS
            {verifiedData && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-50 text-indigo-700 font-mono">
                {verifiedData.total}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab("unverified");
              setCurrentPage(1);
            }}
            className={`py-3 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "unverified"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Not verified - gates not run
            {unverifiedData && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-amber-50 text-amber-700 font-mono">
                {unverifiedData.total}
              </span>
            )}
          </button>
        </div>

        {/* Filter Controls Row */}
        <div className="px-6 py-2 bg-slate-50/50 border-b border-slate-100">
          <FilterBar
            searchQuery={searchQuery}
            onSearchChange={(q) => {
              setSearchQuery(q);
              setCurrentPage(1);
            }}
            selectedRegion={selectedRegion}
            onRegionChange={(r) => {
              setSelectedRegion(r);
              setCurrentPage(1);
            }}
            selectedSort={selectedSort}
            onSortChange={(s) => {
              setSelectedSort(s);
              setCurrentPage(1);
            }}
            sortOptions={[
              { id: "score_desc", label: "Sort: AI score (High to Low)" },
              { id: "date_desc", label: "Sort: Newest discovered" },
              { id: "price_asc", label: "Price: Low to High" },
              { id: "price_desc", label: "Price: High to Low" },
            ]}
            onReset={handleResetFilters}
            placeholder="Search verified products or niches..."
          />
        </div>

        {/* Optional Banner for Unverified Tab */}
        {activeTab === "unverified" && (
          <div className="mx-6 my-4 p-4 rounded-xl bg-amber-50/70 border border-amber-200 text-xs text-amber-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <strong className="block text-amber-950 font-semibold mb-0.5">
                  Not verified by APRS — gates not run ({unverifiedData?.total || 0})
                </strong>
                <span>
                  These products were extracted from source signals, but the deep gate pipeline has not completed for them.
                </span>
              </div>
            </div>
            <Button
              variant="outline"
              size="xs"
              onClick={() =>
                showFeedback("Batch gate execution is an autonomous daemon job managed under V8 Scheduler (Phase 4).")
              }
              className="bg-white border-amber-300 text-amber-900 hover:bg-amber-100 shrink-0 font-medium"
            >
              Run gates for all
            </Button>
          </div>
        )}

        {/* Data Table */}
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
              <ErrorState message={error} onRetry={fetchData} />
            </div>
          ) : !currentDisplayData || currentDisplayData.items.length === 0 ? (
            <div className="p-8">
              <EmptyState
                title="No products found"
                description="No products matched your active filters in this verification section."
                actionLabel="Reset filters"
                onAction={handleResetFilters}
              />
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/90 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-6">Product</th>
                  <th className="py-3 px-4">Source</th>
                  <th className="py-3 px-4">Price</th>
                  <th className="py-3 px-4">Gates</th>
                  <th className="py-3 px-4">Discovered</th>
                  <th className="py-3 px-4">AI Score</th>
                  <th className="py-3 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {currentDisplayData.items.map((prod: ProductSummary) => {
                  const isVerified = prod.status === "PASS";

                  return (
                    <tr
                      key={prod.product_id}
                      className="hover:bg-slate-50/70 transition-colors group"
                    >
                      {/* Product Name & Visual */}
                      <td className="py-3.5 px-6">
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={() =>
                              showFeedback("Shortlist mutation API (POST /products/{id}/shortlist) is pending backend release.")
                            }
                            title="Shortlist"
                            className="text-slate-300 hover:text-amber-500 transition-colors"
                          >
                            <Star
                              className={`w-4 h-4 ${
                                prod.is_shortlisted ? "fill-amber-400 text-amber-500" : ""
                              }`}
                            />
                          </button>

                          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-50 to-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 font-semibold text-xs shrink-0">
                            {prod.name.charAt(0)}
                          </div>

                          <div className="max-w-md">
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => setSelectedProductId(prod.product_id)}
                                className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors text-left line-clamp-1"
                              >
                                {prod.name}
                              </button>
                              {isVerified && (
                                <span className="px-1.5 py-0.2 rounded text-[10px] bg-emerald-50 text-emerald-700 font-semibold">
                                  Verified
                                </span>
                              )}
                            </div>
                            <span className="block text-[11px] text-slate-400 line-clamp-1">
                              {prod.category || "General Catalog"} • {prod.region || "Global"}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Source */}
                      <td className="py-3.5 px-4">
                        <MarketplaceBadge source={prod.trend_source || "Amazon"} />
                      </td>

                      {/* Planned MSRP */}
                      <td className="py-3.5 px-4 font-semibold text-slate-900">
                        {formatCurrency(prod.planned_msrp)}
                      </td>

                      {/* Gates Progress */}
                      <td className="py-3.5 px-4">
                        <GateBadge
                          passed={prod.gates_passed}
                          total={5}
                          status={prod.status}
                        />
                      </td>

                      {/* Discovered */}
                      <td className="py-3.5 px-4 text-slate-500">
                        {formatDate(prod.created_at)}
                      </td>

                      {/* AI Score / Confidence */}
                      <td className="py-3.5 px-4">
                        {prod.overall_score && prod.overall_score > 0 ? (
                          <span className="font-mono font-bold text-indigo-600">
                            {Math.round(prod.overall_score)}%
                          </span>
                        ) : (
                          <span className="text-slate-400 font-mono">-</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-6 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <Button
                            variant="primary"
                            size="xs"
                            onClick={() => setSelectedProductId(prod.product_id)}
                            className="bg-indigo-600 hover:bg-indigo-700"
                          >
                            Details
                          </Button>
                          {isVerified ? (
                            <Button
                              variant="outline"
                              size="xs"
                              onClick={() =>
                                showFeedback("Remove product from trending moves it to archive. Mutation API pending.")
                              }
                              className="text-slate-500 hover:text-rose-600 hover:border-rose-200"
                            >
                              Remove
                            </Button>
                          ) : (
                            <Button
                              variant="outline"
                              size="xs"
                              onClick={() =>
                                showFeedback("Manual single-product gate execution will be linked via V8 Scheduler API.")
                              }
                              className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                            >
                              Run gates
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer with Pagination */}
        {currentDisplayData && currentDisplayData.total > 0 && (
          <div className="border-t border-slate-200 px-6 bg-slate-50/50">
            <Pagination
              currentPage={currentPage}
              pageSize={pageSize}
              total={currentDisplayData.total}
              hasNext={currentDisplayData.has_next}
              onPageChange={(page) => setCurrentPage(page)}
              note={
                activeTab === "verified"
                  ? `${verifiedData?.total || 0} verified products`
                  : `${unverifiedData?.total || 0} products pending evaluation`
              }
            />
          </div>
        )}
      </div>

      {/* Customize Logic Slide-over Drawer */}
      <CustomizeLogicDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onApply={(config: LogicConfig) => {
          showFeedback(`Discovery logic filters updated for country: ${config.country}.`);
          fetchData();
        }}
      />

      {/* Product Dossier Modal */}
      <ProductDossierModal
        productId={selectedProductId}
        onClose={() => setSelectedProductId(null)}
      />
    </div>
  );
}
