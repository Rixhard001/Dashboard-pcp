"""Analytics aggregation tests (PR2b task 1). Fakes only, zero live network.

Rows are pallet/lote DETAIL: the same pallet_id repeats across lote rows
with cantidad_pallets repeated, and contenedor repeats on every row of the
container. Naive sums lie — containers and pallets are DISTINCT counts.
"""
import pytest

import analytics


def _row(**over):
    base = {"fecha_salida": "2026-10-01", "contenedor": "C-001",
            "pallet_id": "PAL-001", "codigo_pallet": "COD-001",
            "pais_destino": "PAIS X", "puerto_destino": "PUERTO X",
            "formato": "FORMATO A",
            "cantidad_cajas_produccion": 100,
            "cantidad_cajas_equivalentes": 95.5,
            "cantidad_pallets": 2}
    base.update(over)
    return base


def test_contenedores_counts_distinct_ignoring_empty_and_null():
    rows = [_row(contenedor="C-001"), _row(contenedor="C-001"),
            _row(contenedor="C-002"),
            _row(contenedor=""), _row(contenedor=None),
            _row()]  # missing key is tolerated upstream; explicit del below
    del rows[-1]["contenedor"]

    assert analytics.count_contenedores(rows) == 2


def test_pallets_distinct_regression_duplicated_pallet_id():
    # Same pallet repeats across lote rows with cantidad_pallets repeated:
    # summing would report 4, the honest answer is 1 pallet.
    rows = [_row(pallet_id="PAL-001", cantidad_pallets=2, lote_id="L-1"),
            _row(pallet_id="PAL-001", cantidad_pallets=2, lote_id="L-2")]

    assert analytics.count_pallets(rows) == 1


def test_pallets_falls_back_to_codigo_pallet_when_pallet_id_missing():
    rows = [_row(pallet_id="", codigo_pallet="COD-007"),
            _row()]  # pallet_id entirely absent
    del rows[1]["pallet_id"]
    rows[1]["codigo_pallet"] = "COD-008"

    assert analytics.count_pallets(rows) == 2


def test_cajas_are_plain_sums_with_num_coercion():
    rows = [_row(cantidad_cajas_produccion=100,
                 cantidad_cajas_equivalentes=95.5),
            _row(cantidad_cajas_produccion=None,
                 cantidad_cajas_equivalentes=""),
            _row(cantidad_cajas_produccion="1,200",
                 cantidad_cajas_equivalentes="50,5".replace(",5", ""))]

    assert analytics.sum_cajas_produccion(rows) == 1300
    assert analytics.sum_cajas_equivalentes(rows) == pytest.approx(145.5)


def test_grouping_is_verbatim_mojibake_preserved():
    mojibake = "PAÃ\x8dS CON ACENTO ROTO"
    rows = [_row(pais_destino=mojibake), _row(pais_destino=mojibake)]

    top = analytics.compute_analytics(rows)["top_paises"]

    assert len(top) == 1
    assert top[0]["pais"] == mojibake


def test_missing_keys_never_raise():
    rows = [{}, {"fecha_salida": "2026-10-02", "contenedor": "C-9",
                 "codigo_pallet": "COD-9"}]

    body = analytics.compute_analytics(rows)

    assert body["kpis"]["contenedores"] == 1
    assert body["kpis"]["pallets"] == 1  # codigo_pallet fallback
    assert body["por_fecha"][0]["fecha"] in ("", "2026-10-02")


def test_por_fecha_sorted_despite_unsorted_input():
    rows = [_row(fecha_salida="2026-10-05", contenedor="C-3"),
            _row(fecha_salida="2026-10-01", contenedor="C-1"),
            _row(fecha_salida="2026-10-03", contenedor="C-2")]

    fechas = [d["fecha"]
              for d in analytics.compute_analytics(rows)["por_fecha"]]

    assert fechas == ["2026-10-01", "2026-10-03", "2026-10-05"]


