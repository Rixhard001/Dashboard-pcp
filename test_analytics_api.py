"""Analytics endpoint tests (PR2b task 2). Flask test client + fake reader."""
import pytest

import app
import sheet_reader


ROWS = [
    {"fecha_salida": "2026-10-01", "contenedor": "C-001",
     "pallet_id": "PAL-001", "codigo_pallet": "COD-001",
     "pais_destino": "PAIS X", "puerto_destino": "PUERTO X",
     "formato": "FORMATO A", "planta_despacho": "PLANTA A",
     "variedad": "SC",
     "cantidad_cajas_produccion": 100,
     "cantidad_cajas_equivalentes": 95.5, "cantidad_pallets": 2},
    # Same pallet repeats across lote rows: pallet count stays 1, not 2.
    {"fecha_salida": "2026-10-01", "contenedor": "C-001",
     "pallet_id": "PAL-001", "codigo_pallet": "COD-001",
     "pais_destino": "PAIS X", "puerto_destino": "PUERTO X",
     "formato": "FORMATO A", "planta_despacho": "PLANTA A",
     "variedad": "SC", "lote": "L-2",
     "cantidad_cajas_produccion": 40,
     "cantidad_cajas_equivalentes": 38.0, "cantidad_pallets": 2},
    {"fecha_salida": "2026-10-03", "contenedor": "C-002",
     "pallet_id": "PAL-002", "codigo_pallet": "COD-002",
     "pais_destino": "PAIS Y", "puerto_destino": "PUERTO Y",
     "formato": "FORMATO B", "planta_despacho": "PLANTA B",
     "variedad": "TM",
     "cantidad_cajas_produccion": 200,
     "cantidad_cajas_equivalentes": 190.0, "cantidad_pallets": 4},
]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(sheet_reader, "read_all",
                        lambda force=False: [dict(r) for r in ROWS])
    monkeypatch.setattr(sheet_reader, "last_updated",
                        lambda: "2026-10-11 12:00:00")
    app.app.config["TESTING"] = True
    return app.app.test_client()


def test_api_analytics_returns_kpis_por_fecha_tops_and_puerto(client):
    body = client.get("/api/analytics").get_json()

    assert set(body) >= {"kpis", "por_fecha", "top_paises", "por_puerto",
                         "top_formatos", "ultima_actualizacion"}
    assert body["ultima_actualizacion"] == "2026-10-11 12:00:00"


def test_api_analytics_kpis_use_distinct_counts(client):
    kpis = client.get("/api/analytics").get_json()["kpis"]

    assert kpis["contenedores"] == 2
    assert kpis["pallets"] == 2  # PAL-001 duplicated across lotes: no double
    assert kpis["cajas_produccion"] == 340
    assert kpis["cajas_equivalentes"] == pytest.approx(323.5)
    assert kpis["fecha_desde"] == "2026-10-01"
    assert kpis["fecha_hasta"] == "2026-10-03"
    assert kpis["ultima_salida"] == "2026-10-03"


def test_api_analytics_por_fecha_lists_day_countries(client):
    (first, second) = client.get("/api/analytics").get_json()["por_fecha"]

    assert first["fecha"] == "2026-10-01"
    assert first["contenedores"] == 1
    assert first["pallets"] == 1
    assert first["paises"] == ["PAIS X"]
    assert second["fecha"] == "2026-10-03"
    assert second["paises"] == ["PAIS Y"]


def test_api_analytics_honours_date_filters(client):
    body = client.get("/api/analytics?desde=2026-10-03").get_json()

    assert body["kpis"]["contenedores"] == 1
    assert [d["fecha"] for d in body["por_fecha"]] == ["2026-10-03"]
    assert [p["pais"] for p in body["top_paises"]] == ["PAIS Y"]


def test_api_analytics_ranks_countries_ports_and_formats(client):
    body = client.get("/api/analytics").get_json()

    # Tie on contenedores (1-1): PAIS Y wins on cajas equivalentes.
    assert [(p["pais"], p["contenedores"])
            for p in body["top_paises"]] == [("PAIS Y", 1), ("PAIS X", 1)]
    assert {(p["pais"], p["puerto"]) for p in body["por_puerto"]} == {
        ("PAIS X", "PUERTO X"), ("PAIS Y", "PUERTO Y")}
    assert {f["formato"] for f in body["top_formatos"]} == {
        "FORMATO A", "FORMATO B"}


def test_api_pallets_keeps_legacy_summary_and_stamp(client):
    body = client.get("/api/pallets").get_json()

    assert body["summary"]["filas"] == 3
    assert body["ultima_actualizacion"] == "2026-10-11 12:00:00"


def test_refresh_still_posts_and_advances_stamp(monkeypatch):
    stamps = {"current": "2026-10-11 12:00:00"}
    monkeypatch.setattr(sheet_reader, "read_all",
                        lambda force=False: [dict(r) for r in ROWS])
    monkeypatch.setattr(sheet_reader, "refresh",
                        lambda: [dict(r) for r in ROWS])
    monkeypatch.setattr(sheet_reader, "last_updated",
                        lambda: stamps["current"])
    app.app.config["TESTING"] = True
    test_client = app.app.test_client()

    stamps["current"] = "2026-10-11 12:30:00"
    res = test_client.post("/api/refresh")

    assert res.status_code == 200
    assert res.get_json()["ultima_actualizacion"] == "2026-10-11 12:30:00"
