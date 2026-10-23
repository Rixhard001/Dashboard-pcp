"""Campaign view analytics tests. Pure functions, zero network."""
import campaign_analytics


def rec(fecha="2026-10-22", hora="18", planta="Packing 1 - Piura",
        variedad="TM", jabas=10, fecha_evento=""):
    return {"fecha": fecha, "hora": hora, "planta": planta,
            "variedad": variedad, "jabas": jabas, "guias": 1, "pallets": 2,
            "fecha_evento": fecha_evento or fecha}


def aba(fecha="2026-10-22", hora="19", planta="Packing 1 - Piura",
        variedad="TM", jabas=8, fecha_evento=""):
    return {"fecha": fecha, "hora": hora, "planta": planta,
            "variedad": variedad, "jabas": jabas, "descargas": 1,
            "fecha_evento": fecha_evento or fecha}


def pro(fecha="2026-10-22", planta="Packing 1 - Piura", variedad="TM",
        cajas=4, eq=3, kilos=40):
    return {"fecha": fecha, "planta": planta, "variedad": variedad,
            "cajas_produccion": cajas, "cajas_equivalentes": eq,
            "kilos": kilos}


def test_defaults_to_last_date_with_data():
    data = {"recepcion": [rec(fecha="2026-10-20"), rec(fecha="2026-10-22")],
            "abastecimiento": [aba(fecha="2026-10-21")],
            "produccion": [pro(fecha="2026-10-19")]}
    body = campaign_analytics.collect(data)
    assert body["fecha"] == "2026-10-22"
    assert body["ultima_fecha"] == "2026-10-22"
    assert body["fechas"] == ["2026-10-19", "2026-10-20", "2026-10-21",
                              "2026-10-22"]


def test_explicit_date_filters_every_dataset():
    data = {"recepcion": [rec(), rec(fecha="2026-10-21")],
            "abastecimiento": [aba()], "produccion": [pro()]}
    body = campaign_analytics.collect(data, fecha="2026-10-21")
    assert body["kpis"]["jabas_recepcion"] == 10
    assert body["kpis"]["jabas_abastecimiento"] == 0
    assert body["kpis"]["cajas_produccion"] == 0


def test_kpis_sum_and_percentage():
    data = {"recepcion": [rec(jabas=10), rec(variedad="JS", jabas=30)],
            "abastecimiento": [aba(jabas=20)], "produccion": [pro()]}
    body = campaign_analytics.collect(data)
    assert body["kpis"]["jabas_recepcion"] == 40
    assert body["kpis"]["jabas_abastecimiento"] == 20
    assert body["kpis"]["pct_abastecido"] == 50.0
    assert body["kpis"]["cajas_produccion"] == 4
    assert body["kpis"]["cajas_equivalentes"] == 3


def test_hourly_series_has_the_whole_campaign_day():
    data = {"recepcion": [rec(hora="18")], "abastecimiento": [aba(hora="19")],
            "produccion": []}
    body = campaign_analytics.collect(data)
    assert len(body["por_hora"]) == 28
    rows = {row["hora"]: row for row in body["por_hora"]
            if row["hora"] not in {"03", "04", "05", "06"}}
    assert rows["18"]["recepcion"] == 10
    assert rows["19"]["abastecimiento"] == 8
    assert rows["18"]["abastecimiento"] == 0


def test_hourly_series_runs_from_3am_to_6am_next_day():
    body = campaign_analytics.collect({})
    hours = [row["hora"] for row in body["por_hora"]]
    assert len(hours) == 28
    assert hours[:4] == ["03", "04", "05", "06"]
    assert hours[20:] == ["23", "00", "01", "02", "03", "04", "05", "06"]
    assert hours[-1] == "06"


def test_the_same_hour_lands_twice_from_the_event_date():
    data = {"recepcion": [rec(fecha="2026-10-22", hora="04", jabas=1,
                              fecha_evento="2026-10-22"),
                          rec(fecha="2026-10-22", hora="04", jabas=2,
                              fecha_evento="2026-10-23")],
            "abastecimiento": [], "produccion": []}
    body = campaign_analytics.collect(data)
    rows = body["por_hora"]
    assert rows[1]["hora"] == "04" and rows[1]["recepcion"] == 1
    assert rows[27]["hora"] == "06"
    assert rows[25]["hora"] == "04" and rows[25]["recepcion"] == 2


