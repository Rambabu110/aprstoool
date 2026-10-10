"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Package, Star } from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import { ProductSummary, ProductListResponse } from "@/types/api";
import { FilterBar } from "@/components/common/FilterBar";
import { Pagination } from "@/components/common/Pagination";
import { ScoreBadge } from "@/components/common/ScoreBadge";
import { GateBadge } from "@/components/common/GateBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ProductDossierModal } from "@/components/products/ProductDossierModal";
import { Button } from "@/components/ui/Button";

function ProductsCatalogContent() {
  const searchParams = useSearchParams();

  // Initial search from query params (e.g. from /trends "Find Products")
  const initialSearch = searchParams.get("search") || "";

  // State
  const [data, setData] = useState<ProductListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState(initialSearch);
  const [selectedRegion, setSelectedRegion] = useState("all");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedStatus, setSelectedStatus] = useState("all");
  const [selectedSort, setSelectedSort] = useState("score_desc");
  const [currentPage, setCurrentPage] = useState(1);

  // Modal
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const pageSize = 25;

  const showFeedback = (msg: string) => {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 3500);
  };

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError(null);

    let sort_by = "created_at";
    let sort_order: "asc" | "desc" = "desc";

    if (selectedSort === "score_desc") {
      sort_by = "overall_score";
      sort_order = "desc";
    } else if (selectedSort === "score_asc") {
      sort_by = "overall_score";
      sort_order = "asc";
    } else if (selectedSort === "price_desc") {
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
        search: searchQuery.trim() ? searchQuery.trim() : undefined,
        region: selectedRegion === "all" ? undefined : selectedRegion,
        category: selectedCategory === "all" ? undefined : selectedCategory,
        status: selectedStatus === "all" ? undefined : selectedStatus,
        sort_by,
        sort_order,
      });
      setData(res);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError ? err.message : "Failed to load master products.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [
    currentPage,
    searchQuery,
    selectedRegion,
    selectedCategory,
    selectedStatus,
    selectedSort,
  ]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const handleResetFilters = () => {
    setSearchQuery("");
    setSelectedRegion("all");
    setSelectedCategory("all");
    setSelectedStatus("all");
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

  // Common categories in the database
  const knownCategories = [
    "Electronics",
    "Home & Kitchen",
    "Beauty & Grooming",
    "Fitness & Outdoor",
    "Automotive Accessories",
    "Smart Home",
  ];

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

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Product Intelligence Catalog
            </h1>
            <span className="p-1 rounded-md bg-indigo-50 text-indigo-600">
              <Package className="w-4 h-4" />
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Complete database of 315 master products, gate progress logs, and unit economics
          </p>
        </div>

        {/* Status Pills */}
        <div className="flex items-center gap-2.5 text-xs">
          <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200/80 font-medium">
            SSOT Master Catalog
          </span>
          <span className="px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 font-medium font-mono">
            {data ? `${data.total} products` : "Connecting..."}
          </span>
        </div>
      </div>

      {/* Filter and Content Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs overflow-hidden">
        {/* Filter Controls Row */}
        <div className="p-6 pb-4 border-b border-slate-100 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
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
              selectedCategory={selectedCategory}
              onCategoryChange={(c) => {
                setSelectedCategory(c);
                setCurrentPage(1);
              }}
              categories={knownCategories}
              selectedSort={selectedSort}
              onSortChange={(s) => {
                setSelectedSort(s);
                setCurrentPage(1);
              }}
              sortOptions={[
                { id: "score_desc", label: "Sort: Score (High to Low)" },
                { id: "score_asc", label: "Sort: Score (Low to High)" },
                { id: "price_desc", label: "Sort: MSRP (High to Low)" },
                { id: "price_asc", label: "Sort: MSRP (Low to High)" },
                { id: "date_desc", label: "Sort: Newest First" },
              ]}
              onReset={handleResetFilters}
              placeholder="Search product title, ID, or category..."
              className="py-0 flex-1"
            />

            {/* Quick Status Filter Pill */}
            <div className="relative">
              <select
                value={selectedStatus}
                onChange={(e) => {
                  setSelectedStatus(e.target.value);
                  setCurrentPage(1);
                }}
                aria-label="Evaluation status filter"
                className="appearance-none pl-3 pr-8 py-2 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 font-medium hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs cursor-pointer"
              >
                <option value="all">Status: All Statuses</option>
                <option value="PASS">Status: PASS (Consensus Passed)</option>
                <option value="PENDING">Status: PENDING (Evaluating)</option>
              </select>
              <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">
                ▼
              </span>
            </div>
          </div>
        </div>

        {/* Table Content */}
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
              <ErrorState message={error} onRetry={fetchProducts} />
            </div>
          ) : !data || data.items.length === 0 ? (
            <div className="p-8">
              <EmptyState
                title="No products found"
                description="No products matched your active catalog filters. Try resetting the filters or clearing your search query."
                actionLabel="Reset filters"
                onAction={handleResetFilters}
              />
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/90 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-6">Product Information</th>
                  <th className="py-3 px-4">Region</th>
                  <th className="py-3 px-4">Planned MSRP</th>
                  <th className="py-3 px-4">Landed COGS</th>
                  <th className="py-3 px-4">Gross Margin</th>
                  <th className="py-3 px-4">Gates Passed</th>
                  <th className="py-3 px-4">Overall Score</th>
                  <th className="py-3 px-6 text-right">Dossier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((prod: ProductSummary) => {
                  const isVerified = prod.status === "PASS";

                  return (
                    <tr
                      key={prod.product_id}
                      className="hover:bg-slate-50/70 transition-colors group cursor-pointer"
                      onClick={() => setSelectedProductId(prod.product_id)}
                    >
                      {/* Name & Identity */}
                      <td className="py-3.5 px-6">
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              showFeedback("Shortlist mutation API (POST /products/{id}/shortlist) is pending backend release.");
                            }}
                            title="Shortlist"
                            className="text-slate-300 hover:text-amber-500 transition-colors"
                          >
                            <Star
                              className={`w-4 h-4 ${
                                prod.is_shortlisted ? "fill-amber-400 text-amber-500" : ""
                              }`}
                            />
                          </button>

                          <div className="w-8 h-8 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 font-semibold text-xs shrink-0">
                            {prod.name.charAt(0)}
                          </div>

                          <div className="max-w-md">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-1">
                                {prod.name}
                              </span>
                              {isVerified && (
                                <span className="px-1.5 py-0.2 rounded text-[10px] bg-emerald-50 text-emerald-700 font-semibold shrink-0">
                                  Verified
                                </span>
                              )}
                            </div>
                            <span className="block text-[11px] text-slate-400 line-clamp-1">
                              ID: {prod.product_id} • {prod.category || "General"}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Region */}
                      <td className="py-3.5 px-4 text-slate-700 font-medium">
                        {prod.region || "India"}
                      </td>

                      {/* Planned MSRP */}
                      <td className="py-3.5 px-4 font-semibold text-slate-900 font-mono">
                        {formatCurrency(prod.planned_msrp)}
                      </td>

                      {/* Landed COGS */}
                      <td className="py-3.5 px-4 text-slate-600 font-mono">
                        {formatCurrency(prod.landed_cogs)}
                      </td>

                      {/* Gross Margin */}
                      <td className="py-3.5 px-4">
                        {prod.gross_margin_pct && prod.gross_margin_pct > 0 ? (
                          <span className="font-semibold text-emerald-600 font-mono">
                            {prod.gross_margin_pct.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-slate-400 font-mono">-</span>
                        )}
                      </td>

                      {/* Gates Progress */}
                      <td className="py-3.5 px-4">
                        <GateBadge
                          passed={prod.gates_passed}
                          total={6}
                          status={prod.status}
                        />
                      </td>

                      {/* Overall Score */}
                      <td className="py-3.5 px-4">
                        <ScoreBadge score={prod.overall_score} size="md" />
                      </td>

                      {/* Action */}
                      <td className="py-3.5 px-6 text-right">
                        <Button
                          variant="primary"
                          size="xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedProductId(prod.product_id);
                          }}
                          className="bg-indigo-600 hover:bg-indigo-700"
                        >
                          View Dossier
                        </Button>
                      </td>
                    </tr>
                  );
                })}
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
              note="Authoritative product records from SQLite SSOT"
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

export default function ProductsPage() {
  return (
    <React.Suspense
      fallback={
        <div className="p-8 space-y-4">
          <div className="h-20 bg-slate-100 rounded-xl animate-pulse" />
          <div className="h-64 bg-slate-50 rounded-xl animate-pulse" />
        </div>
      }
    >
      <ProductsCatalogContent />
    </React.Suspense>
  );
}

