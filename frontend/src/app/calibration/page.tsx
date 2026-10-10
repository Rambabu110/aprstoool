"use client";

import React, { useState, useEffect } from "react";
import {
  Sliders,
  RotateCw,
  Scale,
  Brain,
  Info,
  LineChart,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { PortfolioCalibrationSummary } from "@/types/api";
import { ErrorState } from "@/components/common/ErrorState";

export default function CalibrationPage() {
  const [data, setData] = useState<PortfolioCalibrationSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadCalibration() {
      setLoading(true);
      setError(null);
      try {
        const res = await apiClient.getCalibrationSummary();
        setData(res);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load calibration data");
      } finally {
        setLoading(false);
      }
    }
    loadCalibration();
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center space-y-4">
        <RotateCw className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500">Loading AI Calibration & Learning Engine...</p>
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
              AI Model Calibration & Closed-Loop Learning
            </h1>
            <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 ring-1 ring-inset ring-blue-600/20">
              <Brain className="mr-1 h-3.5 w-3.5" />
              Statistical Governance
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Evaluating prediction accuracy residuals (MBE, MAE, MAPE) and Bayesian calibration against real market outcomes.
          </p>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 shadow-sm"
        >
          <RotateCw className="h-3.5 w-3.5" />
          <span>Refresh Metrics</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Frozen Decisions</span>
          <p className="mt-2 text-2xl font-bold text-slate-900">{data?.total_decisions ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">In decision_ledger table</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Observed Outcomes</span>
          <p className="mt-2 text-2xl font-bold text-indigo-600">{data?.total_outcomes ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Ground-truth validation points</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Calibration Reliability</span>
          <p className="mt-2 text-lg font-bold text-amber-600">{data?.calibration_reliability ?? "PENDING"}</p>
          <p className="mt-1 text-xs text-slate-500">Sample size: {data?.sample_size ?? 0}</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Awaiting Observation</span>
          <p className="mt-2 text-2xl font-bold text-emerald-600">{data?.products_awaiting_observation ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Decision maturity window</p>
        </div>
      </div>

      {/* Readiness Report Banner */}
      <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-5 shadow-sm">
        <div className="flex items-start space-x-3">
          <Info className="h-5 w-5 text-amber-600 mt-0.5" />
          <div>
            <h3 className="text-sm font-bold text-amber-900">Calibration Readiness Assessment</h3>
            <p className="mt-1 text-xs text-amber-800 leading-relaxed">
              Model calibration requires ground-truth commercial outcomes to compute statistical residuals (MBE, MAE, MAPE).
              Currently {data?.total_decisions ?? 1} decision is frozen in SQLite with {data?.total_outcomes ?? 0} observed commercial outcomes,
              meaning models maintain baseline prior weights until ground-truth maturity thresholds are met.
            </p>
          </div>
        </div>
      </div>

      {/* Error Metrics Tracking Grid */}
      <div>
        <h3 className="text-base font-semibold text-slate-900 mb-3 flex items-center gap-2">
          <Scale className="h-5 w-5 text-indigo-600" />
          Statistical Residual Metrics (Prediction vs Reality)
        </h3>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h4 className="text-sm font-bold text-slate-900">Demand Bias (MBE)</h4>
              <LineChart className="h-4 w-4 text-slate-400" />
            </div>
            <p className="mt-1 text-[11px] text-slate-500">Mean Bias Error in unit velocity</p>
            <p className="mt-3 text-2xl font-bold text-slate-900">
              {data?.demand_bias_mbe != null ? data.demand_bias_mbe.toFixed(2) : "N/A"}
            </p>
            <span className="text-[11px] text-slate-400">Sample size: {data?.sample_size ?? 0}</span>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h4 className="text-sm font-bold text-slate-900">Demand MAE</h4>
              <LineChart className="h-4 w-4 text-slate-400" />
            </div>
            <p className="mt-1 text-[11px] text-slate-500">Mean Absolute Error in sales volume</p>
            <p className="mt-3 text-2xl font-bold text-slate-900">
              {data?.demand_mae != null ? data.demand_mae.toFixed(2) : "N/A"}
            </p>
            <span className="text-[11px] text-slate-400">Sample size: {data?.sample_size ?? 0}</span>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h4 className="text-sm font-bold text-slate-900">Demand MAPE %</h4>
              <LineChart className="h-4 w-4 text-slate-400" />
            </div>
            <p className="mt-1 text-[11px] text-slate-500">Percentage error on sales volume</p>
            <p className="mt-3 text-2xl font-bold text-slate-900">
              {data?.demand_mape != null ? `${data.demand_mape.toFixed(1)}%` : "N/A"}
            </p>
            <span className="text-[11px] text-slate-400">Sample size: {data?.sample_size ?? 0}</span>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h4 className="text-sm font-bold text-slate-900">Price Bias (MBE)</h4>
              <LineChart className="h-4 w-4 text-slate-400" />
            </div>
            <p className="mt-1 text-[11px] text-slate-500">Mean Bias Error in realized selling price</p>
            <p className="mt-3 text-2xl font-bold text-slate-900">
              {data?.price_bias_mbe != null ? `$${data.price_bias_mbe.toFixed(2)}` : "N/A"}
            </p>
            <span className="text-[11px] text-slate-400">Sample size: {data?.sample_size ?? 0}</span>
          </div>
        </div>
      </div>

      {/* Model Governance Specification */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
          <Sliders className="h-5 w-5 text-indigo-600" />
          Model Governance & Tuning Parameters
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          Parameters are held in core.governance and enforced across all product evaluations.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3 text-xs">
          <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
            <span className="text-slate-500 font-medium">Scoring Engine</span>
            <p className="mt-1 text-sm font-bold text-slate-900">V7.2 Heuristic Trend & Unit Economics</p>
            <p className="mt-1 text-[11px] text-slate-500">10-dimensional scoring with deterministic penalty triggers</p>
          </div>

          <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
            <span className="text-slate-500 font-medium">Re-Calibration Trigger Threshold</span>
            <p className="mt-1 text-sm font-bold text-slate-900">N &ge; 10 Ground-Truth Points</p>
            <p className="mt-1 text-[11px] text-slate-500">Prevents statistical overfitting on sparse observation data</p>
          </div>

          <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
            <span className="text-slate-500 font-medium">Bayesian Prior Confidence</span>
            <p className="mt-1 text-sm font-bold text-slate-900">80.0% Minimum Confidence Gate</p>
            <p className="mt-1 text-[11px] text-slate-500">Gate 3 requirement before launchpad promotion</p>
          </div>
        </div>
      </div>
    </div>
  );
}
