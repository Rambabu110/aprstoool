"use client";

import React, { useState, useEffect } from "react";
import {
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  Play,
  Layers,
  FileCheck,
  Calculator,
  Shield,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import {
  OutcomesListResponse,
  OutcomeSchemaResponse,
  OutcomeValidationResponse,
} from "@/types/api";
import { ErrorState } from "@/components/common/ErrorState";

export default function OutcomeIngestionPage() {
  const [activeTab, setActiveTab] = useState<"records" | "validator" | "schema">("records");
  
  // Data states
  const [outcomes, setOutcomes] = useState<OutcomesListResponse | null>(null);
  const [schema, setSchema] = useState<OutcomeSchemaResponse | null>(null);
  
  // Dry run form state
  const [formProductId, setFormProductId] = useState<string>("US_B09ABC");
  const [formWindowDays, setFormWindowDays] = useState<number>(30);
  const [formUnits, setFormUnits] = useState<string>("2100");
  const [formRevenue, setFormRevenue] = useState<string>("83979");
  const [formAdSpend, setFormAdSpend] = useState<string>("16800");
  const [formCogs, setFormCogs] = useState<string>("24360");
  
  const [validationResult, setValidationResult] = useState<OutcomeValidationResponse | null>(null);
  const [validating, setValidating] = useState<boolean>(false);
  const [ingesting, setIngesting] = useState<boolean>(false);
  const [ingestFeedback, setIngestFeedback] = useState<string | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [outRes, schRes] = await Promise.all([
          apiClient.getOutcomesList(),
          apiClient.getOutcomeSchema(),
        ]);
        setOutcomes(outRes);
        setSchema(schRes);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load outcomes data");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleValidate = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidating(true);
    try {
      const payload = {
        product_id: formProductId,
        window_days: formWindowDays,
        actual_units_sold: parseFloat(formUnits) || 0,
        actual_revenue: parseFloat(formRevenue) || 0,
        ad_spend: parseFloat(formAdSpend) || 0,
        actual_cogs: parseFloat(formCogs) || 0,
      };
      const res = await apiClient.validateOutcome(payload);
      setValidationResult(res);
    } catch (err: unknown) {
      alert(`Validation failed: ${err instanceof Error ? err.message : "Network error"}`);
    } finally {
      setValidating(false);
    }
  };

  const handleCommit = async () => {
    if (!validationResult?.is_valid || ingesting) return;
    setIngesting(true);
    setIngestFeedback(null);
    try {
      const payload = {
        product_id: formProductId,
        window_days: formWindowDays,
        actual_units_sold: parseFloat(formUnits) || 0,
        actual_revenue: parseFloat(formRevenue) || 0,
        ad_spend: parseFloat(formAdSpend) || 0,
        actual_cogs: parseFloat(formCogs) || 0,
      };
      const res = await apiClient.ingestOutcome(payload);
      setIngestFeedback(`Successfully ingested outcome #${res.outcome_id ?? ""}! Status: ${res.status || "INGESTED"}`);
      const outRes = await apiClient.getOutcomesList();
      setOutcomes(outRes);
    } catch (err: unknown) {
      setIngestFeedback(`Ingestion failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setIngesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center space-y-4">
        <RotateCw className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500">Loading Ground-Truth Outcome Engine...</p>
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
              Ground-Truth Outcome Ingestion & Validation
            </h1>
            <span className="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-600/20">
              <Shield className="mr-1 h-3 w-3" />
              Contract-Protected
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Ingest and validate real-world commercial performance data to evaluate prediction residuals and calibrate AI engines.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-700 shadow-sm">
            Schema Version: <strong className="text-slate-900">{schema?.schema_version || "V8.1"}</strong>
          </span>
          <span className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-700 shadow-sm">
            Observed Ground-Truth: <strong className="text-slate-900">{outcomes?.total ?? 0} records</strong>
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab("records")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "records"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <FileSpreadsheet className="h-4 w-4" />
            <span>Observed Market Outcomes ({outcomes?.total ?? 0})</span>
          </button>
          <button
            onClick={() => setActiveTab("validator")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "validator"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Calculator className="h-4 w-4" />
            <span>Dry-Run Metric Derivation Validator</span>
          </button>
          <button
            onClick={() => setActiveTab("schema")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "schema"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <FileCheck className="h-4 w-4" />
            <span>Ingestion Schema Specification</span>
          </button>
        </nav>
      </div>

      {/* TAB 1: OBSERVED RECORDS */}
      {activeTab === "records" && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-slate-200 px-6 py-4 flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-900">Recorded Ground-Truth Outcomes</h3>
              <p className="text-xs text-slate-500">Live authoritative records from product_outcomes table</p>
            </div>
            <span className="text-xs text-slate-500">
              Windows Supported: {schema?.supported_windows.join("d, ")}d
            </span>
          </div>

          {outcomes && outcomes.outcomes.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3 font-semibold">Outcome ID</th>
                    <th className="px-6 py-3 font-semibold">Product ID</th>
                    <th className="px-6 py-3 font-semibold">Observed Date</th>
                    <th className="px-6 py-3 font-semibold">Window</th>
                    <th className="px-6 py-3 font-semibold text-right">Units Sold</th>
                    <th className="px-6 py-3 font-semibold text-right">Revenue</th>
                    <th className="px-6 py-3 font-semibold text-right">Actual CAC</th>
                    <th className="px-6 py-3 font-semibold text-right">Actual CM %</th>
                    <th className="px-6 py-3 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {outcomes.outcomes.map((o) => (
                    <tr key={o.outcome_id} className="hover:bg-slate-50">
                      <td className="px-6 py-4 font-mono font-medium text-slate-900">{o.outcome_id}</td>
                      <td className="px-6 py-4 font-mono font-bold text-indigo-700">{o.product_id}</td>
                      <td className="px-6 py-4 text-slate-700">{o.observation_date}</td>
                      <td className="px-6 py-4 font-medium text-slate-800">{o.window_days} days</td>
                      <td className="px-6 py-4 text-right font-medium text-slate-900">
                        {o.actual_units_sold != null ? o.actual_units_sold.toLocaleString() : "—"}
                      </td>
                      <td className="px-6 py-4 text-right font-medium text-emerald-700">
                        {o.actual_revenue != null ? `$${o.actual_revenue.toLocaleString()}` : "—"}
                      </td>
                      <td className="px-6 py-4 text-right text-slate-700">
                        {o.actual_cac != null ? `$${o.actual_cac.toFixed(2)}` : "—"}
                      </td>
                      <td className="px-6 py-4 text-right font-bold text-slate-900">
                        {o.actual_cm_pct != null ? `${o.actual_cm_pct.toFixed(1)}%` : "—"}
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
                          {o.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-12 text-center text-slate-500">
              <FileSpreadsheet className="mx-auto h-10 w-10 text-slate-400 mb-2" />
              <p className="text-sm font-medium text-slate-800">Zero Commercial Outcomes Ingested</p>
              <p className="mt-1 text-xs text-slate-500">
                The authoritative production database contains zero synthetic outcome rows.
                Use the pre-ingestion validator tab to dry-run metric derivation.
              </p>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: DRY RUN VALIDATOR */}
      {activeTab === "validator" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Form */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Calculator className="h-5 w-5 text-blue-600" />
              Dry-Run Metric Derivation
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Tests input validation rules and calculates daily sales velocity, real CAC, and CM% via backend core.outcomes logic without mutating the database.
            </p>

            <form onSubmit={handleValidate} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700">Product ID</label>
                <input
                  type="text"
                  value={formProductId}
                  onChange={(e) => setFormProductId(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">Observation Window (Days)</label>
                <select
                  value={formWindowDays}
                  onChange={(e) => setFormWindowDays(parseInt(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                >
                  <option value={7}>7 Days (T+7)</option>
                  <option value={14}>14 Days (T+14)</option>
                  <option value={30}>30 Days (T+30)</option>
                  <option value={60}>60 Days (T+60)</option>
                  <option value={90}>90 Days (T+90)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700">Actual Units Sold</label>
                  <input
                    type="number"
                    value={formUnits}
                    onChange={(e) => setFormUnits(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700">Actual Revenue ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formRevenue}
                    onChange={(e) => setFormRevenue(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700">Ad Spend / Marketing ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formAdSpend}
                    onChange={(e) => setFormAdSpend(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700">Total Landed COGS ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formCogs}
                    onChange={(e) => setFormCogs(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={validating}
                className="w-full inline-flex items-center justify-center space-x-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {validating ? <RotateCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                <span>Run Safe Pre-Ingestion Validation</span>
              </button>
            </form>
          </div>

          {/* Validation Results Card */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
                <FileCheck className="h-5 w-5 text-indigo-600" />
                Validation & Derivation Output
              </h3>

              {validationResult ? (
                <div className="mt-4 space-y-4">
                  <div
                    className={`flex items-center space-x-2 rounded-lg p-3 text-sm ${
                      validationResult.is_valid
                        ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                        : "bg-red-50 text-red-800 border border-red-200"
                    }`}
                  >
                    {validationResult.is_valid ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="h-5 w-5 text-red-600" />
                    )}
                    <span className="font-semibold">
                      {validationResult.is_valid
                        ? "Payload Conforms to V8 Schema Contract"
                        : "Validation Rejection Detected"}
                    </span>
                  </div>

                  {validationResult.errors.length > 0 && (
                    <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">
                      <strong>Schema Errors:</strong>
                      <ul className="mt-1 list-disc pl-4">
                        {validationResult.errors.map((err, i) => (
                          <li key={i}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {validationResult.derived_metrics && (
                    <div className="space-y-3">
                      <p className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                        Derived Economic Ground-Truth
                      </p>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                          <span className="text-[11px] text-slate-500">Observed Daily Units</span>
                          <p className="text-base font-bold text-slate-900">
                            {Number(validationResult.derived_metrics.daily_units).toFixed(1)} / day
                          </p>
                        </div>
                        <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                          <span className="text-[11px] text-slate-500">Realized Selling Price</span>
                          <p className="text-base font-bold text-slate-900">
                            ${Number(validationResult.derived_metrics.selling_price).toFixed(2)}
                          </p>
                        </div>
                        <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                          <span className="text-[11px] text-slate-500">Calculated CAC</span>
                          <p className="text-base font-bold text-slate-900">
                            ${Number(validationResult.derived_metrics.cac).toFixed(2)}
                          </p>
                        </div>
                        <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                          <span className="text-[11px] text-slate-500">Contribution Margin (CM)</span>
                          <p className="text-base font-bold text-emerald-600">
                            {Number(validationResult.derived_metrics.cm_pct).toFixed(1)}%
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {validationResult.is_valid && (
                    <div className="pt-3 border-t border-slate-100 space-y-2">
                      <button
                        type="button"
                        onClick={handleCommit}
                        disabled={ingesting}
                        className="w-full inline-flex items-center justify-center space-x-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors shadow-2xs"
                      >
                        {ingesting ? <RotateCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                        <span>{ingesting ? "Ingesting to SQLite..." : "Commit Verified Outcome to SSOT"}</span>
                      </button>
                      {ingestFeedback && (
                        <p className="text-xs text-center font-medium text-emerald-800 bg-emerald-50 p-2.5 rounded-lg border border-emerald-200">
                          {ingestFeedback}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="mt-12 text-center text-slate-400">
                  <Calculator className="mx-auto h-10 w-10 mb-2 opacity-50" />
                  <p className="text-sm">Submit the validation form to run the dry-run derivation engine.</p>
                </div>
              )}
            </div>

            <div className="mt-6 rounded-lg bg-amber-50 p-3 text-xs text-amber-800 border border-amber-200">
              <span className="font-semibold">Zero DB Mutation Notice:</span> This validation executes fully in-memory via existing APRS logic. No rows are written to SQLite.
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: SCHEMA CONTRACT */}
      {activeTab === "schema" && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-6">
          <div>
            <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Layers className="h-5 w-5 text-indigo-600" />
              Outcome Schema Definition ({schema?.schema_version})
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Standard contract for batch CSV or programmatic ground-truth feedback.
            </p>
          </div>

          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-[11px] font-semibold text-slate-700 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-2.5">Field Name</th>
                  <th className="px-4 py-2.5">Type</th>
                  <th className="px-4 py-2.5">Requirement</th>
                  <th className="px-4 py-2.5">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {schema?.rules.map((r) => (
                  <tr key={r.field_name} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 font-bold text-slate-900">{r.field_name}</td>
                    <td className="px-4 py-2.5 text-indigo-700">{r.field_type}</td>
                    <td className="px-4 py-2.5 font-sans">
                      {r.required ? (
                        <span className="rounded bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-700">
                          REQUIRED
                        </span>
                      ) : (
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                          OPTIONAL
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 font-sans text-slate-700">{r.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
