"""Per-tab Sheet reads: cache, force, missing tab. No network."""
import pytest

import sheet_reader

ROWS = [{"fecha": "2026-10-22", "hora": "18", "planta": "P1",
         "variedad": "TM", "jabas": "10"}]


class FakeWorksheet:
    def __init__(self, rows):
        self.rows = rows

    def get_all_records(self):
        return self.rows


class FakeBook:
    def __init__(self, tabs, opened):
        self.tabs = tabs
        self.opened = opened

    def worksheet(self, name):
        if name not in self.tabs:
            raise sheet_reader.gspread.WorksheetNotFound(name)
        return FakeWorksheet(self.tabs[name])


class FakeClient:
    def __init__(self, tabs, opened):
        self.book = FakeBook(tabs, opened)
        self.opened = opened

    def open_by_key(self, key):
        self.opened.append(key)
        return self.book


@pytest.fixture
def opened(monkeypatch):
    calls = []
    tabs = {"Recepcion jabas": ROWS}
    monkeypatch.setattr(sheet_reader, "_load_creds", lambda: object())
    monkeypatch.setattr(sheet_reader.gspread, "authorize",
                        lambda creds: FakeClient(tabs, calls))
    sheet_reader._tab_cache.clear()
    yield calls
    sheet_reader._tab_cache.clear()


def test_read_tab_returns_rows_and_caches(opened):
    assert sheet_reader.read_tab("Recepcion jabas") == ROWS
    assert sheet_reader.read_tab("Recepcion jabas") == ROWS
    assert len(opened) == 1


def test_force_bypasses_the_cache(opened):
    sheet_reader.read_tab("Recepcion jabas")
    sheet_reader.read_tab("Recepcion jabas", force=True)
    assert len(opened) == 2


def test_missing_tab_reads_empty_instead_of_failing(opened):
    assert sheet_reader.read_tab("Produccion cajas") == []
    assert len(opened) == 1


def test_tab_updated_is_empty_until_the_tab_is_read(opened):
    assert sheet_reader.tab_updated("Recepcion jabas") == ""
    sheet_reader.read_tab("Recepcion jabas")
    assert sheet_reader.tab_updated("Recepcion jabas")
