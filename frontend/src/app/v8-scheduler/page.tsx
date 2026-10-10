"use client";

import React, { useState, useEffect } from "react";
import {
  Calendar,
  Clock,
  RotateCw,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Hourglass,
  Layers,
  Activity,
  Play,
  Square,
  ShieldCheck,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import {
  DaemonStatusResponse,
  ObservationSchedulesResponse,
  ObservationJobItem,
  SchedulerRunOnceSummary,
  WorkerStatsResponse,
} from "@/types/api";
import { ErrorState } from "@/components/common/ErrorState";

export default function V8SchedulerPage() {
  const [daemon, setDaemon] = useState<DaemonStatusResponse | null>(null);
  const [schedules, setSchedules] = useState<ObservationSchedulesResponse | null>(null);
  const [obsJobs, setObsJobs] = useState<ObservationJobItem[]>([]);
  const [runnerLoading, setRunnerLoading] = useState<boolean>(false);
  const [runnerResult, setRunnerResult] = useState<SchedulerRunOnceSummary | null>(null);
  const [workerStats, setWorkerStats] = useState<WorkerStatsResponse | null>(null);
  const [workerLoading, setWorkerLoading] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);
  const [triggerFeedback, setTriggerFeedback] = useState<string | null>(null);

  const handleTriggerObserve = async (productId: string) => {
    setTriggeringId(productId);
    try {
      const res = await apiClient.triggerObservation(productId);
      const state = (res as { observation_job_state?: string }).observation_job_state || "CHECKED";
      setTriggerFeedback(`${productId}: State is ${state}`);
      setTimeout(() => setTriggerFeedback(null), 4000);
    } catch (err: unknown) {
      setTriggerFeedback(`Check failed: ${err instanceof Error ? err.message : "Error"}`);
    } finally {
      setTriggeringId(null);
    }
  };

  const handleRunJobs = async (dryRun: boolean) => {
    setRunnerLoading(true);
    setRunnerResult(null);
    try {
      const res = await apiClient.runDueObservationJobs(10, dryRun);
      setRunnerResult(res);
      const updated = await apiClient.getObservationJobs({ limit: 20 }).catch(() => []);
      setObsJobs(updated);
    } catch (err: unknown) {
      setTriggerFeedback(`Runner error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally {
      setRunnerLoading(false);
    }
  };

  const handleStartWorker = async () => {
    setWorkerLoading(true);
    try {
      const stats = await apiClient.startObservationWorker();
      setWorkerStats(stats);
      setTriggerFeedback("Observation Worker started.");
      setTimeout(() => setTriggerFeedback(null), 4000);
    } catch (err: unknown) {
      setTriggerFeedback(`Start worker failed: ${err instanceof Error ? err.message : "Error"}`);
    } finally {
      setWorkerLoading(false);
    }
  };

  const handleStopWorker = async () => {
    setWorkerLoading(true);
    try {
      const stats = await apiClient.stopObservationWorker();
      setWorkerStats(stats);
      setTriggerFeedback("Observation Worker stopped gracefully.");
      setTimeout(() => setTriggerFeedback(null), 4000);
    } catch (err: unknown) {
      setTriggerFeedback(`Stop worker failed: ${err instanceof Error ? err.message : "Error"}`);
    } finally {
      setWorkerLoading(false);
    }
  };

  const handleRecoverJobs = async () => {
    setWorkerLoading(true);
    try {
      const res = await apiClient.recoverAbandonedObservationJobs();
      setTriggerFeedback(`Recovery complete: ${res.total_recovered} jobs scanned (${res.recovered_to_retry.length} reset to RETRY).`);
      setTimeout(() => setTriggerFeedback(null), 5000);
      const [wRes, jRes] = await Promise.all([
        apiClient.getObservationWorkerStatus().catch(() => null),
        apiClient.getObservationJobs({ limit: 20 }).catch(() => []),
      ]);
      if (wRes) setWorkerStats(wRes);
      setObsJobs(jRes);
    } catch (err: unknown) {
      setTriggerFeedback(`Recovery failed: ${err instanceof Error ? err.message : "Error"}`);
    } finally {
      setWorkerLoading(false);
    }
  };

  useEffect(() => {
    async function loadScheduler() {
      setLoading(true);
      setError(null);
      try {
        const [dRes, sRes, jRes, wRes] = await Promise.all([
          apiClient.getSchedulerDaemon(),
          apiClient.getObservationMaturity(),
          apiClient.getObservationJobs({ limit: 20 }).catch(() => []),
          apiClient.getObservationWorkerStatus().catch(() => null),
        ]);
        setDaemon(dRes);
        setSchedules(sRes);
        setObsJobs(jRes || []);
        setWorkerStats(wRes);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load scheduler data");
      } finally {
        setLoading(false);
      }
    }
    loadScheduler();
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center space-y-4">
        <RotateCw className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500">Loading Observation Scheduler & Daemon Telemetry...</p>
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
              Observation Scheduler & Pipeline Monitor
            </h1>
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                daemon?.is_running
                  ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20"
                  : "bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-500/20"
              }`}
            >
              <span
                className={`mr-1.5 h-1.5 w-1.5 rounded-full ${
                  daemon?.is_running ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
                }`}
              ></span>
              {daemon?.mode || "STANDBY"}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Real-time tracking of observation windows (T+7, T+30, T+90) for frozen decisions against market ground truth.
          </p>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 shadow-sm"
        >
          <RotateCw className="h-3.5 w-3.5" />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {/* Daemon Status Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="flex items-start space-x-3">
            <div className="rounded-lg bg-indigo-50 p-2.5 text-indigo-600">
              <Cpu className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">{daemon?.daemon_name}</h2>
              <p className="mt-0.5 text-xs text-slate-500">{daemon?.message}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs">
            <div className="flex items-center space-x-1.5 text-slate-600">
              <Clock className="h-4 w-4 text-slate-400" />
              <span>Poll Interval:</span>
              <strong className="text-slate-900">{daemon?.poll_interval_seconds ?? 3600}s</strong>
            </div>
            <div className="flex items-center space-x-1.5 text-slate-600">
              <Activity className="h-4 w-4 text-slate-400" />
              <span>Heartbeat:</span>
              <strong className="text-slate-900">{daemon?.last_heartbeat || "Standby on demand"}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Scheduled Products</span>
            <Layers className="h-4 w-4 text-indigo-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{schedules?.total_scheduled ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Tracked in decision ledger</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Ready for Observation</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-emerald-600">{schedules?.ready_for_observation ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Maturity window reached</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Pending Observation</span>
            <Hourglass className="h-4 w-4 text-amber-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-amber-600">{schedules?.pending_observation ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Awaiting ground truth date</p>
        </div>
      </div>

      {/* Scheduled Products Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Observation Pipeline Registry</h3>
            <p className="text-xs text-slate-500">
              Evaluated via ObservationScheduler against active decision ledger records
            </p>
          </div>
          <div className="flex items-center space-x-1 text-xs text-slate-500">
            <Calendar className="h-3.5 w-3.5" />
            <span>Windows: 7d, 14d, 30d, 60d, 90d</span>
          </div>
        </div>

        {triggerFeedback && (
          <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 text-xs px-4 py-2 font-medium rounded-lg flex items-center justify-between">
            <span>{triggerFeedback}</span>
            <button type="button" onClick={() => setTriggerFeedback(null)} className="text-indigo-400 hover:text-indigo-700">✕</button>
          </div>
        )}

        {schedules && schedules.products.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3 font-semibold">Product ID</th>
                  <th className="px-6 py-3 font-semibold">Decision Date</th>
                  <th className="px-6 py-3 font-semibold">First Expected Date</th>
                  <th className="px-6 py-3 font-semibold">Window Days</th>
                  <th className="px-6 py-3 font-semibold">Maturity Status</th>
                  <th className="px-6 py-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {schedules.products.map((item, idx) => (
                  <tr key={idx} className="hover:bg-slate-50">
                    <td className="px-6 py-4 font-mono font-bold text-slate-900">{item.product_id}</td>
                    <td className="px-6 py-4 text-slate-700">{item.decision_date}</td>
                    <td className="px-6 py-4 text-slate-700">{item.first_expected_date || "—"}</td>
                    <td className="px-6 py-4 font-medium text-slate-900">{item.observation_window_days} days</td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                          item.status === "READY"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-amber-50 text-amber-700 border border-amber-200"
                        }`}
                      >
                        {item.status === "READY" ? (
                          <CheckCircle2 className="mr-1 h-3 w-3" />
                        ) : (
                          <Hourglass className="mr-1 h-3 w-3" />
                        )}
                        {item.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleTriggerObserve(item.product_id)}
                        disabled={triggeringId === item.product_id}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 disabled:opacity-50 transition-colors shadow-2xs"
                      >
                        <RotateCw className={`w-3 h-3 ${triggeringId === item.product_id ? "animate-spin" : ""}`} />
                        <span>{triggeringId === item.product_id ? "Checking..." : "Check Maturity"}</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-sm text-slate-500">
            <AlertCircle className="mx-auto h-8 w-8 text-slate-400 mb-2" />
            No observation items currently scheduled in SQLite.
          </div>
        )}
      </div>

      {/* Phase 6 Controlled Persistent Observation Worker */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-200 p-5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-50/50">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-semibold text-slate-900">
                Phase 6 Persistent Observation Worker
              </h2>
              <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                Mode: CONTROLLED WORKER
              </span>
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  workerStats?.is_running
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : workerStats?.state === "ERROR"
                    ? "bg-red-50 text-red-700 border border-red-200"
                    : "bg-slate-100 text-slate-700 border border-slate-200"
                }`}
              >
                <span
                  className={`mr-1.5 h-1.5 w-1.5 rounded-full ${
                    workerStats?.is_running
                      ? "bg-emerald-500 animate-pulse"
                      : workerStats?.state === "ERROR"
                      ? "bg-red-500"
                      : "bg-slate-400"
                  }`}
                />
                Status: {workerStats?.state || "STOPPED"}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Controlled background loop that periodically polls due jobs and executes them via the safe observation scheduler. Supports crash recovery of abandoned jobs.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRecoverJobs}
              disabled={workerLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 disabled:opacity-50 shadow-2xs transition-colors"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
              <span>Recover Abandoned</span>
            </button>
            {workerStats?.is_running ? (
              <button
                type="button"
                onClick={handleStopWorker}
                disabled={workerLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600 hover:bg-red-700 text-white disabled:opacity-50 shadow-sm transition-colors"
              >
                <Square className="w-3.5 h-3.5" />
                <span>{workerLoading ? "Stopping..." : "Stop Worker"}</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStartWorker}
                disabled={workerLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50 shadow-sm transition-colors"
              >
                <Play className="w-3.5 h-3.5" />
                <span>{workerLoading ? "Starting..." : "Start Worker"}</span>
              </button>
            )}
          </div>
        </div>

        {/* Worker Telemetry Grid */}
        <div className="p-5 border-b border-slate-200 bg-white text-xs">
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-4">
            <div>
              <span className="text-slate-400 block">Worker ID:</span>
              <strong className="text-slate-900 font-mono">{workerStats?.worker_id || "obs-worker-1"}</strong>
            </div>
            <div>
              <span className="text-slate-400 block">Poll Interval:</span>
              <strong className="text-slate-900">{workerStats?.poll_interval_seconds ?? 30}s</strong>
            </div>
            <div>
              <span className="text-slate-400 block">Batch Size:</span>
              <strong className="text-slate-900">{workerStats?.batch_size ?? 10} jobs</strong>
            </div>
            <div>
              <span className="text-slate-400 block">Cycles Completed:</span>
              <strong className="text-indigo-600 font-semibold">{workerStats?.cycle_count ?? 0}</strong>
            </div>
            <div>
              <span className="text-slate-400 block">Jobs Executed:</span>
              <strong className="text-slate-900">{workerStats?.total_jobs_executed ?? 0}</strong>
            </div>
            <div>
              <span className="text-slate-400 block">Recovered Abandoned:</span>
              <strong className="text-amber-600 font-semibold">{workerStats?.recovered_jobs_count ?? 0}</strong>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-6">
              <div>
                <span className="text-slate-400">Succeeded: </span>
                <strong className="text-emerald-600 font-semibold">{workerStats?.total_jobs_succeeded ?? 0}</strong>
              </div>
              <div>
                <span className="text-slate-400">Failed: </span>
                <strong className="text-red-600 font-semibold">{workerStats?.total_jobs_failed ?? 0}</strong>
              </div>
              <div>
                <span className="text-slate-400">Skipped: </span>
                <strong className="text-amber-600 font-semibold">{workerStats?.total_jobs_skipped ?? 0}</strong>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-slate-500">
              <div>
                <span>Last Heartbeat: </span>
                <strong className="text-slate-700">
                  {workerStats?.last_heartbeat ? workerStats.last_heartbeat.slice(0, 19).replace("T", " ") : "Standby"}
                </strong>
              </div>
              <div>
                <span>Last Cycle: </span>
                <strong className="text-slate-700">
                  {workerStats?.last_cycle_at ? workerStats.last_cycle_at.slice(0, 19).replace("T", " ") : "Never"}
                </strong>
              </div>
            </div>
          </div>

          {workerStats?.last_error && (
            <div className="mt-3 p-2.5 rounded-lg bg-red-50 border border-red-200 text-red-700 font-mono text-xs">
              <strong>Last Error:</strong> {workerStats.last_error}
            </div>
          )}
        </div>
      </div>

      {/* Phase 6 Observation Job Runner (One-Shot Mode) */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-200 p-5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-50/50">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-semibold text-slate-900">
                Phase 6 Source Observation Jobs
              </h2>
              <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                Mode: ONE-SHOT
              </span>
              <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Status: READY
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Deterministic job runner on top of verified source observation pipeline. Executes on-demand without persistent daemons.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleRunJobs(true)}
              disabled={runnerLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 disabled:opacity-50 shadow-2xs transition-colors"
            >
              <span>Simulate Dry Run</span>
            </button>
            <button
              type="button"
              onClick={() => handleRunJobs(false)}
              disabled={runnerLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 shadow-sm transition-colors"
            >
              <RotateCw className={`w-3.5 h-3.5 ${runnerLoading ? "animate-spin" : ""}`} />
              <span>{runnerLoading ? "Executing..." : "Run Due Jobs (Limit 10)"}</span>
            </button>
          </div>
        </div>

        {/* Runner Result Summary Banner if present */}
        {runnerResult && (
          <div className="p-4 bg-slate-50 border-b border-slate-200 text-xs">
            <div className="flex flex-wrap items-center gap-4">
              <span className="font-semibold text-slate-900">
                {runnerResult.dry_run ? "Simulation (Dry Run) Complete:" : "Execution Pass Complete:"}
              </span>
              <span>Due: <strong>{runnerResult.due_jobs_count ?? runnerResult.found_due ?? 0}</strong></span>
              {!runnerResult.dry_run ? (
                <>
                  <span>Executed: <strong className="text-blue-600">{runnerResult.executed}</strong></span>
                  <span>Succeeded: <strong className="text-emerald-600">{runnerResult.succeeded}</strong></span>
                  <span>Failed: <strong className="text-red-600">{runnerResult.failed}</strong></span>
                  <span>Skipped: <strong className="text-amber-600">{runnerResult.skipped}</strong></span>
                </>
              ) : (
                <>
                  <span>Eligible to Run: <strong className="text-emerald-600">{runnerResult.eligible_count ?? 0}</strong></span>
                  <span>Ineligible / Skipped: <strong className="text-amber-600">{runnerResult.skipped_count ?? 0}</strong></span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Jobs Table */}
        {obsJobs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-6 py-3 font-semibold">Job ID</th>
                  <th className="px-6 py-3 font-semibold">Product ID</th>
                  <th className="px-6 py-3 font-semibold">Source</th>
                  <th className="px-6 py-3 font-semibold">Status</th>
                  <th className="px-6 py-3 font-semibold">Attempts</th>
                  <th className="px-6 py-3 font-semibold">Next Run</th>
                  <th className="px-6 py-3 font-semibold">Last Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {obsJobs.map((j) => (
                  <tr key={j.job_id} className="hover:bg-slate-50">
                    <td className="px-6 py-3 font-mono font-bold text-slate-900">#{j.job_id}</td>
                    <td className="px-6 py-3 font-mono text-slate-800">{j.product_id}</td>
                    <td className="px-6 py-3 font-medium text-slate-700">{j.source_id}</td>
                    <td className="px-6 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                          j.status === "SUCCESS"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : j.status === "RUNNING"
                            ? "bg-blue-50 text-blue-700 border border-blue-200"
                            : j.status === "FAILED"
                            ? "bg-red-50 text-red-700 border border-red-200"
                            : j.status === "SKIPPED"
                            ? "bg-amber-50 text-amber-700 border border-amber-200"
                            : "bg-slate-100 text-slate-700 border border-slate-200"
                        }`}
                      >
                        {j.status}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-slate-600">{j.attempt_count}</td>
                    <td className="px-6 py-3 text-slate-600">{j.next_run_at ? j.next_run_at.slice(0, 19).replace("T", " ") : "—"}</td>
                    <td className="px-6 py-3 text-red-600 font-mono max-w-xs truncate">{j.last_error || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-sm text-slate-500">
            <Hourglass className="mx-auto h-8 w-8 text-slate-400 mb-2" />
            No observation jobs currently registered. Jobs are created for verified sources (Google Trends, GDELT).
          </div>
        )}
      </div>
    </div>
  );
}

