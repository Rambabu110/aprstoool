"""
api/services/operations_service.py — Service for War Room, Research Jobs, and Operational Telemetry.
Reuses AutonomousIntelligenceEngine and SQLite research_runs / ai_supervisor_logs tables.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from core.database import get_connection
from core.intelligence_engine import AutonomousIntelligenceEngine
from api.schemas.operations import (
    ResearchJobSummary,
    ResearchJobsResponse,
    SupervisorLogItem,
    SupervisorLogsResponse,
    AgentDebatePacket,
    WarRoomDebateResponse,
    WarRoomReply,
    WarRoomChatResponse,
    WarRoomHistoryItem,
    WarRoomHistoryResponse,
    AlertItem,
    AlertsListResponse,
    AlertDismissResponse,
    ConflictItem,
    ConflictsListResponse,
    ConflictResolveResponse,
)



class OperationsService:
    @staticmethod
    def get_research_jobs(limit: int = 50) -> ResearchJobsResponse:
        conn = get_connection()
        cur = conn.cursor()

        # Query all jobs ordered by started_at DESC
        cur.execute("""
            SELECT research_run_id, run_status, started_at, ended_at,
                   products_processed, sources_consulted_count, signals_generated_count,
                   alerts_generated_count, gate_transitions_count, errors_json
            FROM research_runs
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()

        # Summary counts
        cur.execute("SELECT COUNT(*) FROM research_runs")
        total_jobs = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM research_runs WHERE run_status = 'RUNNING'")
        active_jobs_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM research_runs WHERE run_status = 'COMPLETED'")
        completed_jobs_count = cur.fetchone()[0]

        cur.execute("""
            SELECT ended_at FROM research_runs 
            WHERE run_status = 'COMPLETED' AND ended_at IS NOT NULL
            ORDER BY ended_at DESC LIMIT 1
        """)
        last_succ = cur.fetchone()
        last_successful_run = last_succ[0] if last_succ else None

        conn.close()

        job_summaries: List[ResearchJobSummary] = []
        for r in rows:
            duration = None
            if r["started_at"] and r["ended_at"]:
                try:
                    s_dt = datetime.fromisoformat(r["started_at"])
                    e_dt = datetime.fromisoformat(r["ended_at"])
                    duration = max(0.0, (e_dt - s_dt).total_seconds())
                except Exception:
                    duration = None

            errors_count = 0
            if r["errors_json"]:
                try:
                    err_list = json.loads(r["errors_json"])
                    if isinstance(err_list, list):
                        errors_count = len(err_list)
                except Exception:
                    errors_count = 0

            job_summaries.append(
                ResearchJobSummary(
                    research_run_id=r["research_run_id"],
                    run_status=r["run_status"] or "UNKNOWN",
                    started_at=r["started_at"] or "N/A",
                    ended_at=r["ended_at"],
                    duration_seconds=duration,
                    products_processed=r["products_processed"] or 0,
                    sources_consulted_count=r["sources_consulted_count"] or 0,
                    signals_generated_count=r["signals_generated_count"] or 0,
                    alerts_generated_count=r["alerts_generated_count"] or 0,
                    gate_transitions_count=r["gate_transitions_count"] or 0,
                    errors_count=errors_count,
                )
            )

        return ResearchJobsResponse(
            jobs=job_summaries,
            total_jobs=total_jobs,
            active_jobs_count=active_jobs_count,
            completed_jobs_count=completed_jobs_count,
            last_successful_run=last_successful_run
        )

    @staticmethod
    def get_supervisor_logs(limit: int = 50) -> SupervisorLogsResponse:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM ai_supervisor_logs")
        total_events = cur.fetchone()[0]

        cur.execute("""
            SELECT log_id, event_type, details, timestamp, active_tasks, total_validations
            FROM ai_supervisor_logs
            ORDER BY log_id DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()

        log_items: List[SupervisorLogItem] = []
        for r in rows:
            details_dict = {}
            if r["details"]:
                try:
                    details_dict = json.loads(r["details"])
                except Exception:
                    details_dict = {"raw": str(r["details"])}

            log_items.append(
                SupervisorLogItem(
                    log_id=r["log_id"],
                    event_type=r["event_type"],
                    timestamp=r["timestamp"] or "N/A",
                    active_tasks=r["active_tasks"] or 0,
                    total_validations=r["total_validations"] or 0,
                    details=details_dict
                )
            )

        return SupervisorLogsResponse(
            logs=log_items,
            total_events=total_events
        )

    @staticmethod
    def get_war_room_debate(product_id: str) -> Optional[WarRoomDebateResponse]:
        """
        Retrieves already-persisted War Room debate analysis for a product in a strictly READ-ONLY manner.
        Does NOT execute write-producing pipelines (no run_full_product_intelligence, no save_*, no record_*).
        Retrieves from decision_ledger, arbiter_decision_log, or existing product_intelligence.
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM master_products WHERE product_id = ?", (product_id,))
        prod_row = cur.fetchone()
        if not prod_row:
            conn.close()
            return None

        # 1. Check if decision is already frozen in decision_ledger
        cur.execute(
            "SELECT * FROM decision_ledger WHERE product_id = ? ORDER BY decision_id DESC LIMIT 1",
            (product_id,)
        )
        dl_row = cur.fetchone()

        # 2. Check if arbiter_decision_log has a recorded decision
        cur.execute(
            "SELECT * FROM arbiter_decision_log WHERE product_id = ? ORDER BY decision_id DESC LIMIT 1",
            (product_id,)
        )
        arbiter_row = cur.fetchone()

        # 3. Check existing product_intelligence dossier
        cur.execute("SELECT * FROM product_intelligence WHERE product_id = ?", (product_id,))
        pi_row = cur.fetchone()
        conn.close()

        wr: Dict[str, Any] = {}

        if dl_row and dl_row["snapshot_payload_json"]:
            try:
                payload = json.loads(dl_row["snapshot_payload_json"])
                if "war_room_2" in payload and payload["war_room_2"]:
                    wr = payload["war_room_2"]
                else:
                    intel_snap = payload.get("intelligence_snapshot", {})
                    prod_snap = payload.get("product_snapshot", {}) or dict(prod_row)
                    dossier = {
                        "product": prod_snap,
                        "scorecard": json.loads(intel_snap.get("scorecard_json") or "{}"),
                        "kill_switch": {
                            "status": intel_snap.get("kill_status"),
                            "kill_reasons": json.loads(intel_snap.get("kill_reasons_json") or "[]"),
                        },
                        "counterfactual_economics": json.loads(intel_snap.get("counterfactual_json") or "{}"),
                    }
                    wr = AutonomousIntelligenceEngine.run_war_room_2(product_id, dossier)
            except Exception:
                wr = {}
        elif arbiter_row and arbiter_row["decision_json"]:
            try:
                dec = json.loads(arbiter_row["decision_json"])
                if "war_room_2" in dec:
                    wr = dec["war_room_2"]
                elif "agent_packets" in dec:
                    wr = dec
            except Exception:
                wr = {}

        if not wr and pi_row:
            try:
                dossier = {
                    "product": dict(prod_row),
                    "scorecard": json.loads(pi_row["scorecard_json"] or "{}"),
                    "kill_switch": {
                        "status": pi_row["kill_status"],
                        "kill_reasons": json.loads(pi_row["kill_reasons_json"] or "[]"),
                    },
                    "counterfactual_economics": json.loads(pi_row["counterfactual_json"] or "{}"),
                }
                wr = AutonomousIntelligenceEngine.run_war_room_2(product_id, dossier)
            except Exception:
                wr = {}

        if not wr:
            # Honest empty / not available state
            return WarRoomDebateResponse(
                product_id=product_id,
                product_name=prod_row["name"] or "Product",
                decision_type="NO_DEBATE_RECORDED",
                arbiter_verdict="No prior War Room debate or intelligence evaluation recorded for this product.",
                agent_packets=[],
                disagreements=[],
                consensus_score=0.0
            )

        packets_raw = wr.get("agent_packets", [])
        agent_packets: List[AgentDebatePacket] = []
        for p in packets_raw:
            agent_packets.append(
                AgentDebatePacket(
                    agent=p.get("agent", "Agent"),
                    finding=p.get("finding", ""),
                    confidence=float(p.get("confidence", 70.0)),
                    evidence=p.get("evidence", []),
                    risks=p.get("risks", []),
                    missing_data=p.get("missing_data", []),
                    recommendation=p.get("recommendation", "REVIEW")
                )
            )

        disagreements = wr.get("disagreements", [])
        decision_type = wr.get("decision_type", "CONSENSUS")
        arbiter_verdict = wr.get("arbiter_verdict", f"Final verdict classified as {decision_type}")

        pass_count = sum(1 for p in agent_packets if p.recommendation == "PASS")
        consensus_score = round((pass_count / max(1, len(agent_packets))) * 100.0, 1)

        return WarRoomDebateResponse(
            product_id=product_id,
            product_name=prod_row["name"] or "Product",
            decision_type=decision_type,
            arbiter_verdict=arbiter_verdict,
            agent_packets=agent_packets,
            disagreements=disagreements,
            consensus_score=consensus_score
        )

    @staticmethod
    def send_war_room_chat(user_query: str, target_speaker: str = "auto") -> WarRoomChatResponse:
        from core.team_meeting import AITeamMeetingRoom
        room = AITeamMeetingRoom()
        raw_replies = room.chat(user_query=user_query, target_speaker=target_speaker)
        replies = [
            WarRoomReply(
                agent_id=r.get("agent_id", "agent"),
                agent_name=r.get("agent_name", "Specialist"),
                title=r.get("title", "Specialist"),
                avatar=r.get("avatar", "🤖"),
                message=r.get("message", ""),
                cached=r.get("cached", False),
                latency_sec=r.get("latency_sec", 0.0),
            )
            for r in raw_replies
        ]
        return WarRoomChatResponse(session_id=room._session_id, replies=replies)

    @staticmethod
    def get_war_room_history(session_id: Optional[str] = None, limit: int = 60) -> WarRoomHistoryResponse:
        from core.database import get_meeting_history
        raw_msgs = get_meeting_history(session_id=session_id, limit=limit)
        messages = [
            WarRoomHistoryItem(
                message_id=m["message_id"],
                session_id=m.get("session_id") or "default",
                speaker_name=m.get("speaker_name") or "Specialist",
                speaker_role=m.get("speaker_role") or "analyst",
                avatar=m.get("avatar"),
                user_prompt=m.get("user_prompt") or "",
                response_text=m.get("response_text") or "",
                timestamp=str(m.get("timestamp") or ""),
            )
            for m in raw_msgs
        ]
        return WarRoomHistoryResponse(total=len(messages), messages=messages)

    @staticmethod
    def generate_war_room_docx(session_id: Optional[str] = None) -> str:
        from core.meeting_doc_manager import generate_meeting_word_doc
        return generate_meeting_word_doc(session_id=session_id)

    @staticmethod
    def get_active_alerts(limit: int = 50) -> AlertsListResponse:
        from core.database import get_active_alerts
        rows = get_active_alerts(limit=limit)
        alerts = [
            AlertItem(
                alert_id=r["alert_id"],
                product_id=r.get("product_id"),
                severity=r.get("severity") or "INFO",
                title=r.get("title") or "System Alert",
                what_happened=r.get("what_happened") or "",
                why_it_matters=r.get("why_it_matters") or "",
                recommended_action=r.get("recommended_action") or "",
                is_dismissed=r.get("is_dismissed", 0),
                created_at=str(r.get("created_at") or ""),
            )
            for r in rows
        ]
        return AlertsListResponse(total=len(alerts), alerts=alerts)

    @staticmethod
    def dismiss_alert(alert_id: int) -> AlertDismissResponse:
        from core.database import dismiss_alert
        ok = dismiss_alert(alert_id)
        return AlertDismissResponse(
            success=ok,
            alert_id=alert_id,
            message=f"Alert {alert_id} dismissed." if ok else f"Alert {alert_id} not found or could not be dismissed."
        )

    @staticmethod
    def get_data_conflicts(unresolved_only: bool = True) -> ConflictsListResponse:
        from core.database import get_data_conflicts
        rows = get_data_conflicts(unresolved_only=unresolved_only)
        conflicts = [
            ConflictItem(
                conflict_id=r["conflict_id"],
                product_id=r.get("product_id"),
                product_name=r.get("product_name"),
                field_name=r.get("field_name") or "",
                source_a=r.get("source_a") or "",
                value_a=str(r.get("value_a") or ""),
                source_b=r.get("source_b") or "",
                value_b=str(r.get("value_b") or ""),
                explanation=r.get("explanation"),
                resolution_status=r.get("resolution_status") or "UNRESOLVED",
                created_at=str(r.get("created_at") or ""),
            )
            for r in rows
        ]
        return ConflictsListResponse(total=len(conflicts), conflicts=conflicts)

    @staticmethod
    def resolve_data_conflict(conflict_id: int, resolution_status: str = "RESOLVED", explanation: str = "") -> ConflictResolveResponse:
        from core.database import resolve_data_conflict
        ok = resolve_data_conflict(conflict_id, resolution_status=resolution_status, explanation=explanation)
        return ConflictResolveResponse(
            success=ok,
            conflict_id=conflict_id,
            message=f"Conflict {conflict_id} resolved with status '{resolution_status}'." if ok else f"Conflict {conflict_id} could not be resolved."
        )

