"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, TrendingUp } from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import { TrendItem, TrendListResponse } from "@/types/api";
import { PlatformFilterBar } from "@/components/common/PlatformFilterBar";
import { FilterBar } from "@/components/common/FilterBar";
import { Pagination } from "@/components/common/Pagination";
import { ScoreBadge } from "@/components/common/ScoreBadge";
import { MarketplaceBadge } from "@/components/common/MarketplaceBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Button } from "@/components/ui/Button";

export default function TrendsPage() {
  const router = useRouter();

  // State
  const [data, setData] = useState<TrendListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedSource, setSelectedSource] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRegion, setSelectedRegion] = useState("all");
  const [selectedSort, setSelectedSort] = useState("score_desc");
  const [currentPage, setCurrentPage] = useState(1);
  const [activeTab, setActiveTab] = useState<"active" | "archived">("active");
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const pageSize = 25;

  const showFeedback = (msg: string) => {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 3500);
  };

  const fetchTrends = useCallback(async () => {
    setLoading(true);
    setError(null);

    // Map selected sort
    let sort_by = "velocity_score";
    let sort_order: "asc" | "desc" = "desc";
    if (selectedSort === "date_desc") {
      sort_by = "created_at";
      sort_order = "desc";
    } else if (selectedSort === "volume_desc") {
      sort_by = "search_volume_est";
      sort_order = "desc";
    } else if (selectedSort === "score_asc") {
      sort_by = "velocity_score";
      sort_order = "asc";
    }

    try {
      const res = await api.getTrends({
        page: currentPage,
        pageSize,
        platform: selectedSource === "all" ? undefined : selectedSource,
        region: selectedRegion === "all" ? undefined : selectedRegion,
        search: searchQuery.trim() ? searchQuery.trim() : undefined,
        status: activeTab === "active" ? "ACTIVE" : "ARCHIVED",
        sort_by,
        sort_order,
      });
      setData(res);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError ? err.message : "Failed to load trend signals.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [currentPage, selectedSource, selectedRegion, searchQuery, activeTab, selectedSort]);

  useEffect(() => {
    fetchTrends();
  }, [fetchTrends]);

  const handleResetFilters = () => {
    setSelectedSource("all");
    setSearchQuery("");
    setSelectedRegion("all");
    setSelectedSort("score_desc");
    setCurrentPage(1);
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

  const formatSearchVolume = (vol?: string | null) => {
    if (!vol) return "-";
    const num = parseInt(vol, 10);
    if (isNaN(num)) return vol;
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
    return num.toLocaleString();
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
              E-com Trend
            </h1>
            <span className="p-1 rounded-md bg-indigo-50 text-indigo-600">
              <TrendingUp className="w-4 h-4" />
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Trending product signals discovered across connected e-commerce platforms
          </p>
        </div>

        {/* Top Right Status Indicators */}
        <div className="flex items-center gap-2.5 text-xs">
          <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200/80 font-medium">
            Logic: platform best-seller rank movement
          </span>
          <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Live SSOT Sync
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

        {/* Tabs: Active vs Archived */}
        <div className="px-6 flex items-center gap-6 border-b border-slate-200 text-xs font-semibold">
          <button
            type="button"
            onClick={() => {
              setActiveTab("active");
              setCurrentPage(1);
            }}
            className={`py-3 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "active"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Trending products
            {data && activeTab === "active" && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-50 text-indigo-700 font-mono">
                {data.total}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab("archived");
              setCurrentPage(1);
            }}
            className={`py-3 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "archived"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Out of trending products
            {data && activeTab === "archived" && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-100 text-slate-600 font-mono">
                {data.total}
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
              { id: "score_desc", label: "Sort: Trend score (High to Low)" },
              { id: "score_asc", label: "Sort: Trend score (Low to High)" },
              { id: "date_desc", label: "Sort: Newest detected" },
              { id: "volume_desc", label: "Sort: Est. Search Volume" },
            ]}
            onReset={handleResetFilters}
            placeholder="Search keywords or niche..."
          />
        </div>

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
              <ErrorState message={error} onRetry={fetchTrends} />
            </div>
          ) : !data || data.items.length === 0 ? (
            <div className="p-8">
              <EmptyState
                title="No trend signals found"
                description="No signals matched your current filters. Try selecting 'All sources' or clearing the search query."
                actionLabel="Reset filters"
                onAction={handleResetFilters}
              />
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/90 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-6">Product / Keyword</th>
                  <th className="py-3 px-4">Source</th>
                  <th className="py-3 px-4">Region</th>
                  <th className="py-3 px-4">Category / Niche</th>
                  <th className="py-3 px-4">Volume Est.</th>
                  <th className="py-3 px-4">Discovered</th>
                  <th className="py-3 px-4">Score</th>
                  <th className="py-3 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((item: TrendItem, idx: number) => (
                  <tr
                    key={item.signal_id || idx}
                    className="hover:bg-slate-50/70 transition-colors group"
                  >
                    {/* Keyword / Name */}
                    <td className="py-3.5 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-semibold shrink-0">
                          <Sparkles className="w-4 h-4" />
                        </div>
                        <div>
                          <span className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors capitalize">
                            {item.keyword}
                          </span>
                          <span className="block text-[11px] text-slate-400">
                            Signal #{item.signal_id || "-"}
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Source */}
                    <td className="py-3.5 px-4">
                      <MarketplaceBadge source={item.source} />
                    </td>

                    {/* Region */}
                    <td className="py-3.5 px-4 text-slate-600 font-medium">
                      {item.region || "Global"}
                    </td>

                    {/* Trend type / category */}
                    <td className="py-3.5 px-4 text-slate-600">
                      {item.trend_type || "General E-Com"}
                    </td>

                    {/* Search Volume Indicator */}
                    <td className="py-3.5 px-4 text-slate-700 font-mono">
                      {formatSearchVolume(item.search_volume_indicator)}
                    </td>

                    {/* Discovered */}
                    <td className="py-3.5 px-4 text-slate-500">
                      {formatDate(item.first_detected_at)}
                    </td>

                    {/* Score */}
                    <td className="py-3.5 px-4">
                      <ScoreBadge score={item.velocity_score} size="md" />
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-6 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <Button
                          variant="primary"
                          size="xs"
                          onClick={() => {
                            router.push(`/products?search=${encodeURIComponent(item.keyword)}`);
                          }}
                          className="bg-indigo-600 hover:bg-indigo-700"
                        >
                          Find Products
                        </Button>
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={() =>
                            showFeedback("Archive signal mutation API (PATCH /trends/{id}) is scheduled for future release.")
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
              note="Remove moves a product to 'Out of trending' - nothing is deleted permanently"
            />
          </div>
        )}
      </div>
    </div>
  );
}
