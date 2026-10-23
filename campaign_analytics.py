"""Campaign view analytics (pure): last date, hourly series and KPIs.

Rows come from the Sheet as strings. The default date is the newest date
with data, which is the requirement: "por defecto solo debe mostrar la
ǧltima fecha con datos".
"""
import datetime as dt

HOURS = [f"{(3 + index) % 24:02d}" for index in range(28)]
OVERFLOW = len(HOURS)
OVERFLOW_LABEL = "07+"


def _slot(row):
    """Position on the campaign timeline: 03:00 -> 06:00 of the next day.

    The production date alone cannot tell 04:00 of the day from 04:00 of the
    next morning, so the writer stores `fecha_evento`. Anything after 06:00
    of the next morning goes to an explicit overflow bucket instead of
    inflating the 06:00 bar. Rows written before that column existed fall
    back to the clock hour.
    """
    try:
        hour = int(_text(row.get("hora")).zfill(2)[:2] or 0)
    except ValueError:
        hour = 0
    fecha = _text(row.get("fecha"))[:10]
    evento = _text(row.get("fecha_evento"))[:10]
    delta = 0
    if fecha and evento:
        try:
            delta = (dt.date.fromisoformat(evento)
                     - dt.date.fromisoformat(fecha)).days
        except ValueError:
            delta = 0
    if delta <= 0:
        index = hour - 3 if hour >= 3 else hour + 21
    else:
        index = hour + 21 + (delta - 1) * 24
    return max(0, min(OVERFLOW, index))