def test_cumulative_hours_accumulate_in_campaign_day_order():
    data = {"recepcion": [rec(hora="03", jabas=1, fecha_evento="2026-10-22"),
                          rec(hora="23", jabas=7, fecha_evento="2026-10-22"),
                          rec(hora="00", jabas=3, fecha_evento="2026-10-23"),
                          rec(hora="06", jabas=2, fecha_evento="2026-10-23")],
            "abastecimiento": [], "produccion": []}
    body = campaign_analytics.collect(data)
    rows = body["por_hora"]
    assert rows[0]["recepcion_acum"] == 1
    assert rows[20]["recepcion_acum"] == 8
    assert rows[21]["recepcion_acum"] == 11
    assert rows[27]["recepcion_acum"] == 13


def test_variety_table_joins_the_three_sources():
    data = {"recepcion": [rec(variedad="TM", jabas=10)],
            "abastecimiento": [aba(variedad="TM", jabas=8),
                               aba(variedad="JS", jabas=2)],
            "produccion": [pro(variedad="TM", cajas=4, eq=3)]}
    body = campaign_analytics.collect(data)
    rows = {r["variedad"]: r for r in body["por_variedad"]}
    assert rows["TM"]["jabas_recepcion"] == 10
    assert rows["TM"]["jabas_abastecimiento"] == 8
    assert rows["TM"]["cajas_produccion"] == 4
    assert rows["JS"]["jabas_recepcion"] == 0
    assert rows["JS"]["jabas_abastecimiento"] == 2


def test_planta_and_variedad_filters_apply():
    data = {"recepcion": [rec(planta="P1", variedad="TM"),
                          rec(planta="P2", variedad="JS")],
            "abastecimiento": [], "produccion": []}
    body = campaign_analytics.collect(data, planta="P2")
    assert body["kpis"]["jabas_recepcion"] == 10
    assert [r["variedad"] for r in body["por_variedad"]] == ["JS"]
    body = campaign_analytics.collect(data, variedad="JS")
    assert body["kpis"]["jabas_recepcion"] == 10


def test_filter_options_cover_every_date_and_planta():
    data = {"recepcion": [rec(planta="P1"), rec(planta="P2",
                                                fecha="2026-10-21")],
            "abastecimiento": [], "produccion": []}
    body = campaign_analytics.collect(data, fecha="2026-10-21")
    assert body["plantas"] == ["P1", "P2"]
    assert body["variedades"] == ["TM"]


def test_packing_table_joins_reception_and_supply():
    data = {"recepcion": [rec(planta="P1", variedad="TM", jabas=10),
                          rec(planta="P2", variedad="TM", jabas=6)],
            "abastecimiento": [aba(planta="P1", variedad="TM", jabas=4)],
            "produccion": []}
    body = campaign_analytics.collect(data)
    rows = {(r["planta"], r["variedad"]): r for r in body["por_packing"]}
    assert rows[("P1", "TM")]["faltantes"] == 6
    assert rows[("P1", "TM")]["avance_pct"] == 40.0
    assert rows[("P2", "TM")]["faltantes"] == 6
    assert rows[("P2", "TM")]["avance_pct"] == 0


def test_totals_row_sums_and_recomputes_percentage():
    data = {"recepcion": [rec(jabas=10), rec(planta="P2", jabas=30)],
            "abastecimiento": [aba(jabas=20)], "produccion": []}
    body = campaign_analytics.collect(data)
    totales = body["totales"]
    assert totales["jabas_recepcion"] == 40
    assert totales["jabas_abastecimiento"] == 20
    assert totales["faltantes"] == 20
    assert totales["avance_pct"] == 50.0
    assert body["kpis"]["faltantes"] == 20


def test_faltantes_can_be_negative_when_stock_is_used():
    data = {"recepcion": [rec(jabas=5)], "abastecimiento": [aba(jabas=8)],
            "produccion": []}
    body = campaign_analytics.collect(data)
    assert body["totales"]["faltantes"] == -3
    assert body["totales"]["avance_pct"] == 160.0


def test_variety_rows_carry_progress_for_the_pies():
    data = {"recepcion": [rec(variedad="TM", jabas=10)],
            "abastecimiento": [aba(variedad="TM", jabas=4)],
            "produccion": []}
    body = campaign_analytics.collect(data)
    row = body["por_variedad"][0]
    assert row["faltantes"] == 6
    assert row["avance_pct"] == 40.0


def test_produccion_totals_sum_every_column():
    data = {"recepcion": [], "abastecimiento": [],
            "produccion": [pro(cajas=4, eq=3, kilos=40),
                           pro(variedad="JS", cajas=6, eq=5, kilos=60)]}
    body = campaign_analytics.collect(data)
    assert body["produccion_totales"] == {"cajas_produccion": 10,
                                          "cajas_equivalentes": 8,
                                          "kilos": 100}


