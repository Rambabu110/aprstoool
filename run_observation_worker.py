"""
run_observation_worker.py — Standalone Process Entrypoint for APRS Observation Worker.

Usage:
    python run_observation_worker.py [options]

Options:
    --interval SECONDS     Polling interval between cycles (default: 30.0)
    --batch-size N         Maximum due jobs to process per cycle (default: 10)
    --lease-seconds SECS   Lease timeout for abandoned RUNNING jobs (default: 300.0)
    --db-path PATH         Custom database path (default: data/research_engine.db or APRS_DB_PATH)
    --max-cycles N         Stop automatically after N cycles (default: unlimited)
    --once                 Run exactly one cycle and terminate
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.research_sources.worker import ObservationWorker, WorkerConfig

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s %(levelname)s — %(message)s"
)
logger = logging.getLogger("aprs.observation_worker_cli")


def main():
    parser = argparse.ArgumentParser(description="APRS Controlled Persistent Observation Worker")
    parser.add_argument("--interval", type=float, default=30.0, help="Polling interval in seconds (default: 30.0)")
    parser.add_argument("--batch-size", type=int, default=10, help="Max jobs per cycle (default: 10)")
    parser.add_argument("--lease-seconds", type=float, default=300.0, help="Lease seconds for crash recovery (default: 300.0)")
    parser.add_argument("--db-path", type=str, default=None, help="SQLite database path")
    parser.add_argument("--max-cycles", type=int, default=None, help="Exit after N cycles")
    parser.add_argument("--once", action="store_true", help="Execute single cycle and exit")

    args = parser.parse_args()

    max_cycles = 1 if args.once else args.max_cycles

    config = WorkerConfig(
        worker_id="obs-worker-cli",
        poll_interval_seconds=args.interval,
        batch_size=args.batch_size,
        running_lease_seconds=args.lease_seconds,
        db_path=args.db_path,
        max_cycles=max_cycles
    )

    worker = ObservationWorker(config=config)

    if args.once:
        logger.info("Executing single one-shot observation cycle...")
        result = worker.run_cycle()
        logger.info(f"Cycle completed. Result: {result.get('success')}")
        sys.exit(0 if result.get("success") else 1)
    else:
        logger.info(f"Starting persistent observation worker (Interval: {args.interval}s, Batch: {args.batch_size})...")
        worker.run_forever()


if __name__ == "__main__":
    main()
