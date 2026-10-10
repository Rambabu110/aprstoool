"use client";

import React, { useState, useEffect } from "react";
import {
  Bot,
  Activity,
  CheckCircle2,
  Play,
  RotateCw,
  Cpu,
  Layers,
  Terminal,
  Send,
  FileDown,
  MessageSquare,
  Users,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import {
  ResearchJobsResponse,
  SupervisorLogsResponse,
  WarRoomDebateResponse,
  WarRoomHistoryItem,
} from "@/types/api";
import { ErrorState } from "@/components/common/ErrorState";
import { ScoreBadge } from "@/components/common/ScoreBadge";

const SPECIALIST_ROSTER = [
  { id: "auto", name: "Auto Detect Specialist", avatar: "🎯", desc: "Routes query based on keywords" },
  { id: "all", name: "All Specialists (@all)", avatar: "👥", desc: "Consults entire 6-member team" },
  { id: "sales", name: "Maya — Sales & Demand", avatar: "📈", desc: "BSR velocity, ad hooks, unit projections" },
  { id: "quality", name: "Rajan — Quality & Defects", avatar: "🛡️", desc: "3-star flaw analysis, v2.0 engineering spec" },
  { id: "supplier", name: "Priya — Global Sourcing", avatar: "🏭", desc: "Manufacturing clusters, FOB, MOQs, BIS" },
  { id: "finance", name: "Arjun — Unit Economics", avatar: "💰", desc: "Landed COGS, stress testing, CAC surge" },
  { id: "tech", name: "Antigravity — Tech Systems", avatar: "💻", desc: "APRS platform architecture & database" },
  { id: "secretary", name: "Kavya — Chief Scribe", avatar: "📝", desc: "Meeting minutes summary & action items" },
];

export default function WarRoomPage() {
  const [activeTab, setActiveTab] = useState<"chat" | "debate" | "jobs" | "logs">("chat");

  // Data states
  const [jobsData, setJobsData] = useState<ResearchJobsResponse | null>(null);
  const [logsData, setLogsData] = useState<SupervisorLogsResponse | null>(null);
  const [debateData, setDebateData] = useState<WarRoomDebateResponse | null>(null);

  // War Room Chat states
  const [chatMessages, setChatMessages] = useState<WarRoomHistoryItem[]>([]);
  const [targetSpeaker, setTargetSpeaker] = useState<string>("auto");
  const [userQuery, setUserQuery] = useState<string>("");
  const [sendingChat, setSendingChat] = useState<boolean>(false);
  const [sessionId, setSessionId] = useState<string>("");

  // Selected product for debate
  const [selectedProductId, setSelectedProductId] = useState<string>("US_B09ABC");

  // UI states
  const [loadingOverview, setLoadingOverview] = useState<boolean>(true);
  const [loadingDebate, setLoadingDebate] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Initial load: Fetch jobs, supervisor logs, default debate, and meeting history
  useEffect(() => {
    async function loadData() {
      setLoadingOverview(true);
      setError(null);
      try {
        const [jobsRes, logsRes, histRes] = await Promise.all([
          apiClient.getResearchJobs().catch(() => ({ jobs: [], total_jobs: 0, active_jobs_count: 0, completed_jobs_count: 0 })),
          apiClient.getSupervisorLogs(30).catch(() => ({ logs: [], total_events: 0 })),
          apiClient.getWarRoomHistory(undefined, 60).catch(() => ({ total: 0, messages: [] })),
        ]);
        setJobsData(jobsRes as ResearchJobsResponse);
        setLogsData(logsRes as SupervisorLogsResponse);
        setChatMessages(histRes.messages || []);
        if (histRes.messages && histRes.messages.length > 0) {
          setSessionId(histRes.messages[histRes.messages.length - 1].session_id);
        }

        // Load default debate
        try {
          const deb = await apiClient.getWarRoomDebate(selectedProductId);
          setDebateData(deb);
        } catch {
          // If default product not loaded, leave debateData null
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load operations data");
      } finally {
        setLoadingOverview(false);
      }
    }
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRunDebate = async (pId: string) => {
    if (!pId.trim()) return;
    setLoadingDebate(true);
    try {
      const res = await apiClient.getWarRoomDebate(pId.trim());
      setDebateData(res);
    } catch (err: unknown) {
      alert(`Debate analysis failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setLoadingDebate(false);
    }
  };

  const handleSendChat = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!userQuery.trim() || sendingChat) return;

    const q = userQuery.trim();
    setUserQuery("");
    setSendingChat(true);

    try {
      const res = await apiClient.sendWarRoomChat(q, targetSpeaker);
      setSessionId(res.session_id);

      const newTurns: WarRoomHistoryItem[] = res.replies.map((r, i) => ({
        message_id: Date.now() + i,
        session_id: res.session_id,
        speaker_name: r.agent_name,
        speaker_role: r.title,
        avatar: r.avatar,
        user_prompt: q,
        response_text: r.message,
        timestamp: new Date().toLocaleTimeString(),
      }));

      setChatMessages((prev) => [...prev, ...newTurns]);
    } catch (err: unknown) {
      alert(`War Room request failed: ${err instanceof Error ? err.message : "Service unavailable"}`);
    } finally {
      setSendingChat(false);
    }
  };

  if (loadingOverview) {
    return (
      <div className="flex h-96 flex-col items-center justify-center space-y-4">
        <RotateCw className="h-8 w-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500">Loading AI War Room & Operations Console...</p>
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
              AI Multi-Agent War Room &amp; Operations Console
            </h1>
            <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
              <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Live Engine Connected
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Interactive single-speaker specialist dialogue, 5-agent consensus debate, and autonomous supervisor logs.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 shadow-xs">
            <Bot className="h-4 w-4 text-indigo-600" />
            <span className="text-xs font-medium text-slate-600">6 Specialist Agents:</span>
            <span className="text-xs font-bold text-slate-900">Online</span>
          </div>
          <div className="flex items-center space-x-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 shadow-xs">
            <Activity className="h-4 w-4 text-blue-600" />
            <span className="text-xs font-medium text-slate-600">Research Runs:</span>
            <span className="text-xs font-bold text-slate-900">{jobsData?.total_jobs ?? 0}</span>
          </div>
        </div>
      </div>

      {/* KPI Overview Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Total Research Runs</span>
            <Layers className="h-4 w-4 text-slate-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{jobsData?.total_jobs ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Recorded historical runs</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Active Pipelines</span>
            <Cpu className="h-4 w-4 text-emerald-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-emerald-600">{jobsData?.active_jobs_count ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Currently executing tasks</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Supervisor Log Events</span>
            <Terminal className="h-4 w-4 text-indigo-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-indigo-600">{logsData?.total_events ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">System telemetry events</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Recorded Meeting Turns</span>
            <MessageSquare className="h-4 w-4 text-amber-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-amber-600">{chatMessages.length}</p>
          <p className="mt-1 text-xs text-slate-500">Dialogue turns in SQLite</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "chat"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Users className="h-4 w-4" />
            <span>Interactive Specialist Team Room</span>
          </button>
          <button
            onClick={() => setActiveTab("debate")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "debate"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Bot className="h-4 w-4" />
            <span>5-Agent Adversarial Debate</span>
          </button>
          <button
            onClick={() => setActiveTab("jobs")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "jobs"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Activity className="h-4 w-4" />
            <span>Research Runs Telemetry ({jobsData?.total_jobs ?? 0})</span>
          </button>
          <button
            onClick={() => setActiveTab("logs")}
            className={`flex items-center space-x-2 border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === "logs"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            <Terminal className="h-4 w-4" />
            <span>AI Supervisor Log Stream</span>
          </button>
        </nav>
      </div>

      {/* TAB CONTENT: INTERACTIVE SPECIALIST TEAM ROOM (Streamlit Parity) */}
      {activeTab === "chat" && (
        <div className="space-y-6">
          {/* Controls Bar: Speaker Selector & Word Doc Export */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">
                Target Speaker:
              </span>
              <select
                value={targetSpeaker}
                onChange={(e) => setTargetSpeaker(e.target.value)}
                className="text-xs font-medium rounded-lg border border-slate-300 bg-slate-50 px-3 py-1.5 text-slate-800 focus:outline-hidden focus:border-indigo-500"
              >
                {SPECIALIST_ROSTER.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.avatar} {s.name}
                  </option>
                ))}
              </select>
              <span className="text-[11px] text-slate-500 hidden md:inline">
                {SPECIALIST_ROSTER.find((s) => s.id === targetSpeaker)?.desc}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <a
                href={apiClient.getWarRoomDocxUrl(sessionId || undefined)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 transition-colors shadow-2xs"
              >
                <FileDown className="w-3.5 h-3.5" />
                <span>Export Meeting Minutes (.docx)</span>
              </a>
            </div>
          </div>

          {/* Dialogue Feed */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-4 max-h-[550px] overflow-y-auto">
            {chatMessages.length === 0 ? (
              <div className="py-16 text-center space-y-2">
                <Users className="w-10 h-10 text-slate-300 mx-auto" />
                <h3 className="text-sm font-semibold text-slate-700">No Dialogue Recorded Yet</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Ask the specialist team a question below. Queries can target specific personas or route automatically.
                </p>
              </div>
            ) : (
              chatMessages.map((m) => (
                <div
                  key={m.message_id}
                  className="rounded-xl border border-slate-100 bg-slate-50/70 p-4 space-y-2.5 transition-all"
                >
                  <div className="flex items-center justify-between border-b border-slate-200/50 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{m.avatar || "🤖"}</span>
                      <div>
                        <span className="text-xs font-bold text-slate-900">{m.speaker_name}</span>
                        <span className="text-[10px] text-indigo-600 font-medium ml-2 uppercase">
                          {m.speaker_role}
                        </span>
                      </div>
                    </div>
                    <span className="text-[11px] text-slate-400 font-mono">{m.timestamp}</span>
                  </div>

                  {m.user_prompt && (
                    <div className="text-xs bg-white p-2.5 rounded-lg border border-slate-100 text-slate-600 italic">
                      <span className="font-semibold not-italic text-slate-400 mr-1.5">User Prompt:</span>
                      &quot;{m.user_prompt}&quot;
                    </div>
                  )}

                  <div className="text-xs text-slate-800 leading-relaxed font-sans bg-white p-3.5 rounded-lg border border-slate-200 shadow-2xs whitespace-pre-wrap">
                    {m.response_text}
                  </div>
                </div>
              ))
            )}

            {sendingChat && (
              <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-4 flex items-center gap-3 animate-pulse">
                <RotateCw className="w-4 h-4 animate-spin text-indigo-600" />
                <span className="text-xs font-medium text-indigo-700">
                  Specialist team is analysing prompt and consulting intelligence models...
                </span>
              </div>
            )}
          </div>

          {/* Prompt Suggestions */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-slate-400 font-medium">Quick Prompts:</span>
            {[
              "Sales: what is the Amazon demand velocity for bamboo products?",
              "Quality: find top defects in magnetic phone mounts",
              "Supplier: recommend best sourcing cluster in India with realistic FOB",
              "Finance: calculate 12-factor landed margin with 35% CAC surge",
              "Tech: verify scraper status and database schema integrity",
            ].map((p, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setUserQuery(p)}
                className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 hover:bg-slate-200 text-[11px] transition-colors"
              >
                {p}
              </button>
            ))}
          </div>

          {/* Chat Input Form */}
          <form onSubmit={handleSendChat} className="flex items-center gap-2">
            <input
              type="text"
              value={userQuery}
              onChange={(e) => setUserQuery(e.target.value)}
              placeholder="Ask the team... (e.g. 'What is the FOB price in Moradabad?', '@quality review flaw analysis')"
              disabled={sendingChat}
              className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 placeholder-slate-400 shadow-xs focus:border-indigo-500 focus:outline-hidden"
            />
            <button
              type="submit"
              disabled={sendingChat || !userQuery.trim()}
              className="inline-flex items-center gap-1.5 px-5 py-3 rounded-xl bg-indigo-600 text-white font-semibold text-sm hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-xs"
            >
              {sendingChat ? <RotateCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              <span>Consult Team</span>
            </button>
          </form>
        </div>
      )}

      {/* TAB CONTENT 2: 5-AGENT DEBATE */}
      {activeTab === "debate" && (
        <div className="space-y-6">
          {/* Target Product Search / Selector */}
          <div className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between shadow-xs">
            <div className="flex flex-1 items-center space-x-3">
              <label htmlFor="pId" className="text-sm font-semibold text-slate-700 whitespace-nowrap">
                Inspect Product ID:
              </label>
              <input
                id="pId"
                type="text"
                value={selectedProductId}
                onChange={(e) => setSelectedProductId(e.target.value)}
                placeholder="e.g. US_B09ABC"
                className="w-full max-w-xs rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-900 focus:border-blue-500 focus:outline-hidden"
              />
              <button
                onClick={() => handleRunDebate(selectedProductId)}
                disabled={loadingDebate}
                className="inline-flex items-center space-x-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {loadingDebate ? <RotateCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                <span>Evaluate Debate</span>
              </button>
            </div>

            <div className="text-xs text-slate-500">
              Backend Source: <span className="font-mono font-medium text-slate-700">AutonomousIntelligenceEngine</span>
            </div>
          </div>

          {debateData ? (
            <div className="space-y-6">
              {/* Verdict Header Card */}
              <div className="rounded-xl border border-slate-200 bg-gradient-to-r from-slate-900 to-indigo-950 p-6 text-white shadow-md">
                <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
                  <div>
                    <div className="flex items-center space-x-3">
                      <h2 className="text-xl font-bold">{debateData.product_name}</h2>
                      <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
                        {debateData.product_id}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-300">
                      Chief Arbiter Decision: <strong className="text-white">{debateData.decision_type}</strong>
                    </p>
                  </div>

                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-semibold">
                        Consensus Score
                      </span>
                      <span className="text-2xl font-black text-emerald-400">
                        {debateData.consensus_score}%
                      </span>
                    </div>
                    <ScoreBadge score={debateData.consensus_score} size="lg" />
                  </div>
                </div>

                <div className="mt-4 rounded-lg bg-slate-800/80 p-3.5 border border-slate-700 text-xs leading-relaxed text-slate-200">
                  <span className="font-bold text-amber-300 mr-1.5">⚖️ Arbiter Verdict:</span>
                  {debateData.arbiter_verdict}
                </div>
              </div>

              {/* Agent Debate Packets */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {debateData.agent_packets.map((agent, idx) => (
                  <div
                    key={idx}
                    className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-4"
                  >
                    <div>
                      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                        <div className="flex items-center space-x-2">
                          <Bot className="h-4 w-4 text-indigo-600" />
                          <h3 className="font-bold text-sm text-slate-900">{agent.agent}</h3>
                        </div>
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                            agent.recommendation === "PASS"
                              ? "bg-emerald-100 text-emerald-800"
                              : agent.recommendation === "KILL"
                              ? "bg-red-100 text-red-800"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {agent.recommendation}
                        </span>
                      </div>

                      <p className="mt-3 text-xs text-slate-700 leading-relaxed font-medium">
                        {agent.finding}
                      </p>

                      {/* Evidence */}
                      {agent.evidence && agent.evidence.length > 0 && (
                        <div className="mt-3">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                            Key Signals
                          </span>
                          <ul className="space-y-1 text-[11px] text-slate-600">
                            {agent.evidence.map((ev, i) => (
                              <li key={i} className="flex items-start space-x-1.5">
                                <span className="text-emerald-500 font-bold">&bull;</span>
                                <span>{ev}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Risks */}
                      {agent.risks && agent.risks.length > 0 && (
                        <div className="mt-3">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-red-400 block mb-1">
                            Risks Flagged
                          </span>
                          <ul className="space-y-1 text-[11px] text-red-700">
                            {agent.risks.map((rk, i) => (
                              <li key={i} className="flex items-start space-x-1.5">
                                <span className="font-bold">&times;</span>
                                <span>{rk}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    <div className="border-t border-slate-100 pt-3 flex items-center justify-between text-xs text-slate-500">
                      <span>Confidence</span>
                      <strong className="text-slate-900">{agent.confidence}%</strong>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-500">
              No debate found for product. Enter a valid product ID and evaluate debate.
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT 3: RESEARCH RUNS TELEMETRY */}
      {activeTab === "jobs" && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
          <div className="border-b border-slate-200 px-6 py-4">
            <h3 className="text-base font-semibold text-slate-900">Historical Research Cycles</h3>
            <p className="text-xs text-slate-500">
              Recorded runs from the research_runs SQLite table with signal counters and error tallies.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 font-semibold text-slate-600">
                <tr>
                  <th className="px-6 py-3">Run ID</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Started</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Products</th>
                  <th className="px-4 py-3">Signals</th>
                  <th className="px-4 py-3">Alerts</th>
                  <th className="px-4 py-3">Errors</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(jobsData?.jobs || []).map((job) => (
                  <tr key={job.research_run_id} className="hover:bg-slate-50">
                    <td className="px-6 py-3.5 font-mono font-medium text-slate-900">
                      {job.research_run_id}
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          job.run_status === "COMPLETED"
                            ? "bg-emerald-100 text-emerald-800"
                            : job.run_status === "RUNNING"
                            ? "bg-blue-100 text-blue-800 animate-pulse"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {job.run_status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-slate-500">{job.started_at}</td>
                    <td className="px-4 py-3.5 text-slate-700 font-mono">
                      {job.duration_seconds ? `${job.duration_seconds.toFixed(1)}s` : "—"}
                    </td>
                    <td className="px-4 py-3.5 text-slate-900 font-semibold">{job.products_processed}</td>
                    <td className="px-4 py-3.5 text-slate-900 font-semibold">{job.signals_generated_count}</td>
                    <td className="px-4 py-3.5 text-slate-900 font-semibold">{job.alerts_generated_count}</td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`font-semibold ${
                          job.errors_count > 0 ? "text-red-600" : "text-slate-400"
                        }`}
                      >
                        {job.errors_count}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB CONTENT 4: SUPERVISOR LOG STREAM */}
      {activeTab === "logs" && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
          <div className="border-b border-slate-200 px-6 py-4">
            <h3 className="text-base font-semibold text-slate-900">
              Autonomous Supervisor Diagnostic Events
            </h3>
            <p className="text-xs text-slate-500">
              Stream of events from ai_supervisor_logs capturing validator integrity checks.
            </p>
          </div>

          {logsData && logsData.logs && logsData.logs.length > 0 ? (
            <div className="divide-y divide-slate-100 p-4 space-y-2">
              {logsData.logs.map((log) => (
                <div
                  key={log.log_id}
                  className="flex items-start space-x-3 rounded-lg border border-slate-100 p-3 hover:bg-slate-50"
                >
                  <div className="mt-0.5">
                    <CheckCircle2 className="h-5 w-5 text-blue-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-xs text-slate-900">{log.event_type}</span>
                      <span className="text-[11px] text-slate-400">{log.timestamp}</span>
                    </div>
                    {log.details && Object.keys(log.details).length > 0 && (
                      <pre className="mt-1.5 rounded bg-slate-900 p-2 text-[10px] text-emerald-400 overflow-x-auto">
                        {JSON.stringify(log.details, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-sm text-slate-500">
              Zero supervisor exceptions logged. Engine health nominal.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
