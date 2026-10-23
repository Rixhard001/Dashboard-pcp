"""Analytics page tests (PR2b task 3). Static HTML asserts, no live calls."""
import app


def test_index_shows_dispatch_kpi_cards():
    html = app.app.test_client().get("/").get_data(as_text=True)

    for label in ("Contenedores", "Pallets", "Cajas producci",
                  "Cajas equivalentes", "Rango de fechas",
                  "ltima salida"):
        assert label in html, label


def test_index_shows_analytics_sections_and_charts():
    html = app.app.test_client().get("/").get_data(as_text=True)

    for label in ("Despachos por d", "Top pa", "Resumen por fecha",
                  "país y puerto", "puerto", "Formato", "Presentaci"):
        assert label in html, label
    assert html.count("<canvas") >= 2  # daily combo + top countries
    assert "/api/analytics" in html  # page feeds charts from the endpoint


def test_index_keeps_refresh_stamp_and_spanish_filters():
    html = app.app.test_client().get("/").get_data(as_text=True)

    for label in ("Desde", "Hasta", "Planta", "Variedad", "Actualizar",
                  "ltima actualizaci", "chart.umd.min.js"):
        assert label in html, label
    assert "api/refresh" in html


def test_index_filters_from_memory_without_sheet_flash():
    html = app.app.test_client().get("/").get_data(as_text=True)

    assert "Promise.all" in html  # analytics + detail in parallel
    assert "DETALLE_MAX" in html  # detail grid capped, KPIs/charts keep all rows
    assert "Mostrando" in html
    assert "setTimeout" in html  # loader only appears when the roundtrip is slow
