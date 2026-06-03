# AGENTS.md

## Project summary

Hypixel SkyBlock Bazaar price tracker. Polls `https://api.hypixel.net/skyblock/bazaar` every 30s, stores time-series data in a SQLite database (`bazzar.db`), and provides a PySide6+matplotlib dashboard GUI for graphing price/volume/order trends with sortable table, search, and embedded charts.

## Commands

```
python hypixel_api.py    # background data collector (infinite loop)
python main.py           # PySide6 dashboard GUI
python update_bazzar_file.py  # one-shot manual update (BROKEN, see below)
pytest -m "not live"    # run unit tests (no network)
pytest -m "live"        # run live API integration tests (needs internet)
```

Run inside the `venv/` (Python 3.9). Activate with `venv\Scripts\activate`.

## Dependencies

**No dependency file exists.** You must manually install into the venv:

```
pip install requests matplotlib numpy PySide6
```

`pandas` is present in the venv but no project file uses it.

## Known bugs & quirks

- **`update_bazzar_file.py` crashes on startup.** It calls `hypixel_api(65, 4, 8774)` with 3 positional args, but `hypixel_api.__init__()` takes only `self`. Do not expect this script to work without fixing the instantiation.
- **Persistent spelling typos** — `file_handeler` (not `file_handler`) and `bazzar` (not `bazaar`) are used consistently in filenames, class names, and imports. Match the existing spelling when referencing these.
- **`file_handeler.write_file_json()`** calls `str(json.dumps(...))` — `json.dumps()` already returns a string, the extra `str()` is harmless but useless.

## Data storage

Primary storage is **SQLite** (`bazzar.db`). Schema (`bazzar_db.py`):

- `products(id, product_id)` — unique product identifiers
- `snapshots(id, timestamp_ms, product_id FK, sell_price, buy_price, sell_volume, buy_volume, sell_orders, buy_orders)` — time-series data, indexed on `(product_id, timestamp_ms)`
- `meta(key, value)` — metadata (schema version)

WAL journal mode, foreign keys enabled. Atomic batch inserts via transactions.

Legacy JSON file (`bazzar_static_file.json`) is still supported for backward compat. Migrate existing JSON data with:

```python
from bazzar_db import BazaarDB
db = BazaarDB("bazzar.db")
db.migrate_from_json("bazzar_static_file.json")
```

Legacy JSON structure:
```json
{
  "time": [epoch_ms, ...],
  "PRODUCT_ID": {
    "start_time": [index, bool],
    "sell_price": [...], "buy_price": [...],
    "sell_order": [...], "buy_order": [...],
    "buy_volume": [...], "sell_volume": [...]
  }
}
```

The `BAZAAR_COOKIE` item is hardcoded to be excluded from the GUI (see `main.py`).

## Architecture

- **`bazzar_db.py`** — SQLite database layer (`BazaarDB` class): schema, `insert_snapshot()`, `get_latest_for_all()`, `get_history()`, `migrate_from_json()`
- **`hypixel_api_class.py`** — API client with retry (urllib3 `Retry`), 15s timeout, response validation. Default mode uses `BazaarDB`; pass `db_path=None` to use legacy JSON methods.
- **`hypixel_api.py`** — Collection daemon: polls every 30s, exponential backoff on errors, proper KeyboardInterrupt handling, structured logging.
- **`main.py`** — PySide6 dashboard: queries SQLite for table + charts, dark Catppuccin theme, sortable product table with profit margin coloring, 5 chart tabs including price+SMA overlay, time-window selector (1h–All).
- **`file_handeler.py`** — Legacy JSON read/write utilities (used only for backward compat and migration).
- **`update_bazzar_file.py`** — One-shot JSON sync script (broken due to constructor args mismatch).

## Testing

Test suite (`test_hypixel_api.py`): 43 tests across:

| Suite | Count | Coverage |
|-------|-------|----------|
| `TestFileHandeler` | 5 | JSON load/write round-trips, edge cases |
| `TestBazaarDB` | 15 | SQLite CRUD, history queries, JSON migration, price changes, SMA, market summary |
| `TestHypixelApiDB` | 4 | DB-mode `save_snapshot`, fetch validation, error handling |
| `TestHypixelApiLegacy` | 11 | Legacy JSON methods (backward compat) |
| `TestHypixelApiLive` | 8 | Real API smoke tests (requires internet) |

Run: `pytest -m "not live"` (unit, no network) or `pytest -m "live"` (requires internet).

## Git workflow

**Commit and push every change.** After completing a task, stage all relevant files, write a concise commit message describing the *why* not just the *what*, commit, and push to the remote.

## No linting, formatter, or CI

This project has no linter/formatter config, no CI, and no build system.
