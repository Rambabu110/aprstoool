"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Calculator,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import { EconomicsResponse, ScenarioDetail } from "@/types/api";
import { Button } from "@/components/ui/Button";

const VERIFIED_SAMPLE_PRODUCTS = [
  { id: "IN_B08KLT", label: "Solid Brass Safety Razor (IN)" },
  { id: "GC_B0AD01", label: "Smart Electric Bakhoor (GCC)" },
  { id: "US_B08XYZ", label: "MagSafe 15W Qi2 Mount (US)" },
  { id: "IN_B0GMJH", label: "2-Tier Under Sink Storage (IN)" },
  { id: "UK_B0UK01", label: "Over-Sink Dish Drying Rack (UK)" },
  { id: "US_B09ABC", label: "Ultrasonic Cleaning Pod (US)" },
];

export default function EconomicsPage() {
  const [selectedProductId, setSelectedProductId] = useState<string>("IN_B08KLT");
  const [customIdInput, setCustomIdInput] = useState<string>("");
  const [data, setData] = useState<EconomicsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Optional simulation overrides
  const [simMsrp, setSimMsrp] = useState<string>("");
  const [simFob, setSimFob] = useState<string>("");

  const fetchEconomics = useCallback(
    async (productId: string, overrideMsrp?: number, overrideFob?: number) => {
      setLoading(true);
      setError(null);

      try {
        const res = await api.getEconomics(productId, {
          plannedMsrp: overrideMsrp,
          fobPrice: overrideFob,
        });
        setData(res);
      } catch (err: unknown) {
        const msg =
          err instanceof ApiClientError ? err.message : "Failed to load unit economics.";
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchEconomics(selectedProductId);
    setSimMsrp("");
    setSimFob("");
  }, [selectedProductId, fetchEconomics]);

  const handleSimulate = (e: React.FormEvent) => {
    e.preventDefault();
    const msrpNum = simMsrp ? parseFloat(simMsrp) : undefined;
    const fobNum = simFob ? parseFloat(simFob) : undefined;
    fetchEconomics(selectedProductId, msrpNum, fobNum);
  };

  const handleResetSimulation = () => {
    setSimMsrp("");
    setSimFob("");
    fetchEconomics(selectedProductId);
  };

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customIdInput.trim()) {
      setSelectedProductId(customIdInput.trim());
      setCustomIdInput("");
    }
  };

  const formatCurrency = (val?: number | null, curr: string = "INR") => {
    if (val === undefined || val === null) return "-";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: curr === "INR" ? "INR" : curr === "USD" ? "USD" : "INR",
      maximumFractionDigits: 1,
    }).format(val);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              15-Factor Unit Economics
            </h1>
            <span className="p-1 rounded-md bg-indigo-50 text-indigo-600">
              <Calculator className="w-4 h-4" />
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Authoritative Python Comprehensive15FactorEconomics financial modeling across 3 risk scenarios
          </p>
        </div>

        <div className="flex items-center gap-2.5 text-xs">
          <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200/80 font-medium">
            Python Engine Calculation
          </span>
          {data && (
            <span
              className={`px-2.5 py-1 rounded-full font-bold border ${
                data.is_financially_viable
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-rose-50 text-rose-700 border-rose-200"
              }`}
            >
              Recommendation: {data.recommendation}
            </span>
          )}
        </div>
      </div>

      {/* Product Selector Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-2">
            Select Product:
          </span>
          {VERIFIED_SAMPLE_PRODUCTS.map((p) => {
            const isSelected = selectedProductId === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedProductId(p.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  isSelected
                    ? "bg-indigo-600 text-white font-semibold shadow-xs"
                    : "bg-slate-50 border border-slate-200 text-slate-700 hover:bg-slate-100"
                }`}
              >
                {p.label}
              </button>
            );
          })}
        </div>

        {/* Custom Product ID input */}
        <form onSubmit={handleCustomSubmit} className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Custom Product ID..."
            value={customIdInput}
            onChange={(e) => setCustomIdInput(e.target.value)}
            className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
          <button
            type="submit"
            className="px-3 py-1.5 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg border border-slate-200"
          >
            Load
          </button>
        </form>
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="bg-white p-12 rounded-xl border border-slate-200 flex flex-col items-center justify-center text-slate-500 gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
          <span className="text-sm">Calculating 15-factor economics in Python backend...</span>
        </div>
      ) : error ? (
        <div className="bg-rose-50 p-6 rounded-xl border border-rose-200 text-rose-700 text-sm">
          {error}
        </div>
      ) : data ? (
        <div className="space-y-5">
          {/* Top Level Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-xs text-slate-500 font-medium">Financial Viability</span>
              <div className="flex items-center gap-2 mt-1">
                {data.is_financially_viable ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-rose-600" />
                )}
                <span className="text-lg font-bold text-slate-900">
                  {data.is_financially_viable ? "VIABLE" : "UNVIABLE"}
                </span>
              </div>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-xs text-slate-500 font-medium">Composite Score</span>
              <div className="text-lg font-bold text-indigo-600 mt-1 font-mono">
                {data.composite_score.toFixed(1)} / 100
              </div>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-xs text-slate-500 font-medium">Lead Time Risk Factor</span>
              <div className="text-lg font-bold text-slate-800 mt-1 font-mono">
                {data.lead_time_risk_factor.toFixed(2)}x
                <span className="text-xs font-normal text-slate-500 ml-1">
                  ({data.lead_time_days} days)
                </span>
              </div>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-xs text-slate-500 font-medium">Trend Half-Life</span>
              <div className="text-lg font-bold text-slate-800 mt-1 font-mono">
                {data.trend_half_life_days} days
              </div>
            </div>
          </div>

          {/* 3 Risk Scenarios Comparison Cards */}
          <div>
            <h2 className="text-sm font-bold text-slate-900 mb-3 uppercase tracking-wider">
              3-Scenario Stress Test Matrix
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {data.scenarios.map((sc: ScenarioDetail, idx: number) => {
                const isConservative = sc.scenario_name.toLowerCase().includes("conservative");
                const isUpside = sc.scenario_name.toLowerCase().includes("upside");
                const isExpected = !isConservative && !isUpside;

                let cardHeaderBg = "bg-slate-50 border-slate-200";
                let badgeColor = "bg-slate-100 text-slate-700";
                if (isConservative) {
                  cardHeaderBg = "bg-amber-50/60 border-amber-200";
                  badgeColor = "bg-amber-100 text-amber-800";
                } else if (isExpected) {
                  cardHeaderBg = "bg-indigo-50/60 border-indigo-200";
                  badgeColor = "bg-indigo-100 text-indigo-800";
                } else if (isUpside) {
                  cardHeaderBg = "bg-emerald-50/60 border-emerald-200";
                  badgeColor = "bg-emerald-100 text-emerald-800";
                }

                return (
                  <div
                    key={idx}
                    className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col justify-between"
                  >
                    {/* Scenario Header */}
                    <div className={`p-4 border-b ${cardHeaderBg} flex items-center justify-between`}>
                      <div>
                        <h3 className="font-bold text-slate-900 text-sm">
                          {sc.scenario_name}
                        </h3>
                        <span className="text-[11px] text-slate-500">
                          {isConservative
                            ? "High CAC / Stress margins"
                            : isExpected
                            ? "Baseline operational expectations"
                            : "Optimal sales & bulk volume"}
                        </span>
                      </div>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${badgeColor}`}>
                        {sc.status}
                      </span>
                    </div>

                    {/* Scenario Financial Metrics */}
                    <div className="p-5 space-y-3.5 text-xs">
                      <div className="flex justify-between items-center py-1 border-b border-slate-50">
                        <span className="text-slate-500">Planned MSRP:</span>
                        <span className="font-bold text-slate-900 font-mono">
                          {formatCurrency(sc.planned_msrp, data.currency)}
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1 border-b border-slate-50">
                        <span className="text-slate-500">Factory FOB Cost:</span>
                        <span className="font-medium text-slate-700 font-mono">
                          {formatCurrency(sc.fob_price, data.currency)}
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1 border-b border-slate-50">
                        <span className="text-slate-500">Landed COGS:</span>
                        <span className="font-medium text-slate-700 font-mono">
                          {formatCurrency(sc.landed_cogs, data.currency)}
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1 border-b border-slate-50">
                        <span className="text-slate-500">Gross Margin:</span>
                        <span className="font-bold text-emerald-600 font-mono">
                          {sc.gross_margin_pct.toFixed(1)}%
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1 border-b border-slate-50">
                        <span className="text-slate-500">Net Profit Margin:</span>
                        <span
                          className={`font-bold font-mono ${
                            sc.net_profit_pct > 15
                              ? "text-indigo-600"
                              : sc.net_profit_pct > 0
                              ? "text-slate-800"
                              : "text-rose-600"
                          }`}
                        >
                          {sc.net_profit_pct.toFixed(1)}%
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1 border-b border-slate-50">
                        <span className="text-slate-500">Stress Test Margin:</span>
                        <span
                          className={`font-semibold font-mono ${
                            sc.worst_case_stress_margin_pct > 0
                              ? "text-emerald-700"
                              : "text-rose-600"
                          }`}
                        >
                          {sc.worst_case_stress_margin_pct.toFixed(1)}%
                        </span>
                      </div>

                      <div className="flex justify-between items-center py-1">
                        <span className="text-slate-500">Break-Even Volume:</span>
                        <span className="font-bold text-slate-900 font-mono">
                          {sc.break_even_units.toLocaleString()} units
                        </span>
                      </div>
                    </div>

                    {/* Footer Viability pill */}
                    <div className="p-3 bg-slate-50 border-t border-slate-100 text-center">
                      <span
                        className={`text-xs font-semibold ${
                          sc.is_viable ? "text-emerald-700" : "text-rose-600"
                        }`}
                      >
                        {sc.is_viable ? "✓ Financed Viable" : "✗ Fails Risk Hurdle"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Interactive Dynamic Simulator Form */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Real-Time Economic Simulator
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Simulate different wholesale FOB sourcing costs and retail price points through the authoritative Python calculations.
              </p>
            </div>

            <form onSubmit={handleSimulate} className="flex flex-wrap items-center gap-4">
              <div className="flex-1 min-w-[180px]">
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Simulated Retail MSRP ({data.currency})
                </label>
                <input
                  type="number"
                  step="any"
                  placeholder={`Default: ${data.scenarios[1]?.planned_msrp || 0}`}
                  value={simMsrp}
                  onChange={(e) => setSimMsrp(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div className="flex-1 min-w-[180px]">
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Simulated Factory FOB Price ({data.currency})
                </label>
                <input
                  type="number"
                  step="any"
                  placeholder={`Default: ${data.scenarios[1]?.fob_price || 0}`}
                  value={simFob}
                  onChange={(e) => setSimFob(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div className="flex items-center gap-2 pt-5">
                <Button variant="primary" size="sm" type="submit" className="bg-indigo-600 hover:bg-indigo-700">
                  Recalculate
                </Button>
                <Button variant="outline" size="sm" type="button" onClick={handleResetSimulation}>
                  Reset
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
