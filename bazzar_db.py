"""SQLite-backed storage for Hypixel Bazaar time-series data.

Replaces the monolithic single-line JSON file with a normalized schema
that supports atomic inserts, indexed queries, and efficient range scans.
"""
import sqlite3
import os
import json


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_ms  INTEGER NOT NULL,
    product_id    INTEGER NOT NULL REFERENCES products(id),
    sell_price    REAL,
    buy_price     REAL,
    sell_volume   REAL,
    buy_volume    REAL,
    sell_orders   REAL,
    buy_orders    REAL
);

CREATE INDEX IF NOT EXISTS idx_snap_product_time
    ON snapshots(product_id, timestamp_ms);

CREATE INDEX IF NOT EXISTS idx_snap_timestamp
    ON snapshots(timestamp_ms);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class BazaarDB:
    """High-level interface to the Bazaar SQLite database."""

    def __init__(self, db_path="bazzar.db"):
        self.db_path = db_path
        is_new = not os.path.exists(db_path)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        if is_new:
            self._conn.execute(
                "INSERT OR IGNORE INTO meta VALUES (?, ?)",
                ("schema_version", "1"),
            )
            self._conn.commit()

    # ── products ──────────────────────────────────────────────────────

    def _product_id_to_pk(self, product_id):
        """Return the integer primary key for *product_id*, inserting if new."""
        self._conn.execute(
            "INSERT OR IGNORE INTO products (product_id) VALUES (?)",
            (product_id,),
        )
        return self._conn.execute(
            "SELECT id FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()["id"]

    def get_product_ids(self):
        """Return sorted list of product_id strings."""
        rows = self._conn.execute(
            "SELECT product_id FROM products ORDER BY product_id"
        ).fetchall()
        return [r["product_id"] for r in rows]

    # ── inserts ───────────────────────────────────────────────────────

    def insert_snapshot(self, timestamp_ms, products_data):
        """Atomically insert one snapshot for multiple products.

        *products_data*: dict of {product_id: {sell_price, buy_price, ...}}
                         as returned by the Hypixel API quick_status.
        """
        with self._conn:
            for pid, fields in products_data.items():
                pk = self._product_id_to_pk(pid)
                self._conn.execute(
                    """INSERT INTO snapshots
                       (timestamp_ms, product_id, sell_price, buy_price,
                        sell_volume, buy_volume, sell_orders, buy_orders)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        timestamp_ms,
                        pk,
                        fields.get("sellPrice"),
                        fields.get("buyPrice"),
                        fields.get("sellVolume"),
                        fields.get("buyVolume"),
                        fields.get("sellOrders"),
                        fields.get("buyOrders"),
                    ),
                )

    # ── queries ───────────────────────────────────────────────────────

    def get_latest_for_all(self):
        """Return dict {product_id: {field: value}} for the most recent snapshot of each product."""
        result = {}
        rows = self._conn.execute("""
            SELECT p.product_id, s.timestamp_ms,
                   s.sell_price, s.buy_price,
                   s.sell_volume, s.buy_volume,
                   s.sell_orders, s.buy_orders
            FROM snapshots s
            JOIN products p ON p.id = s.product_id
            WHERE s.timestamp_ms = (SELECT MAX(timestamp_ms) FROM snapshots)
        """).fetchall()
        for row in rows:
            result[row["product_id"]] = {
                "timestamp_ms": row["timestamp_ms"],
                "sell_price": row["sell_price"],
                "buy_price": row["buy_price"],
                "sell_volume": row["sell_volume"],
                "buy_volume": row["buy_volume"],
                "sell_orders": row["sell_orders"],
                "buy_orders": row["buy_orders"],
            }
        return result

    def get_history(self, product_id, fields=("sell_price", "buy_price")):
        """Return {field: [values], "time": [epoch_ms]} for charting."""
        pk = self._product_id_to_pk(product_id)
        cols = ", ".join(f"s.{f}" for f in fields)
        rows = self._conn.execute(
            f"SELECT s.timestamp_ms, {cols} "
            f"FROM snapshots s WHERE s.product_id = ? "
            f"ORDER BY s.timestamp_ms",
            (pk,),
        ).fetchall()

        result = {"time": []}
        for f in fields:
            result[f] = []
        for row in rows:
            result["time"].append(row["timestamp_ms"])
            for f in fields:
                result[f].append(row[f])
        return result

    def get_time_range(self):
        """Return (min_timestamp_ms, max_timestamp_ms) or (None, None)."""
        row = self._conn.execute(
            "SELECT MIN(timestamp_ms) AS lo, MAX(timestamp_ms) AS hi FROM snapshots"
        ).fetchone()
        if row["lo"] is None:
            return None, None
        return row["lo"], row["hi"]

    def get_snapshot_count(self):
        """Return total number of snapshot rows."""
        row = self._conn.execute("SELECT COUNT(*) AS cnt FROM snapshots").fetchone()
        return row["cnt"]

    def get_latest_timestamp(self):
        """Return the most recent timestamp_ms, or 0 if empty."""
        row = self._conn.execute(
            "SELECT MAX(timestamp_ms) AS ts FROM snapshots"
        ).fetchone()
        return row["ts"] or 0

    # ── analytics ─────────────────────────────────────────────────────

    def get_price_change(self, product_id, field="sell_price", lookback=1):
        """Return (change_abs, change_pct) between latest and N-snapshots-ago value.

        *lookback*: how many snapshots back to compare against (1 = previous snapshot).
        Returns (0, 0) if insufficient data.
        """
        pk = self._product_id_to_pk(product_id)
        rows = self._conn.execute(
            f"SELECT s.{field} FROM snapshots s "
            f"WHERE s.product_id = ? "
            f"ORDER BY s.timestamp_ms DESC LIMIT ?",
            (pk, lookback + 1),
        ).fetchall()

        if len(rows) < lookback + 1:
            return 0, 0
        latest = rows[0][0] or 0
        older = rows[-1][0] or 0
        if older == 0:
            return 0, 0
        change = latest - older
        pct = (change / older) * 100
        return round(change, 2), round(pct, 2)

    def get_summary_stats(self, product_id, field="sell_price"):
        """Return {min, max, mean, latest, count} for a given numeric field."""
        pk = self._product_id_to_pk(product_id)
        row = self._conn.execute(
            f"SELECT MIN(s.{field}), MAX(s.{field}), AVG(s.{field}), COUNT(s.{field}) "
            f"FROM snapshots s WHERE s.product_id = ?",
            (pk,),
        ).fetchone()
        count = row[3] or 0
        latest_row = self._conn.execute(
            f"SELECT s.{field} FROM snapshots s "
            f"WHERE s.product_id = ? ORDER BY s.timestamp_ms DESC LIMIT 1",
            (pk,),
        ).fetchone()
        latest = latest_row[0] if latest_row else 0
        return {
            "min": round(row[0], 2) if row[0] else 0,
            "max": round(row[1], 2) if row[1] else 0,
            "mean": round(row[2], 2) if row[2] else 0,
            "latest": round(latest, 2) if latest else 0,
            "count": count,
        }

    def get_all_price_changes(self, field="sell_price", lookback=1):
        """Return {product_id: (change_abs, change_pct)} for all products."""
        result = {}
        for pid in self.get_product_ids():
            change = self.get_price_change(pid, field, lookback)
            if change != (0, 0):
                result[pid] = change
        return result

    # ── moving average ────────────────────────────────────────────────

    def get_moving_average(self, product_id, field="sell_price", window=5):
        """Return windowed-SMA as list of (timestamp_ms, avg_value).

        Requires at least *window* snapshots; returns [] otherwise.
        """
        pk = self._product_id_to_pk(product_id)
        rows = self._conn.execute(
            f"SELECT s.timestamp_ms, s.{field} FROM snapshots s "
            f"WHERE s.product_id = ? "
            f"ORDER BY s.timestamp_ms",
            (pk,),
        ).fetchall()

        if len(rows) < window:
            return []

        result = []
        values = [r[1] or 0 for r in rows]
        for i in range(window - 1, len(values)):
            avg = sum(values[i - window + 1:i + 1]) / window
            result.append((rows[i][0], round(avg, 2)))
        return result

    # ── market overview ───────────────────────────────────────────────

    def get_market_summary(self):
        """Return dict with aggregate market stats."""
        latest = self.get_latest_for_all()
        if not latest:
            return {"total_products": 0, "total_sell_volume": 0,
                    "total_buy_volume": 0, "avg_margin": 0, "top_movers": []}

        total_sv = sum(d.get("sell_volume", 0) or 0 for d in latest.values())
        total_bv = sum(d.get("buy_volume", 0) or 0 for d in latest.values())
        margins = []
        movers = []
        for pid, d in latest.items():
            bp = d.get("buy_price", 0) or 0
            sp = d.get("sell_price", 0) or 0
            if bp:
                margins.append(((sp - bp) / bp) * 100)
            change = self.get_price_change(pid, "sell_price", lookback=1)
            if change[1] != 0:
                movers.append((pid, change[1]))

        movers.sort(key=lambda x: abs(x[1]), reverse=True)
        return {
            "total_products": len(latest),
            "total_sell_volume": total_sv,
            "total_buy_volume": total_bv,
            "avg_margin": round(sum(margins) / len(margins), 2) if margins else 0,
            "top_movers": movers[:5],
        }

    # ── migration ─────────────────────────────────────────────────────

    def migrate_from_json(self, json_path):
        """One-shot import from the legacy single-line JSON file.

        Skips 'time', 'BAZAAR_COOKIE', and any key whose value is not a dict.
        Expects format:
            {"time": [ms,...], "PROD_ID": {"sell_price": [...], ...}, ...}
        """
        with open(json_path, "r") as f:
            data = json.load(f)

        time_list = data.get("time", [])
        if not time_list:
            return 0

        product_keys = [
            k for k in data
            if k != "time"
            and k != "BAZAAR_COOKIE"
            and isinstance(data[k], dict)
        ]

        count = 0
        with self._conn:
            for idx, ts in enumerate(time_list):
                batch = {}
                for pid in product_keys:
                    product_data = data[pid]
                    fields = {
                        "sellPrice": self._idx_or_none(product_data, "sell_price", idx),
                        "buyPrice": self._idx_or_none(product_data, "buy_price", idx),
                        "sellVolume": self._idx_or_none(product_data, "sell_volume", idx),
                        "buyVolume": self._idx_or_none(product_data, "buy_volume", idx),
                        "sellOrders": self._idx_or_none(product_data, "sell_order", idx),
                        "buyOrders": self._idx_or_none(product_data, "buy_order", idx),
                    }
                    batch[pid] = fields
                self.insert_snapshot(ts, batch)
                count += len(batch)

        return count

    @staticmethod
    def _idx_or_none(data_dict, key, idx):
        arr = data_dict.get(key, [])
        return arr[idx] if idx < len(arr) else None

    # ── maintenance ───────────────────────────────────────────────────

    def vacuum(self):
        """Reclaim disk space."""
        self._conn.execute("VACUUM")

    def close(self):
        self._conn.close()
