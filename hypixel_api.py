"""Background data collector — polls Hypixel Bazaar API every 30s and stores to SQLite.

Usage:  python hypixel_api.py

Press Ctrl+C to stop.  Fetches are retried on transient errors; fatal errors
are logged and the loop continues after a backoff.
"""
import datetime
import logging
import time

from hypixel_api_class import hypixel_api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("collector")


def main():
    api = hypixel_api(db_path="bazzar.db")
    logger.info("Starting Bazaar data collector (DB: bazzar.db)")

    consecutive_failures = 0
    snapshot_count = 0

    while True:
        try:
            data = api.fetch()
            if data.get("success"):
                products = api.save_snapshot(data)
                snapshot_count += 1
                ts = datetime.datetime.fromtimestamp(
                    data["lastUpdated"] / 1000.0
                ).strftime("%Y-%m-%d %H:%M:%S")
                logger.info(
                    "Snapshot #%d — %d products — %s",
                    snapshot_count, products, ts,
                )
                consecutive_failures = 0
                sleep_sec = 30
            else:
                logger.warning("API returned success=False, retrying in 60s")
                sleep_sec = 60
                consecutive_failures += 1
        except Exception as exc:
            consecutive_failures += 1
            sleep_sec = min(30 * (2 ** consecutive_failures), 300)
            logger.error(
                "Fetch error (attempt %d, next retry in %ds): %s",
                consecutive_failures, sleep_sec, exc,
            )

        try:
            time.sleep(sleep_sec)
        except KeyboardInterrupt:
            logger.info("Shutting down (Ctrl+C). %d snapshots collected.", snapshot_count)
            break


if __name__ == "__main__":
    main()
