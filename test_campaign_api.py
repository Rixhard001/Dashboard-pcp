"""Campaign tab wiring: reader mapping and Flask endpoints (no network)."""
import pytest

import app
import campaign_reader
import sheet_reader

DATA = {
    "recepcion": [{"fecha": "2026-10-22", "hora": "18",
                   "planta": "Packing 1 - Piura", "variedad": "TM",
                   "jabas": "10", "guias": "1", "pallets": "2"}],
    "abastecimiento": [{"fecha": "2026-10-22", "hora": "19",
                        "planta": "Packing 1 - Piura", "variedad": "TM",
                        "jabas": "8", "descargas": "1"}],
    "produccion": [{"fecha": "2026-10-22", "planta": "Packing 1 - Piura",
                    "variedad": "TM", "cajas_produccion": "4",
                    "cajas_equivalentes": "3", "kilos": "40"}],
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(campaign_reader, "read", lambda force=False: DATA)
    monkeypatch.setattr(campaign_reader, "last_updated",
                        lambda: "2026-10-22 09:00:00")
    monkeypatch.setattr(campaign_reader, "refresh", lambda: DATA)
    app.app.config["TESTING"] = True
    return app.app.test_client()


def test_reader_maps_the_three_tabs(monkeypatch):
    calls = []

    def fake_read_tab(tab, force=False):
        calls.append(tab)
        return [{"fecha": "2026-10-22"}]

    monkeypatch.setattr(sheet_reader, "read_tab", fake_read_tab)
    out = campaign_reader.read()
    assert set(out) == {"recepcion", "abastecimiento", "produccion"}
    assert calls == list(campaign_reader.TABS.values())


def test_api_campania_defaults_to_last_date(client):
    body = client.get("/api/campania").get_json()
    assert body["fecha"] == "2026-10-22"
    assert body["kpis"]["jabas_recepcion"] == 10
    assert body["kpis"]["jabas_abastecimiento"] == 8
    assert body["ultima_actualizacion"] == "2026-10-22 09:00:00"


def test_api_campania_exposes_packing_rows_and_totals(client):
    body = client.get("/api/campania").get_json()
    assert body["por_packing"][0]["planta"] == "Packing 1 - Piura"
    assert body["totales"]["jabas_recepcion"] == 10
    assert body["totales"]["faltantes"] == 2
    assert body["produccion_totales"]["cajas_produccion"] == 4


def test_api_campania_accepts_filters(client):
    body = client.get("/api/campania?fecha=2026-10-21&planta=Packing 1 - "
                      "Piura&variedad=TM").get_json()
    assert body["fecha"] == "2026-10-21"
    assert body["kpis"]["jabas_recepcion"] == 0


def test_api_campania_refresh_drops_the_tab_cache(client):
    body = client.post("/api/campania/refresh").get_json()
    assert body["fecha"] == "2026-10-22"
    assert body["kpis"]["jabas_recepcion"] == 10


def test_page_exposes_the_campania_tab(client):
    html = client.get("/").get_data(as_text=True)
    assert "Campaña" in html
    assert "/api/campania" in html
    assert "Jabas recepcionadas" in html
    assert "Producción por variedad" in html


def test_campania_note_keeps_only_the_faltantes_rule(client):
    html = client.get("/").get_data(as_text=True)
    assert "Faltantes = recepcionadas − abastecidas" in html
    assert "sincroniza cada 5 minutos" not in html


def test_page_has_packing_table_totals_and_variety_pies(client):
    html = client.get("/").get_data(as_text=True)
    assert "Resumen por packing y variedad" in html
    assert "Jabas faltantes" in html
    assert "% avance" in html
    assert 'id="cPacking"' in html
    assert 'id="cPies"' in html


def test_hidden_attribute_wins_over_flex_filters(client):
    html = client.get("/").get_data(as_text=True)
    assert "[hidden]{display:none!important}" in html


def test_page_uses_general_title_and_kpi_for_missing_jabas(client):
    html = client.get("/").get_data(as_text=True)
    assert "Dashboard PCP" in html
    assert "Pallets exportados" not in html
    assert "['Jabas faltantes',fmt(k.faltantes)],['% abastecido'" in html


def test_packing_table_shows_boxes_bars_and_subtotals(client):
    html = client.get("/").get_data(as_text=True)
    assert "Cajas reales" in html
    assert "Cajas equivalentes" in html
    assert 'class="bar"' in html
    assert 'class="pctbar"' in html
    assert "subtotales_packing" in html
    assert "Subtotal" in html


def test_variety_pies_draw_jaba_labels(client):
    html = client.get("/").get_data(as_text=True)
    assert "pieLabels" in html
    assert "afterDatasetsDraw" in html


def test_hour_table_has_cumulative_columns_and_chart_switch(client):
    html = client.get("/").get_data(as_text=True)
    assert "Recepcionadas acumuladas" in html
    assert "Abastecidas acumuladas" in html
    assert 'id="cModo"' in html
    assert "Acumulado" in html