def test_packing_rows_include_production_boxes():
    data = {"recepcion": [rec(planta="P1", variedad="TM", jabas=10)],
            "abastecimiento": [aba(planta="P1", variedad="TM", jabas=4)],
            "produccion": [pro(planta="P1", variedad="TM", cajas=7, eq=6)]}
    body = campaign_analytics.collect(data)
    row = body["por_packing"][0]
    assert row["cajas_produccion"] == 7
    assert row["cajas_equivalentes"] == 6
    assert body["totales"]["cajas_produccion"] == 7
    assert body["totales"]["cajas_equivalentes"] == 6


def test_packing_subtotals_group_by_planta():
    data = {"recepcion": [rec(planta="P1", variedad="TM", jabas=10),
                          rec(planta="P1", variedad="JS", jabas=5),
                          rec(planta="P2", variedad="TM", jabas=4)],
            "abastecimiento": [aba(planta="P1", variedad="TM", jabas=8)],
            "produccion": [pro(planta="P1", variedad="TM", cajas=7, eq=6),
                           pro(planta="P1", variedad="JS", cajas=3, eq=2)]}
    body = campaign_analytics.collect(data)
    subs = {s["planta"]: s for s in body["subtotales_packing"]}
    assert subs["P1"]["jabas_recepcion"] == 15
    assert subs["P1"]["jabas_abastecimiento"] == 8
    assert subs["P1"]["faltantes"] == 7
    assert subs["P1"]["cajas_produccion"] == 10
    assert subs["P1"]["cajas_equivalentes"] == 8
    assert subs["P2"]["jabas_recepcion"] == 4
    assert [s["planta"] for s in body["subtotales_packing"]] == ["P1", "P2"]


def test_hour_rows_carry_cumulative_totals():
    data = {"recepcion": [rec(hora="18", jabas=10), rec(hora="20", jabas=5)],
            "abastecimiento": [aba(hora="19", jabas=4), aba(hora="21", jabas=1)],
            "produccion": []}
    body = campaign_analytics.collect(data)
    rows = {r["hora"]: r for r in body["por_hora"]}
    assert rows["18"]["recepcion_acum"] == 10
    assert rows["19"]["recepcion_acum"] == 10
    assert rows["20"]["recepcion_acum"] == 15
    assert rows["18"]["abastecimiento_acum"] == 0
    assert rows["19"]["abastecimiento_acum"] == 4
    assert rows["21"]["abastecimiento_acum"] == 5


def test_empty_data_is_safe():
    body = campaign_analytics.collect({})
    assert body["fecha"] == ""
    assert body["ultima_fecha"] == ""
    assert body["kpis"]["jabas_recepcion"] == 0
    assert body["kpis"]["pct_abastecido"] == 0
    assert len(body["por_hora"]) == 28
    assert body["por_hora"][0]["recepcion_acum"] == 0
    assert body["por_variedad"] == []
    assert body["por_packing"] == []
    assert body["subtotales_packing"] == []
    assert body["totales"] == {"jabas_recepcion": 0,
                               "jabas_abastecimiento": 0,
                               "faltantes": 0, "avance_pct": 0,
                               "cajas_produccion": 0,
                               "cajas_equivalentes": 0}
    assert body["produccion_totales"] == {"cajas_produccion": 0,
                                          "cajas_equivalentes": 0,
                                          "kilos": 0}


def test_numbers_accept_sheet_strings_with_thousand_separators():
    data = {"recepcion": [rec(jabas="1,234.5")], "abastecimiento": [],
            "produccion": []}
    body = campaign_analytics.collect(data)
    assert body["kpis"]["jabas_recepcion"] == 1234.5


def test_rows_after_6am_go_to_an_explicit_overflow_bucket():
    data = {"recepcion": [],
            "abastecimiento": [aba(hora="06", jabas=2,
                                   fecha_evento="2026-10-23"),
                               aba(hora="09", jabas=5,
                                   fecha_evento="2026-10-23")],
            "produccion": []}
    body = campaign_analytics.collect(data)
    rows = body["por_hora"]
    assert len(rows) == 29
    assert rows[27]["hora"] == "06" and rows[27]["abastecimiento"] == 2
    assert rows[28]["hora"] == "07+" and rows[28]["abastecimiento"] == 5
    assert rows[28]["abastecimiento_acum"] == 7


def test_no_overflow_bucket_when_everything_fits():
    data = {"recepcion": [rec(hora="05", fecha_evento="2026-10-23")],
            "abastecimiento": [], "produccion": []}
    body = campaign_analytics.collect(data)
    assert len(body["por_hora"]) == 28
    assert body["por_hora"][-1]["hora"] == "06"
