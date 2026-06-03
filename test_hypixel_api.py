"""Tests for bazzar_db, hypixel_api_class, file_handeler, and live API."""
import json
import os
import tempfile
import time
from unittest.mock import Mock, patch

import pytest

from bazzar_db import BazaarDB
from file_handeler import file_handeler
from hypixel_api_class import hypixel_api


# ── Mock API response helpers ─────────────────────────────────────────

def _mock_api_data(last_updated=None):
    if last_updated is None:
        last_updated = int(time.time() * 1000)
    return {
        "success": True,
        "lastUpdated": last_updated,
        "products": {
            "STONE": {
                "product_id": "STONE",
                "sell_summary": [],
                "buy_summary": [],
                "quick_status": {
                    "productId": "STONE",
                    "sellPrice": 1.5,
                    "sellVolume": 5000000,
                    "sellMovingWeek": 45000000,
                    "sellOrders": 1200,
                    "buyPrice": 1.2,
                    "buyVolume": 3000000,
                    "buyMovingWeek": 28000000,
                    "buyOrders": 800,
                },
            },
            "OAK_LOG": {
                "product_id": "OAK_LOG",
                "sell_summary": [],
                "buy_summary": [],
                "quick_status": {
                    "productId": "OAK_LOG",
                    "sellPrice": 8.3,
                    "sellVolume": 150000,
                    "sellMovingWeek": 1200000,
                    "sellOrders": 60,
                    "buyPrice": 7.1,
                    "buyVolume": 200000,
                    "buyMovingWeek": 1500000,
                    "buyOrders": 45,
                },
            },
        },
    }


@pytest.fixture
def mock_api():
    return _mock_api_data()


@pytest.fixture
def api_json():
    """Legacy JSON-mode API client (no DB)."""
    return hypixel_api(db_path=None)


