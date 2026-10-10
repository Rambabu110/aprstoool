"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Scale,
  ExternalLink,
  Loader2,
  TrendingDown,
  Building2,
  Search,
  CheckCircle2,
} from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import { PriceCompareResponse, ProductSummary } from "@/types/api";

export default function PriceComparePage() {
  // Modes: "tracked" | "custom"
  const [mode, setMode] = useState<"tracked" | "custom">("tracked");

  // Tracked mode states
  const [catalogProducts, setCatalogProducts] = useState<ProductSummary[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState<boolean>(true);
  const [selectedProductId, setSelectedProductId] = useState<string>("IN_B08KLT");
  const [regionFilter, setRegionFilter] = useState<string>("all");

  // Custom search states
  const [customQuery, setCustomQuery] = useState<string>("Smart Electric Bakhoor Incense Burner USB");
  const [customRegion, setCustomRegion] = useState<string>("India");
  const [customMsrp, setCustomMsrp] = useState<number>(1299.0);

  // Comparison result states
  const [data, setData] = useState<PriceCompareResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Load catalog products for dropdown
  useEffect(() => {
    let isMounted = true;
    api
      .getProducts({ page: 1, pageSize: 100 })
      .then((res) => {
        if (isMounted) {
          setCatalogProducts(res.items);
          if (res.items.length > 0 && !res.items.some((p) => p.product_id === selectedProductId)) {
            setSelectedProductId(res.items[0].product_id);
          }
        }
      })
      .catch((err) => {
        console.error("Failed to load catalog products for price comparison:", err);
      })
      .finally(() => {
        if (isMounted) setLoadingCatalog(false);
      });

    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch comparison data
  const fetchComparison = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      let res: PriceCompareResponse;
      if (mode === "tracked") {
        res = await api.getPriceCompare({
          productId: selectedProductId,
        });
      } else {
        if (!customQuery.trim()) {
          setError("Please enter a product name or search keyword.");
          setLoading(false);
          return;
        }
        res = await api.getPriceCompare({
          query: customQuery.trim(),
          region: customRegion,
          plannedMsrp: customMsrp > 0 ? customMsrp : undefined,
        });
      }
      setData(res);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError ? err.message : "Failed to load price comparison";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [mode, selectedProductId, customQuery, customRegion, customMsrp]);

  useEffect(() => {
    fetchComparison();
  }, [fetchComparison]);

  const filteredProducts =
    regionFilter === "all"
      ? catalogProducts
      : catalogProducts.filter(
          (p) => (p.region || "").toLowerCase() === regionFilter.toLowerCase()
        );

  const formatPrice = (val: number, cur: string) => {
    return `${cur} ${val.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
  };

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              5-Platform Price Comparison &amp; Lowest Price Finder
            </h1>
            <span className="p-1 rounded-md bg-indigo-50 text-indigo-600">
              <Scale className="w-4 h-4" />
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Compare live market pricing across top 5 regional platforms, calculate arbitrage savings, and view verified factory wholesaler contacts
          </p>
        </div>

        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
          <button
            type="button"
            onClick={() => setMode("tracked")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              mode === "tracked"
                ? "bg-white text-slate-900 shadow-xs font-semibold"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Tracked Catalog Product
          </button>
          <button
            type="button"
            onClick={() => setMode("custom")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              mode === "custom"
                ? "bg-white text-slate-900 shadow-xs font-semibold"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Custom Keyword Search
          </button>
        </div>
      </div>

      {/* Control Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs space-y-3">
        {mode === "tracked" ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Filter by Region
              </label>
              <select
                value={regionFilter}
                onChange={(e) => setRegionFilter(e.target.value)}
                className="w-full text-xs rounded-lg border border-slate-200 px-3 py-2 bg-slate-50 text-slate-800 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                <option value="all">All Regions</option>
                <option value="india">India</option>
                <option value="usa">USA</option>
                <option value="gcc_middleeast">GCC / Middle East</option>
                <option value="uk">UK</option>
                <option value="europe">Europe</option>
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Select Tracked Product ({filteredProducts.length} available)
              </label>
              <select
                value={selectedProductId}
                onChange={(e) => setSelectedProductId(e.target.value)}
                disabled={loadingCatalog || filteredProducts.length === 0}
                className="w-full text-xs rounded-lg border border-slate-200 px-3 py-2 bg-slate-50 text-slate-800 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                {filteredProducts.map((p) => (
                  <option key={p.product_id} value={p.product_id}>
                    [{p.region || "IN"}] {p.name} — MSRP: {p.planned_msrp ? `₹${p.planned_msrp}` : "N/A"}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Product Name / Search Query
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={customQuery}
                  onChange={(e) => setCustomQuery(e.target.value)}
                  placeholder="e.g. Ultrasonic Cleaner Pod USB"
                  className="w-full text-xs rounded-lg border border-slate-200 pl-8 pr-3 py-2 bg-slate-50 text-slate-800 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Marketplace Region
              </label>
              <select
                value={customRegion}
                onChange={(e) => setCustomRegion(e.target.value)}
                className="w-full text-xs rounded-lg border border-slate-200 px-3 py-2 bg-slate-50 text-slate-800 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                <option value="India">India</option>
                <option value="USA">USA</option>
                <option value="GCC_MiddleEast">GCC / Middle East</option>
                <option value="UK">UK</option>
                <option value="Europe">Europe</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Benchmark MSRP
              </label>
              <input
                type="number"
                min="1"
                step="10"
                value={customMsrp}
                onChange={(e) => setCustomMsrp(parseFloat(e.target.value) || 0)}
                className="w-full text-xs rounded-lg border border-slate-200 px-3 py-2 bg-slate-50 text-slate-800 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* Comparison Content */}
      {loading ? (
        <div className="bg-white p-12 rounded-xl border border-slate-200 flex flex-col items-center justify-center text-slate-500 gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
          <span className="text-sm font-medium">Comparing prices across top 5 regional platforms...</span>
        </div>
      ) : error ? (
        <div className="bg-rose-50 p-6 rounded-xl border border-rose-200 text-rose-700 text-sm">
          {error}
        </div>
      ) : data ? (
        <div className="space-y-5">
          {/* Arbitrage Banner */}
          <div className="bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-700 p-5 rounded-2xl text-white shadow-md flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold uppercase tracking-wider mb-1">
                <TrendingDown className="w-3.5 h-3.5" />
                Arbitrage &amp; Savings Opportunity
              </div>
              <h2 className="text-xl font-bold">
                {data.product_name}
              </h2>
              <p className="text-xs text-white/80 mt-0.5">
                Benchmark: {formatPrice(data.benchmark_msrp, data.currency)} • Region: {data.region}
              </p>
            </div>

            <div className="flex items-center gap-4 bg-white/10 px-4 py-2.5 rounded-xl border border-white/20 backdrop-blur-xs">
              <div>
                <span className="text-2xs text-white/70 block uppercase font-medium">Spread Savings</span>
                <span className="text-xl font-extrabold text-white">
                  {formatPrice(data.arbitrage_savings, data.currency)}
                </span>
              </div>
              <div className="h-8 w-px bg-white/20" />
              <div>
                <span className="text-2xs text-white/70 block uppercase font-medium">Arbitrage Margin</span>
                <span className="text-xl font-extrabold text-emerald-300">
                  {data.arbitrage_pct}%
                </span>
              </div>
            </div>
          </div>

          {/* 5 Platforms Cards */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            {data.marketplaces.map((m, idx) => (
              <div
                key={idx}
                className={`p-4 rounded-xl border flex flex-col justify-between transition-all ${
                  m.is_lowest
                    ? "bg-emerald-50/50 border-emerald-300 ring-2 ring-emerald-500/20 shadow-md"
                    : "bg-white border-slate-200 hover:border-slate-300 shadow-2xs"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className="text-xs font-bold px-2 py-0.5 rounded-md"
                      style={{ backgroundColor: `${m.color}15`, color: m.color }}
                    >
                      {m.badge}
                    </span>
                    {m.is_lowest && (
                      <span className="inline-flex items-center gap-1 text-2xs font-extrabold px-1.5 py-0.5 rounded-md bg-emerald-600 text-white uppercase tracking-wider">
                        <CheckCircle2 className="w-2.5 h-2.5" /> Lowest
                      </span>
                    )}
                  </div>

                  <div className="text-xl font-extrabold text-slate-900 mt-1">
                    {formatPrice(m.price, m.currency)}
                  </div>

                  <div className="text-2xs text-slate-500 mt-1 font-medium">
                    ⚡ {m.delivery}
                  </div>

                  <p className="text-2xs text-slate-500 mt-2 line-clamp-2">
                    {m.note}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-2xs text-slate-400">
                    {m.savings_vs_highest > 0
                      ? `Save ${formatPrice(m.savings_vs_highest, m.currency)}`
                      : "Highest tier"}
                  </span>
                  <a
                    href={m.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                  >
                    View <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>

          {/* Wholesaler / Factory Card */}
          {data.wholesaler && (
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center gap-2 mb-3">
                <span className="p-1 rounded-md bg-amber-50 text-amber-700">
                  <Building2 className="w-4 h-4" />
                </span>
                <h3 className="text-sm font-bold text-slate-900">
                  Verified Factory Partner &amp; Wholesaler Sourcing Contact
                </h3>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs">
                <div>
                  <span className="text-slate-400 block font-medium">Factory / Partner</span>
                  <span className="font-semibold text-slate-800 mt-0.5 block">
                    {data.wholesaler.factory_name}
                  </span>
                  <span className="text-slate-500 text-2xs">
                    Contact: {data.wholesaler.contact_person}
                  </span>
                </div>

                <div>
                  <span className="text-slate-400 block font-medium">FOB Price &amp; MOQ</span>
                  <span className="font-semibold text-slate-800 mt-0.5 block">
                    {data.wholesaler.fob_unit_price || "Negotiated upon inquiry"}
                  </span>
                  <span className="text-slate-500 text-2xs">
                    MOQ: {data.wholesaler.moq_units ? `${data.wholesaler.moq_units} units` : "Flexible"}
                  </span>
                </div>

                <div>
                  <span className="text-slate-400 block font-medium">Sourcing Cluster / Address</span>
                  <span className="font-semibold text-slate-800 mt-0.5 block">
                    {data.wholesaler.sourcing_cluster || "Regional Export Hub"}
                  </span>
                  <span className="text-slate-500 text-2xs">
                    {data.wholesaler.contact_details}
                  </span>
                </div>

                <div className="flex flex-col justify-center gap-1">
                  {data.wholesaler.email && (
                    <span className="text-slate-700">
                      ✉️ <a href={`mailto:${data.wholesaler.email}`} className="text-indigo-600 hover:underline">{data.wholesaler.email}</a>
                    </span>
                  )}
                  {data.wholesaler.phone && (
                    <span className="text-slate-700">
                      📞 <span>{data.wholesaler.phone}</span>
                    </span>
                  )}
                  {data.wholesaler.directory_url && (
                    <a
                      href={data.wholesaler.directory_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-indigo-600 font-semibold hover:underline mt-1"
                    >
                      B2B Profile <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
