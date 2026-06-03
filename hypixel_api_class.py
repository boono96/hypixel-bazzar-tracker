"""Hypixel Bazaar API client with retry, validation, and DB-backed storage."""
import json
import logging
import os
import time
import warnings

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bazzar_db import BazaarDB
from file_handeler import file_handeler

logger = logging.getLogger(__name__)

BAZAAR_URL = "https://api.hypixel.net/skyblock/bazaar"

REQUIRED_PRODUCT_FIELDS = (
    "sellPrice", "buyPrice", "sellVolume", "buyVolume",
    "sellOrders", "buyOrders",
)

_SESSION = None


def _get_session(api_key=None):
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=2)
        _SESSION.mount("https://", adapter)
        _SESSION.mount("http://", adapter)

    headers = {"User-Agent": "hypixel-bazaar-tracker/2.0"}
    if api_key:
        headers["API-Key"] = api_key
    _SESSION.headers.update(headers)
    return _SESSION


class hypixel_api:
    """Fetch and store Hypixel SkyBlock Bazaar data.

    By default, stores snapshots into a local SQLite database (``bazzar.db``).
    Pass ``db_path=None`` to use the legacy JSON-file backend instead.

    *api_key* is sent as the ``API-Key`` HTTP header.  If ``None`` the
    ``HYPIXEL_API_KEY`` environment variable is used as a fallback.
    """

    def __init__(self, db_path="bazzar.db", api_key=None):
        self.db: BazaarDB | None = BazaarDB(db_path) if db_path else None
        self.api_key = api_key or os.environ.get("HYPIXEL_API_KEY")

    # ── API fetching ──────────────────────────────────────────────────

    def fetch(self, url=BAZAAR_URL, timeout=15):
        """GET *url* with retry and timeout; return parsed JSON.

        Raises ``requests.RequestException`` on connectivity failure.
        Raises ``ValueError`` if the response payload is structurally invalid.
        """
        session = _get_session(self.api_key)
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()

        # Log rate-limit info if present
        remaining = resp.headers.get("RateLimit-Remaining")
        if remaining is not None:
            logger.debug("RateLimit-Remaining: %s", remaining)

        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("API response is not a JSON object")
        if not data.get("success"):
            cause = data.get("cause", "unknown")
            logger.warning("API returned success=False · cause: %s", cause)
        if "products" not in data:
            raise ValueError("API response missing 'products' key")
        if "lastUpdated" not in data:
            raise ValueError("API response missing 'lastUpdated' key")

        # Quick validation: at least one product has the expected shape
        products = data["products"]
        if not isinstance(products, dict) or len(products) == 0:
            logger.warning("API returned empty products dict")

        return data

    get_information = fetch  # legacy alias

    # ── static convenience (no API key) ───────────────────────────────

    @staticmethod
    def fetch_public(url=BAZAAR_URL, timeout=15):
        """Fetch without an API key — convenience for quick checks."""
        session = _get_session(None)
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    # ── DB storage ────────────────────────────────────────────────────

    def save_snapshot(self, api_data):
        """Persist one API response into the database."""
        if self.db is None:
            raise RuntimeError("No database configured (db_path=None)")

        ts = api_data["lastUpdated"]
        batch = {}
        for product in api_data["products"].values():
            qs = product.get("quick_status", {})
            pid = qs.get("productId")
            if not pid:
                continue
            batch[pid] = {
                field: float(f"{qs.get(field, 0):.2f}")
                for field in REQUIRED_PRODUCT_FIELDS
            }
        self.db.insert_snapshot(ts, batch)
        return len(batch)

    # ── Legacy JSON-file methods (kept for backward compat) ───────────

    def update_price(self, info, file):
        """Legacy: append one snapshot to a JSON file."""
        warnings.warn("update_price() is deprecated; use save_snapshot() + DB",
                      DeprecationWarning, stacklevel=2)
        if self.db:
            self.save_snapshot(info)
            return
        f = file_handeler.load_json_file(file)
        f['time'].append(info['lastUpdated'])
        for i in info['products'].values():
            qs = i['quick_status']
            pid = qs['productId']
            f[pid]['sell_price'].append(float(f"{qs.get('sellPrice', 0):.2f}"))
            f[pid]['buy_price'].append(float(f"{qs.get('buyPrice', 0):.2f}"))
            f[pid]['sell_order'].append(float(f"{qs.get('sellOrders', 0):.2f}"))
            f[pid]['buy_order'].append(float(f"{qs.get('buyOrders', 0):.2f}"))
            f[pid]['buy_volume'].append(float(f"{qs.get('buyVolume', 0):.2f}"))
            f[pid]['sell_volume'].append(float(f"{qs.get('sellVolume', 0):.2f}"))
        with open(file, 'w') as c:
            json.dump(f, c)

    @staticmethod
    def create_dict_name(information):
        warnings.warn("create_dict_name() is a legacy JSON helper",
                      DeprecationWarning, stacklevel=2)
        dictinfo = {'time': []}
        for i in information['products'].values():
            pid = i['quick_status']['productId']
            dictinfo[pid] = {
                'start_time': [9999, False],
                'sell_price': [], 'buy_price': [],
                'sell_order': [], 'buy_order': [],
                'buy_volume': [], 'sell_volume': [],
            }
        return dictinfo

    @staticmethod
    def update_dict_key(information, file):
        warnings.warn("update_dict_key() is a legacy JSON helper",
                      DeprecationWarning, stacklevel=2)
        f = file_handeler.load_json_file(file)
        for i, j in information['products'].items():
            if i != 'time':
                if i in f:
                    logger.debug("%s already exists", i)
                else:
                    f[j['quick_status']['productId']] = {
                        'start_time': [9999, False],
                        'sell_price': [], 'buy_price': [],
                        'sell_order': [], 'buy_order': [],
                        'buy_volume': [], 'sell_volume': [],
                    }
        file_handeler.write_file_json(f, file)

    @staticmethod
    def create_start_time(file, info):
        warnings.warn("create_start_time() is a legacy JSON helper",
                      DeprecationWarning, stacklevel=2)
        f = file_handeler.load_json_file(file)
        for i in f.keys():
            if i != 'time':
                if not f[i]['start_time'][1]:
                    f[i]['start_time'] = [
                        f['time'].index(info['lastUpdated']), True
                    ]
        file_handeler.write_file_json(f, file)

    @staticmethod
    def create_bazzar_file(information, file):
        warnings.warn("create_bazzar_file() is a legacy JSON helper",
                      DeprecationWarning, stacklevel=2)
        dict_info = hypixel_api.create_dict_name(information)
        with open(file, 'w') as f:
            json.dump(dict_info, f)

    @staticmethod
    def check_if_exit(list_info, item):
        warnings.warn("check_if_exit() is unused and broken",
                      DeprecationWarning, stacklevel=2)
        for i in list_info.keys():
            if i != 'time':
                if item in list_info:
                    return True
                else:
                    return False

    @staticmethod
    def get_static_data(names):
        warnings.warn("get_static_data() is a legacy JSON helper; use BazaarDB",
                      DeprecationWarning, stacklevel=2)
        info = file_handeler.load_json_file('bazzar_static_file.json')
        return info[names]
