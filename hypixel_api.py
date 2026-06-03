"""Robust Bazaar data collector — suitable for servers, cron, or long-running daemons.

Usage::
    python hypixel_api.py                          # defaults: 30s interval, console logging
    python hypixel_api.py --interval 60 --db /path/to/bazzar.db
    python hypixel_api.py --api-key YOUR_KEY --log-file collector.log
    python hypixel_api.py --pid-file /run/bazaar.pid --daemon

Signals:
    SIGINT / SIGTERM   → graceful shutdown, final stats logged.
"""
import argparse
import datetime
import logging
import logging.handlers
import os
import signal
import sys
import time

from hypixel_api_class import hypixel_api

logger = logging.getLogger("collector")
_running = True


def _shutdown_handler(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down gracefully...", signum)
    _running = False


def _setup_logging(log_file, level):
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    # Console
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # File (with rotation — 10 MB × 5 files)
    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10 * 1024 * 1024, backupCount=5,
            )
            fh.setFormatter(fmt)
            root.addHandler(fh)
        except OSError as exc:
            logger.warning("Cannot open log file %s: %s", log_file, exc)


def _write_pid(pid_file):
    if pid_file:
        try:
            with open(pid_file, "w") as f:
                f.write(str(os.getpid()))
        except OSError as exc:
            logger.warning("Cannot write PID file %s: %s", pid_file, exc)


def _remove_pid(pid_file):
    if pid_file:
        try:
            os.unlink(pid_file)
        except OSError:
            pass


class CollectorStats:
    """Thread-safe-ish counter bag for tracking collector health."""
    __slots__ = ("snapshots", "products_latest", "failures", "start_time",
                 "last_success", "last_error")

    def __init__(self):
        self.snapshots = 0
        self.products_latest = 0
        self.failures = 0
        self.start_time = time.time()
        self.last_success = 0.0
        self.last_error = ""
        self.last_error_time = 0.0

    def snapshot(self):
        elapsed = time.time() - self.start_time
        uptime = datetime.timedelta(seconds=int(elapsed))
        parts = [
            f"snapshots={self.snapshots}",
            f"failures={self.failures}",
            f"products={self.products_latest}",
            f"uptime={uptime}",
        ]
        if self.last_success:
            parts.append(
                f"last_ok={datetime.datetime.fromtimestamp(self.last_success):%H:%M:%S}"
            )
        if self.failures:
            parts.append(f"last_err={self.last_error}")
        return " | ".join(parts)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Hypixel SkyBlock Bazaar data collector",
    )
    p.add_argument("--db", default="bazzar.db",
                   help="SQLite database path (default: bazzar.db)")
    p.add_argument("--interval", type=int, default=30,
                   help="Seconds between API polls (default: 30)")
    p.add_argument("--api-key", default=os.environ.get("HYPIXEL_API_KEY"),
                   help="Hypixel API key (env: HYPIXEL_API_KEY)")
    p.add_argument("--log-file", default=None,
                   help="Log file path with rotation (optional)")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--pid-file", default=None,
                   help="Write PID to this file")
    p.add_argument("--status-file", default=None,
                   help="Periodically write collector stats to this file")
    p.add_argument("--daemon", action="store_true",
                   help="Detach and run in background (Unix only)")
    p.add_argument("--max-backoff", type=int, default=300,
                   help="Maximum backoff seconds after repeated failures (default: 300)")
    return p.parse_args(argv)


def run_loop(api, interval, stats, max_backoff, status_file):
    """Core fetch → store → sleep loop.  Returns when _running becomes False."""
    global _running
    stats.start_time = time.time()
    consecutive = 0

    while _running:
        try:
            data = api.fetch()
            if data.get("success"):
                count = api.save_snapshot(data)
                stats.snapshots += 1
                stats.products_latest = count
                stats.last_success = time.time()
                consecutive = 0
                ts = datetime.datetime.fromtimestamp(
                    data["lastUpdated"] / 1000.0
                ).strftime("%H:%M:%S")
                logger.info("#%d · %d products · %s", stats.snapshots, count, ts)
            else:
                stats.failures += 1
                consecutive += 1
                logger.warning("success=False · retrying in %ds", interval * 2)
                _interruptible_sleep(interval * 2)
                continue
        except (KeyboardInterrupt, SystemExit):
            _running = False
            break
        except Exception as exc:
            stats.failures += 1
            consecutive += 1
            stats.last_error = str(exc)[:120]
            stats.last_error_time = time.time()
            backoff = min(10 * (2 ** consecutive), max_backoff)
            logger.error("Error #%d · next retry in %ds · %s",
                         consecutive, backoff, exc)
            _interruptible_sleep(backoff)
            continue

        # Heartbeat status file
        if status_file:
            try:
                with open(status_file, "w") as sf:
                    sf.write(stats.snapshot() + "\n")
            except OSError:
                pass

        _interruptible_sleep(interval)


def _interruptible_sleep(seconds):
    """Sleep in 500 ms chunks so signals are handled promptly."""
    end = time.time() + seconds
    while _running and time.time() < end:
        time.sleep(min(0.5, end - time.time()))


def main():
    global _running
    args = parse_args()
    _setup_logging(args.log_file, args.log_level)
    _write_pid(args.pid_file)

    # Register signal handlers
    signal.signal(signal.SIGINT, _shutdown_handler)
    try:
        signal.signal(signal.SIGTERM, _shutdown_handler)
    except (ValueError, AttributeError):
        pass  # SIGTERM not available on Windows threads

    api = hypixel_api(db_path=args.db)
    api_key_display = f"{args.api_key[:4]}***" if args.api_key else "none"
    logger.info("Bazaar collector starting — DB: %s · interval: %ds · key: %s",
                args.db, args.interval, api_key_display)

    stats = CollectorStats()
    try:
        run_loop(api, args.interval, stats, args.max_backoff, args.status_file)
    finally:
        logger.info("Stopped — %s", stats.snapshot())
        _remove_pid(args.pid_file)
        if api.db:
            api.db.close()


if __name__ == "__main__":
    main()
