"use client";

import React, { useState, useEffect } from "react";
import {
  Database,
  Table as TableIcon,
  Search,
  CheckCircle2,
  Lock,
  ChevronLeft,
  ChevronRight,
  RotateCw,
  HardDrive,
  Code,
  ShieldCheck,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import {
  DatabaseOverviewResponse,
  TableInfo,
  TableSchemaResponse,
  TableRowsResponse,
} from "@/types/api";
import { ErrorState } from "@/components/common/ErrorState";

export default function DbExplorerPage() {
  const [overview, setOverview] = useState<DatabaseOverviewResponse | null>(null);
  const [selectedTable, setSelectedTable] = useState<string>("master_products");
  const [tableSearch, setTableSearch] = useState<string>("");
  
  // Tab within selected table
  const [viewMode, setViewMode] = useState<"rows" | "schema">("rows");
  
  // Table schema & rows state
  const [schema, setSchema] = useState<TableSchemaResponse | null>(null);
  const [rowsData, setRowsData] = useState<TableRowsResponse | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

  const [loadingOverview, setLoadingOverview] = useState<boolean>(true);
  const [loadingTable, setLoadingTable] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load database overview on mount
  useEffect(() => {
    async function loadOverview() {
      setLoadingOverview(true);
      setError(null);
      try {
        const res = await apiClient.getDbOverview();
        setOverview(res);
        if (res.tables && res.tables.length > 0) {
          const preferred = res.tables.find((t: TableInfo) => t.name === "master_products");
          setSelectedTable(preferred ? preferred.name : res.tables[0].name);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load database overview");
      } finally {
        setLoadingOverview(false);
      }
    }
    loadOverview();
  }, []);

  // Load schema and rows when selected table or page changes
  useEffect(() => {
    if (!selectedTable) return;
    async function loadTableDetails() {
      setLoadingTable(true);
      try {
        const [schemaRes, rowsRes] = await Promise.all([
          apiClient.getDbSchema(selectedTable),
          apiClient.getDbRows(selectedTable, currentPage, pageSize),
        ]);
        setSchema(schemaRes);
        setRowsData(rowsRes);
      } catch (err: unknown) {
        console.error("Failed to load table details:", err);
      } finally {
        setLoadingTable(false);
      }
    }
    loadTableDetails();
  }, [selectedTable, currentPage]);

  const handleSelectTable = (tblName: string) => {
    setSelectedTable(tblName);
    setCurrentPage(1);
  };

  const filteredTables = (overview?.tables || []).filter((t: TableInfo) =>
    (t?.name || "").toLowerCase().includes((tableSearch || "").toLowerCase())
  );

  if (loadingOverview) {
    return (
      <div className="flex h-96 flex-col items-center justify-center space-y-4">
        <RotateCw className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500">Connecting to SQLite Production Database...</p>
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  }

  const totalPages = rowsData ? Math.ceil(rowsData.total_rows / pageSize) : 1;
  const sizeMb = overview?.file_size_bytes ? (overview.file_size_bytes / (1024 * 1024)).toFixed(2) : "0.00";

  return (
    <div className="space-y-6 p-6">
      {/* Header Banner */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Authoritative SQLite Database Explorer
            </h1>
            <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
              <Lock className="mr-1 h-3 w-3" />
              Read-Only Safe
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Live inspection of the {overview?.total_tables ?? 36} authoritative production tables in {overview?.database_file || "research_engine.db"}.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 shadow-sm text-xs">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            <span className="text-slate-500">Integrity:</span>
            <span className="font-bold text-emerald-700 uppercase">{overview?.integrity_status}</span>
          </div>
          <div className="flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 shadow-sm text-xs">
            <CheckCircle2 className="h-4 w-4 text-blue-600" />
            <span className="text-slate-500">FK Violations:</span>
            <span className="font-bold text-slate-900">{overview?.foreign_key_violations_count}</span>
          </div>
          <div className="flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 shadow-sm text-xs">
            <HardDrive className="h-4 w-4 text-indigo-600" />
            <span className="text-slate-500">DB Size:</span>
            <span className="font-bold text-slate-900">{sizeMb} MB</span>
          </div>
        </div>
      </div>

      {/* Main Split Layout: Table List & Table Viewer */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
        {/* Left Column: Tables Sidebar */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col h-[750px]">
          <div className="p-4 border-b border-slate-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <Database className="h-4 w-4 text-indigo-600" />
                Tables ({overview?.total_tables})
              </span>
            </div>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter tables..."
                value={tableSearch}
                onChange={(e) => setTableSearch(e.target.value)}
                className="w-full rounded-lg border border-slate-200 pl-8 pr-3 py-1.5 text-xs text-slate-900 focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100 p-2 space-y-1">
            {filteredTables.map((t) => {
              const isSelected = t.name === selectedTable;
              return (
                <button
                  key={t.name}
                  onClick={() => handleSelectTable(t.name)}
                  className={`w-full flex items-center justify-between rounded-lg px-3 py-2 text-left text-xs transition ${
                    isSelected
                      ? "bg-blue-50 text-blue-900 font-semibold border border-blue-200"
                      : "text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <span className="truncate pr-2 font-mono">{t.name}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                      isSelected ? "bg-blue-200 text-blue-900" : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {(t?.row_count ?? 0).toLocaleString()}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right 3-Columns: Table Inspector */}
        <div className="lg:col-span-3 rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col h-[750px] overflow-hidden">
          {/* Header & Sub-Tabs */}
          <div className="p-4 border-b border-slate-200 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between bg-slate-50/50">
            <div>
              <div className="flex items-center space-x-2">
                <TableIcon className="h-5 w-5 text-blue-600" />
                <h2 className="text-lg font-bold font-mono text-slate-900">{selectedTable}</h2>
              </div>
              <p className="mt-0.5 text-xs text-slate-500">
                {(rowsData?.total_rows ?? schema?.row_count ?? 0).toLocaleString()} total rows | {schema?.columns?.length ?? 0} columns
              </p>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => setViewMode("rows")}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  viewMode === "rows"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
              >
                Data Rows ({(rowsData?.total_rows ?? schema?.row_count ?? 0).toLocaleString()})
              </button>
              <button
                onClick={() => setViewMode("schema")}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  viewMode === "schema"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
              >
                Schema & Columns ({schema?.columns?.length ?? 0})
              </button>
            </div>
          </div>

          {/* Table Content */}
          <div className="flex-1 overflow-auto p-4">
            {loadingTable ? (
              <div className="flex h-64 items-center justify-center space-y-2">
                <RotateCw className="h-6 w-6 animate-spin text-blue-600" />
              </div>
            ) : viewMode === "rows" ? (
              rowsData && rowsData.rows && rowsData.rows.length > 0 ? (
                <div className="overflow-x-auto border border-slate-200 rounded-lg">
                  <table className="w-full text-left text-xs text-slate-600">
                    <thead className="bg-slate-50 text-[11px] font-semibold text-slate-700 border-b border-slate-200 sticky top-0">
                      <tr>
                        {rowsData.columns.map((col) => (
                          <th key={col} className="px-4 py-2.5 whitespace-nowrap font-mono">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono">
                      {rowsData.rows.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-slate-50">
                          {rowsData.columns.map((col) => {
                            const val = row[col];
                            return (
                              <td key={col} className="px-4 py-2 whitespace-nowrap max-w-xs truncate text-slate-800">
                                {val === null || val === undefined ? (
                                  <span className="text-slate-300 italic">null</span>
                                ) : typeof val === "object" ? (
                                  JSON.stringify(val)
                                ) : (
                                  String(val)
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="flex h-64 flex-col items-center justify-center text-slate-400">
                  <Code className="h-8 w-8 mb-2" />
                  <p className="text-sm">Table is empty (0 rows recorded)</p>
                </div>
              )
            ) : (
              /* Schema View */
              <div className="space-y-4">
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <table className="w-full text-left text-xs text-slate-600">
                    <thead className="bg-slate-50 text-[11px] font-semibold text-slate-700 border-b border-slate-200">
                      <tr>
                        <th className="px-4 py-2.5">CID</th>
                        <th className="px-4 py-2.5">Column Name</th>
                        <th className="px-4 py-2.5">Data Type</th>
                        <th className="px-4 py-2.5">Primary Key</th>
                        <th className="px-4 py-2.5">Not Null</th>
                        <th className="px-4 py-2.5">Default Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono">
                      {schema?.columns?.map((c) => (
                        <tr key={c.cid} className="hover:bg-slate-50">
                          <td className="px-4 py-2 text-slate-400">{c.cid}</td>
                          <td className="px-4 py-2 font-bold text-slate-900">{c.name}</td>
                          <td className="px-4 py-2 text-indigo-700">{c.data_type || "BLOB"}</td>
                          <td className="px-4 py-2">
                            {c.pk ? (
                              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">
                                PRIMARY KEY
                              </span>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="px-4 py-2">
                            {c.notnull ? (
                              <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-bold text-red-700">
                                NOT NULL
                              </span>
                            ) : (
                              "NULLABLE"
                            )}
                          </td>
                          <td className="px-4 py-2 text-slate-500">
                            {c.default_value !== null && c.default_value !== undefined ? String(c.default_value) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {schema && schema.foreign_keys && schema.foreign_keys.length > 0 && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2">
                      Foreign Key References
                    </h4>
                    <pre className="text-xs font-mono text-slate-700 overflow-x-auto">
                      {JSON.stringify(schema.foreign_keys, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Pagination Footer */}
          {viewMode === "rows" && rowsData && rowsData.total_rows > 0 && (
            <div className="border-t border-slate-200 p-3 flex items-center justify-between bg-slate-50 text-xs">
              <span className="text-slate-500">
                Page <strong>{currentPage}</strong> of <strong>{totalPages || 1}</strong> ({rowsData.total_rows.toLocaleString()} rows)
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                  className="inline-flex items-center space-x-1 rounded border border-slate-200 bg-white px-2.5 py-1 text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                  <span>Previous</span>
                </button>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage >= totalPages}
                  className="inline-flex items-center space-x-1 rounded border border-slate-200 bg-white px-2.5 py-1 text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  <span>Next</span>
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