def to_num(value):
    """Sheet cells are strings; tolerate blanks and thousand separators."""
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _clean(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return round(value, 2) if isinstance(value, float) else value


def _text(value):
    return "" if value is None else str(value)


def _pct(abastecido, recepcionado):
    """Share of received jabas already supplied to the line."""
    if not recepcionado:
        return 0
    return round(abastecido / recepcionado * 100, 1)


def _rows(data, key):
    return data.get(key) or []


def _fecha(row):
    return _text(row.get("fecha"))[:10]


def collect(data, fecha=None, planta=None, variedad=None):
    """Build the campaign view body for one date plus filters."""
    recepcion = _rows(data, "recepcion")
    abastecimiento = _rows(data, "abastecimiento")
    produccion = _rows(data, "produccion")
    todo = recepcion + abastecimiento + produccion

    fechas = sorted({_fecha(row) for row in todo if _fecha(row)})
    ultima = fechas[-1] if fechas else ""
    chosen = fecha or ultima
    plantas = sorted({_text(row.get("planta")).strip() for row in todo
                      if _text(row.get("planta")).strip()})
    variedades = sorted({_text(row.get("variedad")).strip() for row in todo
                         if _text(row.get("variedad")).strip()})

    def pick(rows):
        out = []
        for row in rows:
            if _fecha(row) != chosen:
                continue
            if planta and _text(row.get("planta")) != planta:
                continue
            if variedad and _text(row.get("variedad")) != variedad:
                continue
            out.append(row)
        return out

    rec = pick(recepcion)
    aba = pick(abastecimiento)
    pro = pick(produccion)

    jabas_rec = sum(to_num(row.get("jabas")) for row in rec)
    jabas_aba = sum(to_num(row.get("jabas")) for row in aba)
    cajas = sum(to_num(row.get("cajas_produccion")) for row in pro)
    equivalentes = sum(to_num(row.get("cajas_equivalentes")) for row in pro)
    kilos = sum(to_num(row.get("kilos")) for row in pro)

    por_hora = [{"hora": hour, "recepcion": 0.0, "abastecimiento": 0.0}
                for hour in HOURS + [OVERFLOW_LABEL]]
    for row in rec:
        por_hora[_slot(row)]["recepcion"] += to_num(row.get("jabas"))
    for row in aba:
        por_hora[_slot(row)]["abastecimiento"] += to_num(row.get("jabas"))

    if not (por_hora[OVERFLOW]["recepcion"]
            or por_hora[OVERFLOW]["abastecimiento"]):
        por_hora.pop()

    rec_run = 0.0
    aba_run = 0.0
    for entry in por_hora:
        rec_run += entry["recepcion"]
        aba_run += entry["abastecimiento"]
        entry["recepcion_acum"] = rec_run
        entry["abastecimiento_acum"] = aba_run

    variedad_keys = sorted({_text(row.get("variedad")) for row in rec + aba + pro})
    por_variedad = []
    for code in variedad_keys:
        rec_v = [row for row in rec if _text(row.get("variedad")) == code]
        aba_v = [row for row in aba if _text(row.get("variedad")) == code]
        pro_v = [row for row in pro if _text(row.get("variedad")) == code]
        rec_jabas = sum(to_num(r.get("jabas")) for r in rec_v)
        aba_jabas = sum(to_num(r.get("jabas")) for r in aba_v)
        por_variedad.append({
            "variedad": code,
            "jabas_recepcion": _clean(rec_jabas),
            "jabas_abastecimiento": _clean(aba_jabas),
            "faltantes": _clean(rec_jabas - aba_jabas),
            "avance_pct": _pct(aba_jabas, rec_jabas),
            "cajas_produccion": _clean(
                sum(to_num(r.get("cajas_produccion")) for r in pro_v)),
            "cajas_equivalentes": _clean(
                sum(to_num(r.get("cajas_equivalentes")) for r in pro_v)),
        })

    packing_keys = sorted({(_text(r.get("planta")), _text(r.get("variedad")))
                           for r in rec + aba + pro})
    por_packing = []
    for planta_code, variedad_code in packing_keys:
        def total(rows, key):
            return sum(to_num(r.get(key)) for r in rows
                       if _text(r.get("planta")) == planta_code
                       and _text(r.get("variedad")) == variedad_code)

        rec_jabas = total(rec, "jabas")
        aba_jabas = total(aba, "jabas")
        por_packing.append({
            "planta": planta_code,
            "variedad": variedad_code,
            "jabas_recepcion": _clean(rec_jabas),
            "jabas_abastecimiento": _clean(aba_jabas),
            "faltantes": _clean(rec_jabas - aba_jabas),
            "avance_pct": _pct(aba_jabas, rec_jabas),
            "cajas_produccion": _clean(total(pro, "cajas_produccion")),
            "cajas_equivalentes": _clean(total(pro, "cajas_equivalentes")),
        })

    subtotales_packing = []
    for planta_code in sorted({row["planta"] for row in por_packing}):
        group = [row for row in por_packing if row["planta"] == planta_code]
        rec_jabas = sum(to_num(row["jabas_recepcion"]) for row in group)
        aba_jabas = sum(to_num(row["jabas_abastecimiento"]) for row in group)
        subtotales_packing.append({
            "planta": planta_code,
            "jabas_recepcion": _clean(rec_jabas),
            "jabas_abastecimiento": _clean(aba_jabas),
            "faltantes": _clean(rec_jabas - aba_jabas),
            "avance_pct": _pct(aba_jabas, rec_jabas),
            "cajas_produccion": _clean(sum(
                to_num(row["cajas_produccion"]) for row in group)),
            "cajas_equivalentes": _clean(sum(
                to_num(row["cajas_equivalentes"]) for row in group)),
        })

    totales = {
        "jabas_recepcion": _clean(jabas_rec),
        "jabas_abastecimiento": _clean(jabas_aba),
        "faltantes": _clean(jabas_rec - jabas_aba),
        "avance_pct": _pct(jabas_aba, jabas_rec),
        "cajas_produccion": _clean(cajas),
        "cajas_equivalentes": _clean(equivalentes),
    }

    produccion_rows = [{
        "variedad": code,
        "cajas_produccion": _clean(sum(
            to_num(r.get("cajas_produccion")) for r in pro
            if _text(r.get("variedad")) == code)),
        "cajas_equivalentes": _clean(sum(
            to_num(r.get("cajas_equivalentes")) for r in pro
            if _text(r.get("variedad")) == code)),
        "kilos": _clean(sum(
            to_num(r.get("kilos")) for r in pro
            if _text(r.get("variedad")) == code)),
    } for code in sorted({_text(r.get("variedad")) for r in pro})]

    return {
        "fecha": chosen,
        "ultima_fecha": ultima,
        "fechas": fechas,
        "plantas": plantas,
        "variedades": variedades,
        "kpis": {
            "jabas_recepcion": _clean(jabas_rec),
            "jabas_abastecimiento": _clean(jabas_aba),
            "faltantes": _clean(jabas_rec - jabas_aba),
            "pct_abastecido": round(jabas_aba / jabas_rec * 100, 1)
            if jabas_rec else 0,
            "cajas_produccion": _clean(cajas),
            "cajas_equivalentes": _clean(equivalentes),
            "kilos": _clean(kilos),
        },
        "por_hora": [{"hora": entry["hora"],
                      "recepcion": _clean(entry["recepcion"]),
                      "abastecimiento": _clean(entry["abastecimiento"]),
                      "recepcion_acum": _clean(entry["recepcion_acum"]),
                      "abastecimiento_acum": _clean(
                          entry["abastecimiento_acum"])}
                     for entry in por_hora],
        "por_variedad": por_variedad,
        "por_packing": por_packing,
        "subtotales_packing": subtotales_packing,
        "totales": totales,
        "produccion": produccion_rows,
        "produccion_totales": {
            "cajas_produccion": _clean(cajas),
            "cajas_equivalentes": _clean(equivalentes),
            "kilos": _clean(kilos),
        },
    }
