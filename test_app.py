"""Dashboard route tests (PR2 task 3.2). Flask test client + fake reader."""
import pytest

import app
import sheet_reader


ROWS = [
    {"fecha_salida": "2026-10-01", "planta_despacho": "PLANTA A",
     "variedad": "SC", "cliente": "Cliente X", "codigo_pallet": "P-001",
     "cantidad_cajas_produccion": 100, "cantidad_cajas_equivalentes": 95.5,
     "cantidad_pallets": 2},
    {"fecha_salida": "2026-10-03", "planta_despacho": "PLANTA B",
     "variedad": "TM", "cliente": "Cliente Y", "codigo_pallet": "P-002",
     "cantidad_cajas_produccion": 200, "cantidad_cajas_equivalentes": 190.0,
     "cantidad_pallets": 4},
    {"fecha_salida": "2026-10-05", "planta_despacho": "PLANTA A",
     "variedad": "SC", "cliente": "Cliente X", "codigo_pallet": "P-003",
     "cantidad_cajas_produccion": 50, "cantidad_cajas_equivalentes": 48.0,
     "cantidad_pallets": 1},
]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(sheet_reader, "read_all",
                        lambda force=False: [dict(r) for r in ROWS])
    monkeypatch.setattr(sheet_reader, "refresh",
                        lambda: [dict(r) for r in ROWS])
    monkeypatch.setattr(sheet_reader, "last_updated",
                        lambda: "2026-10-11 12:00:00")
    app.app.config["TESTING"] = True
    return app.app.test_client()


def test_index_renders_spanish_ui_and_stamp(client):
    res = client.get("/")

    assert res.status_code == 200
    html = res.get_data(as_text=True)
    for label in ("Dashboard PCP", "Desde", "Hasta", "Planta",
                  "Variedad", "Actualizar", "ltima actualizaci"):
        assert label in html, label
    assert "chart.umd.min.js" in html  # Chart.js parity with balance/


def test_index_states_hourly_cache_and_daily_writer(client):
    res = client.get("/")

    html = res.get_data(as_text=True)
    assert "1 hora" in html
    assert "7:00 am" in html
    assert "Actualizar" in html


def test_api_pallets_filters_by_date_range(client):
    res = client.get("/api/pallets?desde=2026-10-02&hasta=2026-10-04")

    assert res.status_code == 200
    body = res.get_json()
    assert [r["codigo_pallet"] for r in body["rows"]] == ["P-002"]
    assert body["headers"][0] == "fecha_salida"  # verbatim, never renamed
    assert "fecha_salida" in body["headers"]
    assert body["ultima_actualizacion"] == "2026-10-11 12:00:00"


def test_api_pallets_filters_by_planta_and_variedad(client):
    res = client.get("/api/pallets?planta=PLANTA A&variedad=SC")

    body = res.get_json()
    assert [r["codigo_pallet"] for r in body["rows"]] == ["P-001", "P-003"]
    assert body["summary"]["filas"] == 2
    assert body["summary"]["cajas_produccion"] == 150
    assert body["summary"]["cantidad_pallets"] == 3


def test_api_pallets_empty_window_returns_headers_and_zero_summary(client):
    res = client.get("/api/pallets?desde=2026-11-01&hasta=2026-11-30")

    body = res.get_json()
    assert body["rows"] == []
    assert "fecha_salida" in body["headers"]
    assert body["summary"] == {"filas": 0, "cajas_produccion": 0,
                               "cajas_equivalentes": 0.0,
                               "cantidad_pallets": 0}


def test_api_pallets_summary_totals_match_fake_rows(client):
    res = client.get("/api/pallets")

    body = res.get_json()
    assert body["summary"]["filas"] == 3
    assert body["summary"]["cajas_produccion"] == 350
    assert body["summary"]["cajas_equivalentes"] == pytest.approx(333.5)
    assert body["summary"]["cantidad_pallets"] == 7


def test_api_pallets_open_ended_range_keeps_everything_after_desde(client):
    res = client.get("/api/pallets?desde=2026-10-03")

    assert [r["codigo_pallet"] for r in res.get_json()["rows"]] == [
        "P-002", "P-003"]


def test_summary_tolerates_blank_and_formatted_numbers(monkeypatch):
    odd = [{"fecha_salida": "2026-10-01", "planta_despacho": "PLANTA A",
            "variedad": "SC", "codigo_pallet": "P-009",
            "cantidad_cajas_produccion": None,
            "cantidad_cajas_equivalentes": "",
            "cantidad_pallets": "1,200"}]
    monkeypatch.setattr(sheet_reader, "read_all",
                        lambda force=False: [dict(r) for r in odd])
    monkeypatch.setattr(sheet_reader, "last_updated",
                        lambda: "2026-10-11 12:00:00")
    app.app.config["TESTING"] = True
    test_client = app.app.test_client()

    body = test_client.get("/api/pallets").get_json()

    assert body["summary"]["cajas_produccion"] == 0
    assert body["summary"]["cajas_equivalentes"] == 0.0
    assert body["summary"]["cantidad_pallets"] == 1200


def test_api_meta_ignores_blank_labels(monkeypatch):
    odd = [{"fecha_salida": "2026-10-01", "codigo_pallet": "P-009"}]
    monkeypatch.setattr(sheet_reader, "read_all",
                        lambda force=False: [dict(r) for r in odd])
    monkeypatch.setattr(sheet_reader, "last_updated",
                        lambda: "2026-10-11 12:00:00")
    app.app.config["TESTING"] = True
    test_client = app.app.test_client()

    body = test_client.get("/api/meta").get_json()

    assert body["fechas"] == ["2026-10-01"]
    assert body["plantas"] == []
    assert body["variedades"] == []
def test_api_meta_returns_spanish_filter_options(client):
    res = client.get("/api/meta")

    assert res.status_code == 200
    body = res.get_json()
    assert body["fechas"] == ["2026-10-01", "2026-10-03", "2026-10-05"]
    assert body["plantas"] == ["PLANTA A", "PLANTA B"]
    assert body["variedades"] == ["SC", "TM"]


def test_refresh_rereads_sheet_and_returns_new_stamp(monkeypatch):
    calls = {"reads": 0}
    stamps = {"current": "2026-10-11 12:00:00"}

    def _read(force=False):
        if force:
            calls["reads"] += 1
        return [dict(r) for r in ROWS]

    monkeypatch.setattr(sheet_reader, "read_all", _read)
    monkeypatch.setattr(sheet_reader, "refresh",
                        lambda: _read(force=True))
    monkeypatch.setattr(sheet_reader, "last_updated",
                        lambda: stamps["current"])
    app.app.config["TESTING"] = True
    test_client = app.app.test_client()

    before = test_client.get("/api/pallets").get_json()
    assert calls["reads"] == 0  # served from cache, no forced re-read

    stamps["current"] = "2026-10-11 12:30:00"
    res = test_client.post("/api/refresh")

    assert res.status_code == 200
    body = res.get_json()
    assert calls["reads"] == 1
    assert body["filas"] == 3
    assert body["ultima_actualizacion"] == "2026-10-11 12:30:00"
    assert body["ultima_actualizacion"] != before["ultima_actualizacion"]