def test_por_fecha_carries_day_countries_and_both_box_series():
    rows = [_row(fecha_salida="2026-10-01", contenedor="C-1",
                 pallet_id="PAL-1", pais_destino="PAIS A",
                 cantidad_cajas_produccion=100,
                 cantidad_cajas_equivalentes=90.0),
            _row(fecha_salida="2026-10-01", contenedor="C-2",
                 pallet_id="PAL-2", pais_destino="PAIS B",
                 cantidad_cajas_produccion=50,
                 cantidad_cajas_equivalentes=48.0)]

    (day,) = analytics.compute_analytics(rows)["por_fecha"]

    assert day["contenedores"] == 2
    assert day["pallets"] == 2
    assert day["cajas_produccion"] == 150
    assert day["cajas_equivalentes"] == pytest.approx(138.0)
    assert sorted(day["paises"]) == ["PAIS A", "PAIS B"]


def test_kpis_carry_range_and_last_departure():
    rows = [_row(fecha_salida="2026-10-05", contenedor="C-3",
                 pallet_id="PAL-3",
                 cantidad_cajas_produccion=50,
                 cantidad_cajas_equivalentes=48.0),
            _row(fecha_salida="2026-10-01", contenedor="C-1",
                 pallet_id="PAL-1",
                 cantidad_cajas_produccion=100,
                 cantidad_cajas_equivalentes=90.0)]

    kpis = analytics.compute_analytics(rows)["kpis"]

    assert kpis["contenedores"] == 2
    assert kpis["pallets"] == 2
    assert kpis["cajas_produccion"] == 150
    assert kpis["cajas_equivalentes"] == pytest.approx(138.0)
    assert kpis["fecha_desde"] == "2026-10-01"
    assert kpis["fecha_hasta"] == "2026-10-05"
    assert kpis["ultima_salida"] == "2026-10-05"


def test_por_puerto_groups_by_country_and_port():
    rows = [_row(pais_destino="PAIS A", puerto_destino="PUERTO 1",
                 contenedor="C-1", pallet_id="PAL-1"),
            _row(pais_destino="PAIS A", puerto_destino="PUERTO 1",
                 contenedor="C-1", pallet_id="PAL-2"),
            _row(pais_destino="PAIS A", puerto_destino="PUERTO 2",
                 contenedor="C-2", pallet_id="PAL-3")]

    puertos = analytics.compute_analytics(rows)["por_puerto"]

    assert {(p["pais"], p["puerto"]) for p in puertos} == {
        ("PAIS A", "PUERTO 1"), ("PAIS A", "PUERTO 2")}
    first = next(p for p in puertos if p["puerto"] == "PUERTO 1")
    assert first["contenedores"] == 1  # same container, two pallets
    assert first["pallets"] == 2


def test_top_formatos_ranks_by_containers_first():
    rows = [_row(formato="FORMATO A", contenedor="C-1", pallet_id="PAL-1"),
            _row(formato="FORMATO B", contenedor="C-2", pallet_id="PAL-2"),
            _row(formato="FORMATO B", contenedor="C-3", pallet_id="PAL-3")]

    formatos = analytics.compute_analytics(rows)["top_formatos"]

    assert [f["formato"] for f in formatos] == ["FORMATO B", "FORMATO A"]
    assert formatos[0]["contenedores"] == 2


def test_top_paises_ranks_by_containers_first():
    rows = [_row(pais_destino="PAIS A", contenedor="C-1", pallet_id="PAL-1"),
            _row(pais_destino="PAIS B", contenedor="C-2", pallet_id="PAL-2"),
            _row(pais_destino="PAIS B", contenedor="C-3", pallet_id="PAL-3")]

    paises = analytics.compute_analytics(rows)["top_paises"]

    assert [p["pais"] for p in paises] == ["PAIS B", "PAIS A"]


def test_empty_input_returns_zeroed_shape():
    body = analytics.compute_analytics([])

    assert body["kpis"] == {"contenedores": 0, "pallets": 0,
                            "cajas_produccion": 0, "cajas_equivalentes": 0,
                            "fecha_desde": "", "fecha_hasta": "",
                            "ultima_salida": ""}
    assert body["por_fecha"] == []
    assert body["top_paises"] == []
    assert body["por_puerto"] == []
    assert body["top_formatos"] == []
