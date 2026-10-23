"""Read-only Sheet access tests (PR2 task 3.1). Fakes only, zero live network."""
import pytest

import sheet_reader


ROWS = [
    {"fecha_salida": "2026-10-01", "planta_despacho": "PLANTA A",
     "variedad": "SC", "codigo_pallet": "P-001"},
    {"fecha_salida": "2026-10-03", "planta_despacho": "PLANTA B",
     "variedad": "TM", "codigo_pallet": "P-002"},
]


class _FakeWorksheet:
    def __init__(self, records, calls):
        self._records = records
        self._calls = calls

    def get_all_records(self):
        self._calls["reads"] += 1
        return [dict(r) for r in self._records]


class _FakeSpreadsheet:
    def __init__(self, records, calls, seen):
        self._records = records
        self._calls = calls
        self._seen = seen

    def worksheet(self, name):
        self._seen["tab"] = name
        return _FakeWorksheet(self._records, self._calls)


class _FakeClient:
    def __init__(self, records, calls, seen):
        self._records = records
        self._calls = calls
        self._seen = seen

    def open_by_key(self, key):
        self._seen["key"] = key
        return _FakeSpreadsheet(self._records, self._calls, self._seen)


@pytest.fixture()
def fake_sheet(monkeypatch):
    calls = {"auth": 0, "reads": 0}
    seen = {}
    records = {"rows": list(ROWS)}

    def _authorize(_creds):
        calls["auth"] += 1
        return _FakeClient(records["rows"], calls, seen)

    monkeypatch.setattr(sheet_reader.gspread, "authorize", _authorize)
    monkeypatch.setattr(sheet_reader, "_load_creds", lambda: object())
    sheet_reader._cache.update(ts=0.0, data=None)
    return calls, seen, records


def test_read_all_returns_verbatim_rows_from_pallet_tab(fake_sheet):
    calls, seen, _ = fake_sheet

    rows = sheet_reader.read_all(force=True)

    assert rows == ROWS
    assert seen["key"] == "1Svr0a4lwiw1b4Eujr_aMJwfd3N1kbVfSTa1IjzBMbQ4"
    assert seen["tab"] == "Pallets exportados"
    assert calls["reads"] == 1


def test_read_all_serves_cache_without_second_sheet_call(fake_sheet):
    calls, _, _ = fake_sheet

    first = sheet_reader.read_all(force=True)
    second = sheet_reader.read_all()

    assert second == first
    assert calls["reads"] == 1


def test_refresh_forces_reread_and_advances_stamp(fake_sheet, monkeypatch):
    calls, _, records = fake_sheet
    sheet_reader.read_all(force=True)
    old_stamp = sheet_reader.last_updated()
    assert old_stamp != ""

    records["rows"].append(
        {"fecha_salida": "2026-10-05", "planta_despacho": "PLANTA A",
         "variedad": "SC", "codigo_pallet": "P-003"})
    monkeypatch.setattr(sheet_reader.time, "time",
                        lambda: sheet_reader._cache["ts"] + 3600.0)

    rows = sheet_reader.refresh()

    assert calls["reads"] == 2
    assert len(rows) == 3
    assert sheet_reader.last_updated() != old_stamp


def test_empty_tab_returns_no_rows_but_still_stamps(fake_sheet):
    _, _, records = fake_sheet
    records["rows"].clear()

    rows = sheet_reader.read_all(force=True)

    assert rows == []
    assert sheet_reader.last_updated() != ""


def test_cache_expires_after_ttl(fake_sheet, monkeypatch):
    calls, _, _ = fake_sheet
    sheet_reader.read_all(force=True)
    monkeypatch.setattr(
        sheet_reader.time, "time",
        lambda: sheet_reader._cache["ts"] + sheet_reader.CACHE_TTL + 1)

    sheet_reader.read_all()

    assert calls["reads"] == 2


def test_reader_exposes_no_write_method():
    for name in ("write_matrix", "upsert", "update", "delete_rows",
                 "add_worksheet"):
        assert not hasattr(sheet_reader, name), name
    source = open(__file__.replace("test_sheet_reader.py",
                                   "sheet_reader.py"),
                  encoding="utf-8").read()
    assert "def write" not in source
    assert ".update(" not in source


def test_missing_credentials_fails_naming_the_variable(monkeypatch):
    monkeypatch.delenv("GOOGLE_CREDENTIALS_JSON", raising=False)
    monkeypatch.setattr(sheet_reader, "TOKEN_PATH",
                        "definitely-missing-token.json")

    with pytest.raises(SystemExit, match="GOOGLE_CREDENTIALS_JSON"):
        sheet_reader._load_creds()


def test_reader_source_has_no_erp_references():
    source = open(__file__.replace("test_sheet_reader.py",
                                   "sheet_reader.py"),
                  encoding="utf-8").read().lower()
    for marker in ("gestagro", "iniciar_sesion", "erp", "packing",
                   "p_personal_id", "truststore"):
        assert marker not in source, marker