@pytest.fixture
def api_db():
    """DB-mode API client using a temp SQLite file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    api = hypixel_api(db_path=path)
    yield api
    api.db.close()
    os.unlink(path)


@pytest.fixture
def tmp_json():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w") as f:
        json.dump({"dummy": True}, f)
    yield path
    os.unlink(path)


# ── file_handeler ─────────────────────────────────────────────────────

class TestFileHandeler:
    def test_load_existing_json(self, tmp_json):
        data = file_handeler.load_json_file(tmp_json)
        assert data == {"dummy": True}

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            file_handeler.load_json_file("this_file_does_not_exist_99999.json")

    def test_write_and_load_roundtrip(self, tmp_json):
        payload = {"a": 1, "b": [2, 3], "c": {"nested": True}}
        file_handeler.write_file_json(payload, tmp_json)
        result = file_handeler.load_json_file(tmp_json)
        assert result == payload

    def test_write_file_raw(self, tmp_json):
        file_handeler.write_file("hello world", tmp_json)
        with open(tmp_json, "r") as f:
            assert f.read() == "hello world"

    def test_write_file_json_no_double_str(self, tmp_json):
        data = [1, 2, 3]
        file_handeler.write_file_json(data, tmp_json)
        with open(tmp_json, "r") as f:
            raw = f.read()
        assert raw == "[1, 2, 3]"
        assert json.loads(raw) == [1, 2, 3]


# ── BazaarDB unit tests ───────────────────────────────────────────────

class TestBazaarDB:
    @pytest.fixture
    def db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db = BazaarDB(path)
        yield db
        db.close()
        os.unlink(path)

    def test_empty_db(self, db):
        assert db.get_product_ids() == []
        assert db.get_latest_for_all() == {}
        assert db.get_latest_timestamp() == 0
        assert db.get_snapshot_count() == 0
        lo, hi = db.get_time_range()
        assert lo is None and hi is None

    def test_insert_and_query(self, db):
        data = _mock_api_data()
        batch = {}
        for p in data["products"].values():
            batch[p["quick_status"]["productId"]] = p["quick_status"]
        db.insert_snapshot(data["lastUpdated"], batch)

        assert db.get_snapshot_count() == 2
        products = db.get_product_ids()
        assert "STONE" in products
        assert "OAK_LOG" in products

        latest = db.get_latest_for_all()
        assert latest["STONE"]["sell_price"] == 1.5
        assert latest["OAK_LOG"]["buy_price"] == 7.1
        assert db.get_latest_timestamp() == data["lastUpdated"]

    def test_multiple_snapshots(self, db):
        d1 = _mock_api_data(1000)
        batch1 = {p["quick_status"]["productId"]: p["quick_status"] for p in d1["products"].values()}
        db.insert_snapshot(1000, batch1)

        d2 = _mock_api_data(2000)
        d2["products"]["STONE"]["quick_status"]["sellPrice"] = 9.9
        batch2 = {p["quick_status"]["productId"]: p["quick_status"] for p in d2["products"].values()}
        db.insert_snapshot(2000, batch2)

        assert db.get_snapshot_count() == 4

        hist = db.get_history("STONE")
        assert len(hist["time"]) == 2
        assert hist["time"] == [1000, 2000]
        assert hist["sell_price"] == [1.5, 9.9]

        lo, hi = db.get_time_range()
        assert lo == 1000
        assert hi == 2000

    def test_history_fields(self, db):
        d = _mock_api_data(5000)
        batch = {p["quick_status"]["productId"]: p["quick_status"] for p in d["products"].values()}
        db.insert_snapshot(5000, batch)

        hist = db.get_history("STONE", fields=("sell_price", "buy_volume"))
        assert "sell_price" in hist
        assert "buy_volume" in hist
        assert "sell_volume" not in hist

    def test_migrate_from_json(self, db, tmp_path):
        json_path = tmp_path / "test.json"
        data = {
            "time": [1000, 2000],
            "STONE": {
                "start_time": [0, True],
                "sell_price": [1.0, 2.0],
                "buy_price": [0.8, 1.8],
                "sell_order": [10, 20],
                "buy_order": [5, 15],
                "buy_volume": [100, 200],
                "sell_volume": [200, 300],
            },
        }
        json_path.write_text(json.dumps(data))

        count = db.migrate_from_json(str(json_path))
        assert count == 2
        products = db.get_product_ids()
        assert products == ["STONE"]  # BAZAAR_COOKIE excluded

        hist = db.get_history("STONE")
        assert hist["time"] == [1000, 2000]
        assert hist["sell_price"] == [1.0, 2.0]

    def test_migrate_skips_bazaar_cookie(self, db, tmp_path):
        json_path = tmp_path / "test.json"
        data = {
            "time": [1000],
            "BAZAAR_COOKIE": {
                "sell_price": [999],
                "buy_price": [888],
                "sell_order": [0],
                "buy_order": [0],
                "buy_volume": [0],
                "sell_volume": [0],
            },
            "STONE": {
                "sell_price": [1.5],
                "buy_price": [1.2],
                "sell_order": [10],
                "buy_order": [5],
                "buy_volume": [100],
                "sell_volume": [200],
            },
        }
        json_path.write_text(json.dumps(data))
        db.migrate_from_json(str(json_path))
        assert "BAZAAR_COOKIE" not in db.get_product_ids()

    def test_vacuum(self, db):
        d = _mock_api_data(9999)
        batch = {p["quick_status"]["productId"]: p["quick_status"] for p in d["products"].values()}
        db.insert_snapshot(9999, batch)
        db.vacuum()

    def test_close(self, db):
        db.close()

    def test_price_change_positive(self, db):
        d1 = _mock_api_data(1000)
        batch1 = {p["quick_status"]["productId"]: p["quick_status"] for p in d1["products"].values()}
        db.insert_snapshot(1000, batch1)

        d2 = _mock_api_data(2000)
        d2["products"]["STONE"]["quick_status"]["sellPrice"] = 3.0
        batch2 = {p["quick_status"]["productId"]: p["quick_status"] for p in d2["products"].values()}
        db.insert_snapshot(2000, batch2)

        abs_c, pct_c = db.get_price_change("STONE", "sell_price", lookback=1)
        assert abs_c == 1.5
        assert pct_c == 100.0

    def test_price_change_unchanged(self, db):
        d1 = _mock_api_data(1000)
        batch1 = {p["quick_status"]["productId"]: p["quick_status"] for p in d1["products"].values()}
        db.insert_snapshot(1000, batch1)
        db.insert_snapshot(2000, batch1)
        abs_c, pct_c = db.get_price_change("OAK_LOG", "sell_price", lookback=1)
        assert abs_c == 0
        assert pct_c == 0

    def test_price_change_insufficient_data(self, db):
        d = _mock_api_data(1000)
        batch = {p["quick_status"]["productId"]: p["quick_status"] for p in d["products"].values()}
        db.insert_snapshot(1000, batch)
        abs_c, pct_c = db.get_price_change("STONE", lookback=1)
        assert abs_c == 0
        assert pct_c == 0

    def test_summary_stats(self, db):
        d1 = _mock_api_data(1000)
        d1["products"]["STONE"]["quick_status"]["sellPrice"] = 1.0
        batch1 = {p["quick_status"]["productId"]: p["quick_status"] for p in d1["products"].values()}
        db.insert_snapshot(1000, batch1)

        d2 = _mock_api_data(2000)
        d2["products"]["STONE"]["quick_status"]["sellPrice"] = 3.0
        batch2 = {p["quick_status"]["productId"]: p["quick_status"] for p in d2["products"].values()}
        db.insert_snapshot(2000, batch2)

        stats = db.get_summary_stats("STONE", "sell_price")
        assert stats["min"] == 1.0
        assert stats["max"] == 3.0
        assert stats["mean"] == 2.0
        assert stats["latest"] == 3.0
        assert stats["count"] == 2

    def test_get_all_price_changes(self, db):
        d1 = _mock_api_data(1000)
        batch1 = {p["quick_status"]["productId"]: p["quick_status"] for p in d1["products"].values()}
        db.insert_snapshot(1000, batch1)

        d2 = _mock_api_data(2000)
        d2["products"]["STONE"]["quick_status"]["sellPrice"] = 2.5
        d2["products"]["OAK_LOG"]["quick_status"]["sellPrice"] = 10.0
        batch2 = {p["quick_status"]["productId"]: p["quick_status"] for p in d2["products"].values()}
        db.insert_snapshot(2000, batch2)

        changes = db.get_all_price_changes("sell_price", lookback=1)
        assert changes["STONE"][1] > 0
        assert "OAK_LOG" in changes
        assert changes["OAK_LOG"][1] > 0

    def test_moving_average(self, db):
        for i in range(1, 7):
            d = _mock_api_data(i * 1000)
            d["products"]["STONE"]["quick_status"]["sellPrice"] = float(i * 10)
            db.insert_snapshot(i * 1000, {
                "STONE": d["products"]["STONE"]["quick_status"],
            })

        sma = db.get_moving_average("STONE", "sell_price", window=3)
        assert len(sma) == 4
        assert sma[0][0] == 3000
        assert sma[0][1] == 20.0  # (10+20+30)/3
        assert sma[1][1] == 30.0  # (20+30+40)/3

    def test_moving_average_insufficient(self, db):
        d = _mock_api_data(1000)
        db.insert_snapshot(1000, {
            "STONE": d["products"]["STONE"]["quick_status"],
        })
        assert db.get_moving_average("STONE", "sell_price", window=5) == []

    def test_market_summary_empty(self, db):
        ms = db.get_market_summary()
        assert ms["total_products"] == 0

    def test_market_summary(self, db):
        d1 = _mock_api_data(1000)
        batch1 = {p["quick_status"]["productId"]: p["quick_status"] for p in d1["products"].values()}
        db.insert_snapshot(1000, batch1)
        ms = db.get_market_summary()
        assert ms["total_products"] == 2
        assert ms["total_sell_volume"] > 0


# ── hypixel_api (DB mode) unit tests ─────────────────────────────────

class TestHypixelApiDB:
    @pytest.fixture
    def db_path(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    def test_save_snapshot(self, api_db, mock_api):
        with patch("hypixel_api_class._get_session") as mock_sess:
            mock_sess.return_value.get.return_value = Mock()
            mock_sess.return_value.get.return_value.json.return_value = mock_api
            mock_sess.return_value.get.return_value.raise_for_status = Mock()

            data = hypixel_api.fetch()
            count = api_db.save_snapshot(data)
            assert count == 2

            latest = api_db.db.get_latest_for_all()
            assert "STONE" in latest
            assert latest["STONE"]["sell_price"] == 1.5
            assert latest["OAK_LOG"]["buy_volume"] == 200000

    def test_save_snapshot_no_db(self):
        api = hypixel_api(db_path=None)
        with pytest.raises(RuntimeError, match="No database configured"):
            api.save_snapshot({})

    def test_fetch_raises_on_http_error(self):
        with patch("hypixel_api_class._get_session") as mock_sess:
            import requests as req
            mock_resp = Mock(spec=req.Response)
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = req.HTTPError("500 Server Error")
            mock_sess.return_value.get.return_value = mock_resp
            with pytest.raises(req.HTTPError):
                hypixel_api.fetch()

    def test_fetch_invalid_json_raises(self):
        with patch("hypixel_api_class._get_session") as mock_sess:
            mock_resp = Mock()
            mock_resp.json.return_value = "not a dict"
            mock_resp.raise_for_status = Mock()
            mock_sess.return_value.get.return_value = mock_resp
            with pytest.raises(ValueError, match="not a JSON object"):
                hypixel_api.fetch()


# ── hypixel_api (legacy JSON mode) unit tests ─────────────────────────

class TestHypixelApiLegacy:
    def test_get_information(self, api_json, mock_api):
        with patch("hypixel_api_class._get_session") as mock_sess:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_api
            mock_resp.raise_for_status = Mock()
            mock_sess.return_value.get.return_value = mock_resp
            result = api_json.get_information("http://fake.url")
            assert result["success"] is True
            assert "STONE" in result["products"]
            mock_sess.return_value.get.assert_called_once_with("http://fake.url", timeout=15)

    def test_create_dict_name_structure(self, api_json, mock_api):
        result = api_json.create_dict_name(mock_api)
        assert "time" in result
        assert result["time"] == []
        assert "STONE" in result
        stone = result["STONE"]
        assert stone["start_time"] == [9999, False]
        for key in ("sell_price", "buy_price", "sell_order",
                    "buy_order", "buy_volume", "sell_volume"):
            assert key in stone
            assert isinstance(stone[key], list)
            assert len(stone[key]) == 0

    def test_create_dict_name_excludes_meta_keys(self, api_json, mock_api):
        result = api_json.create_dict_name(mock_api)
        assert "success" not in result
        assert "lastUpdated" not in result

    def test_update_price_appends_correctly(self, api_json, mock_api, tmp_json):
        api_json.create_bazzar_file(mock_api, tmp_json)
        updated = _mock_api_data(1649000000000)
        updated["products"]["STONE"]["quick_status"]["sellPrice"] = 2.0
        updated["products"]["OAK_LOG"]["quick_status"]["sellPrice"] = 9.0
        api_json.update_price(updated, tmp_json)
        data = file_handeler.load_json_file(tmp_json)
        assert len(data["time"]) == 1
        assert data["time"][0] == 1649000000000
        assert data["STONE"]["sell_price"] == [2.0]

        updated2 = _mock_api_data(1649000030000)
        updated2["products"]["STONE"]["quick_status"]["sellPrice"] = 2.5
        updated2["products"]["OAK_LOG"]["quick_status"]["sellPrice"] = 8.5
        api_json.update_price(updated2, tmp_json)
        data = file_handeler.load_json_file(tmp_json)
        assert len(data["time"]) == 2
        assert data["STONE"]["sell_price"] == [2.0, 2.5]
        assert data["OAK_LOG"]["sell_price"] == [9.0, 8.5]

    def test_update_price_all_fields(self, api_json, mock_api, tmp_json):
        api_json.create_bazzar_file(mock_api, tmp_json)
        api_json.update_price(mock_api, tmp_json)
        data = file_handeler.load_json_file(tmp_json)
        stone = data["STONE"]
        assert stone["sell_price"] == [1.5]
        assert stone["buy_price"] == [1.2]
        for key in ("sell_order", "buy_order", "buy_volume", "sell_volume"):
            assert isinstance(stone[key][0], float)

    def test_update_dict_key_adds_new_product(self, api_json, tmp_json):
        initial = {"time": [1649000000000],
                   "STONE": {"start_time": [0, True], "sell_price": [1.5],
                             "buy_price": [1.2], "sell_order": [1200],
                             "buy_order": [800], "buy_volume": [3e6],
                             "sell_volume": [5e6]}}
        file_handeler.write_file_json(initial, tmp_json)
        new_response = {"products": {
            "STONE": {},
            "OAK_LOG": {"quick_status": {"productId": "OAK_LOG"}},
        }}
        api_json.update_dict_key(new_response, tmp_json)
        data = file_handeler.load_json_file(tmp_json)
        assert "OAK_LOG" in data
        assert data["OAK_LOG"]["start_time"] == [9999, False]

    def test_update_dict_key_preserves_existing(self, api_json, tmp_json):
        initial = {"time": [1649000000000],
                   "STONE": {"start_time": [0, True], "sell_price": [1.5],
                             "buy_price": [1.2], "sell_order": [1200],
                             "buy_order": [800], "buy_volume": [3e6],
                             "sell_volume": [5e6]}}
        file_handeler.write_file_json(initial, tmp_json)
        api_json.update_dict_key(
            {"products": {"STONE": {"quick_status": {"productId": "STONE"}}}},
            tmp_json,
        )
        data = file_handeler.load_json_file(tmp_json)
        assert data["STONE"]["sell_price"] == [1.5]

    def test_create_start_time(self, api_json, mock_api, tmp_json):
        api_json.create_bazzar_file(mock_api, tmp_json)
        api_json.update_price(mock_api, tmp_json)
        api_json.create_start_time(tmp_json, mock_api)
        data = file_handeler.load_json_file(tmp_json)
        for product in ("STONE", "OAK_LOG"):
            assert data[product]["start_time"][1] is True
            assert isinstance(data[product]["start_time"][0], int)

    def test_update_price_missing_product(self, api_json, tmp_json):
        initial = {"time": [1649000000000],
                   "STONE": {"start_time": [0, True], "sell_price": [],
                             "buy_price": [], "sell_order": [],
                             "buy_order": [], "buy_volume": [],
                             "sell_volume": []}}
        file_handeler.write_file_json(initial, tmp_json)
        with pytest.raises(KeyError):
            api_json.update_price(_mock_api_data(), tmp_json)

    def test_create_bazzar_file(self, api_json, mock_api, tmp_json):
        api_json.create_bazzar_file(mock_api, tmp_json)
        with open(tmp_json, "r") as f:
            parsed = json.load(f)
        assert "time" in parsed
        assert "STONE" in parsed

    def test_empty_products_response(self, api_json):
        empty = {"success": True, "lastUpdated": 1, "products": {}}
        result = api_json.create_dict_name(empty)
        assert result == {"time": []}


# ── Live API tests ────────────────────────────────────────────────────

@pytest.mark.live
class TestHypixelApiLive:
    def test_api_reachable_and_returns_success(self):
        data = hypixel_api.fetch()
        assert data.get("success") is True

    def test_api_has_expected_top_level_keys(self):
        data = hypixel_api.fetch()
        for key in ("success", "lastUpdated", "products"):
            assert key in data

    def test_api_last_updated_is_recent(self):
        data = hypixel_api.fetch()
        now_ms = int(time.time() * 1000)
        lag = now_ms - data["lastUpdated"]
        assert 0 <= lag < 5 * 60 * 1000

    def test_api_product_has_quick_status(self):
        data = hypixel_api.fetch()
        products = data["products"]
        assert len(products) > 0
        first = next(iter(products.values()))
        qs = first.get("quick_status")
        assert qs is not None
        for field in ("productId", "sellPrice", "buyPrice", "sellVolume",
                      "buyVolume", "sellOrders", "buyOrders"):
            assert field in qs

    def test_create_dict_name_integration(self):
        data = hypixel_api.fetch()
        built = hypixel_api.create_dict_name(data)
        assert len(built) == len(data["products"]) + 1
        for p in data["products"].values():
            pid = p["quick_status"]["productId"]
            assert pid in built

    def test_save_and_query_round_trip(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        api = None
        try:
            api = hypixel_api(db_path=path)

            with patch("hypixel_api_class._get_session") as mock_sess:
                mock_resp = Mock()
                data = _mock_api_data()
                mock_resp.json.return_value = data
                mock_resp.raise_for_status = Mock()
                mock_sess.return_value.get.return_value = mock_resp

                fetched = hypixel_api.fetch()
                count = api.save_snapshot(fetched)
                assert count == 2

            latest = api.db.get_latest_for_all()
            assert latest["STONE"]["sell_price"] == 1.5
            hist = api.db.get_history("STONE", fields=("sell_price",))
            assert hist["sell_price"] == [1.5]
        finally:
            if api and api.db:
                api.db.close()
            os.unlink(path)
