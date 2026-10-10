"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Star } from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import { ProductSummary, ProductListResponse } from "@/types/api";
import { PlatformFilterBar } from "@/components/common/PlatformFilterBar";
import { FilterBar } from "@/components/common/FilterBar";
import { Pagination } from "@/components/common/Pagination";
import { ScoreBadge } from "@/components/common/ScoreBadge";
import { GateBadge } from "@/components/common/GateBadge";
import { MarketplaceBadge } from "@/components/common/MarketplaceBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ProductDossierModal } from "@/components/products/ProductDossierModal";
import { Button } from "@/components/ui/Button";

export default function MyShortlistPage() {
  // State
  const [data, setData] = useState<ProductListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedSource, setSelectedSource] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRegion, setSelectedRegion] = useState("all");
  const [selectedSort, setSelectedSort] = useState("score_desc");
  const [currentPage, setCurrentPage] = useState(1);

  // Dossier modal
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const pageSize = 25;

  const showFeedback = (msg: string) => {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 3500);
  };

  const fetchShortlist = useCallback(async () => {
    setLoading(true);
    setError(null);

    let sort_by = "overall_score";
    let sort_order: "asc" | "desc" = "desc";

    if (selectedSort === "price_desc") {
      sort_by = "planned_msrp";
      sort_order = "desc";
    } else if (selectedSort === "price_asc") {
      sort_by = "planned_msrp";
      sort_order = "asc";
    } else if (selectedSort === "date_desc") {
      sort_by = "created_at";
      sort_order = "desc";
    }

    try {
      const res = await api.getProducts({
        page: currentPage,
        pageSize,
        is_shortlisted: true,
        region: selectedRegion === "all" ? undefined : selectedRegion,
        search: searchQuery.trim() ? searchQuery.trim() : undefined,
        sort_by,
        sort_order,
      });
      setData(res);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError ? err.message : "Failed to load shortlisted products.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [currentPage, selectedRegion, searchQuery, selectedSort]);

  useEffect(() => {
    fetchShortlist();
  }, [fetchShortlist]);

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
              My Shortlist
            </h1>
            <span className="p-1 rounded-md bg-amber-50 text-amber-600">
              <Star className="w-4 h-4 fill-amber-400" />
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Products you starred for deeper research, economics, and procurement
          </p>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2.5 text-xs">
          <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200/80 font-medium">
            SSOT Shortlist Filter
          </span>
          <span className="px-2.5 py-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200 font-semibold font-mono">
            {data ? `${data.total} products` : "Loading..."}
          </span>
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

        {/* Filter Controls Row */}
        <div className="px-6 py-2 bg-slate-50/50 border-y border-slate-100">
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
              { id: "score_desc", label: "Sort: Trend score (High to Low)" },
              { id: "score_asc", label: "Sort: Trend score (Low to High)" },
              { id: "date_desc", label: "Sort: Discovered date" },
              { id: "price_asc", label: "Price: Low to High" },
              { id: "price_desc", label: "Price: High to Low" },
            ]}
            onReset={handleResetFilters}
            placeholder="Search shortlisted products..."
          />
        </div>

        {/* Data Table */}
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 space-y-4">
              {[...Array(4)].map((_, i) => (
                <div
                  key={i}
                  className="h-12 bg-slate-100/70 rounded-lg animate-pulse"
                />
              ))}
            </div>
          ) : error ? (
            <div className="p-8">
              <ErrorState message={error} onRetry={fetchShortlist} />
            </div>
          ) : !data || data.items.length === 0 ? (
            <div className="p-8">
              <EmptyState
                title="No shortlisted products found"
                description="You currently have no products marked as shortlisted with the active filters."
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
                  <th className="py-3 px-4">Score</th>
                  <th className="py-3 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((prod: ProductSummary) => (
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
                            showFeedback("Shortlist removal mutation (POST /products/{id}/shortlist) is pending backend API implementation.")
                          }
                          title="Shortlisted"
                          className="text-amber-500 hover:text-amber-600 transition-colors"
                        >
                          <Star className="w-4 h-4 fill-amber-400" />
                        </button>

                        <div className="w-8 h-8 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-700 font-semibold text-xs shrink-0">
                          {prod.name.charAt(0)}
                        </div>

                        <div className="max-w-md">
                          <button
                            type="button"
                            onClick={() => setSelectedProductId(prod.product_id)}
                            className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors text-left line-clamp-1 block"
                          >
                            {prod.name}
                          </button>
                          <span className="block text-[11px] text-slate-400 line-clamp-1">
                            {prod.category || "General"} • {prod.region || "Global"}
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Source */}
                    <td className="py-3.5 px-4">
                      <MarketplaceBadge source={prod.trend_source || "Amazon"} />
                    </td>

                    {/* Price */}
                    <td className="py-3.5 px-4 font-semibold text-slate-900 font-mono">
                      {formatCurrency(prod.planned_msrp)}
                    </td>

                    {/* Gates */}
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

                    {/* Score */}
                    <td className="py-3.5 px-4">
                      <ScoreBadge score={prod.overall_score} size="md" />
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
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={() =>
                            showFeedback("Remove product from shortlist mutation API (POST /products/{id}/shortlist) is pending backend release.")
                          }
                          className="text-slate-500 hover:text-rose-600 hover:border-rose-200"
                        >
                          Remove
                        </Button>
                      </div>
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
              note="Remove moves a product out of your shortlist - nothing is deleted permanently"
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
