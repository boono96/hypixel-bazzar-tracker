# AGENTS.md

## Project summary

Hypixel SkyBlock Bazaar price tracker. Polls `https://api.hypixel.net/skyblock/bazaar` every 30s, stores time-series data in a single JSON file, and provides a PySide6+matplotlib dashboard GUI for graphing price/volume/order trends with sortable table, search, and embedded charts.

## Commands

```
python hypixel_api.py    # background data collector (infinite loop)
python main.py           # PySide6 dashboard GUI
python update_bazzar_file.py  # one-shot manual update (BROKEN, see below)
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
- **`hypixel_api.py` has a dangerous bare except.** The entire `main()` is wrapped in `while True: try: main() except Exception: pass`. This swallows `KeyboardInterrupt`, making the script hard to stop. Recommend replacing with `except Exception` that at least re-raises `KeyboardInterrupt`.
- **Persistent spelling typos** — `file_handeler` (not `file_handler`) and `bazzar` (not `bazaar`) are used consistently in filenames, class names, and imports. Match the existing spelling when referencing these.
- **`file_handeler.write_file_json()`** calls `str(json.dumps(...))` — `json.dumps()` already returns a string, the extra `str()` is harmless but useless.

## Data format

`bazzar_static_file.json` is a single-line (no indentation) JSON file. Avoid reading it with editors expecting multi-line formatting.

Structure:
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

`start_time[0]` is an index into the global `time` list marking when tracking first started for that product. The `BAZAAR_COOKIE` item is hardcoded to be excluded from the GUI (see `main.py`).

## No tests, linting, or CI

This project has no test suite, no linter/formatter config, no CI, and no build system.
