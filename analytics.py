"""Pure dispatch analytics over pallet/lote detail rows.

Correctness contract (rows are pallet/lote DETAIL, naive sums lie):

- Contenedores = DISTINCT non-empty ``contenedor`` values. Never summed;
  ``""``/``None``/whitespace-only are ignored.
- Pallets = DISTINCT ``pallet_id`` (fallback ``codigo_pallet`` when the
  former is missing/empty). The same pallet_id repeats across lote rows
  with ``cantidad_pallets`` repeated, so summing double-counts.
- Cajas (``cantidad_cajas_produccion`` / ``cantidad_cajas_equivalentes``)
  are per-lote quantities: plain sums, coerced via :func:`_num`.
- Grouping keys (``pais_destino`` / ``puerto_destino`` / ``formato``) are
  the raw strings verbatim — never renamed, stripped, or "fixed" (the
  source carries mojibake accents; display as-is). Missing/``None``
  keys become ``""`` and are skipped in rankings (a blank is not a
  country, port, or format).

No I/O, no imports from the dashboard or writer: pure functions only,
covered by ``test_analytics.py`` with fake rows.
"""

DATE_KEY = "fecha_salida"


def _num(value):
    """Coerce one possibly-formatted quantity to float (never raises)."""
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _raw(value):
    """Verbatim grouping text: raw string as-is, ``None``/missing -> ``""``."""
    if value is None:
        return ""
    return str(value)


def _contenedor_key(row):
    value = row.get("contenedor")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _pallet_key(row):
    for field in ("pallet_id", "codigo_pallet"):
        value = row.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def count_contenedores(rows):
    """Distinct non-empty ``contenedor`` values (pure)."""
    return len({key for key in (_contenedor_key(r) for r in rows)
                if key is not None})


def count_pallets(rows):
    """Distinct pallets via ``pallet_id`` (fallback ``codigo_pallet``)."""
    return len({key for key in (_pallet_key(r) for r in rows)
                if key is not None})


def sum_cajas_produccion(rows):
    """Plain sum of per-lote production boxes (pure)."""
    return sum(_num(r.get("cantidad_cajas_produccion")) for r in rows)


def sum_cajas_equivalentes(rows):
    """Plain sum of per-lote equivalent boxes (pure)."""
    return sum(_num(r.get("cantidad_cajas_equivalentes")) for r in rows)


def _group_metrics(rows):
    """Shared per-group metrics: distinct counts + box sums + row count."""
    return {
        "contenedores": count_contenedores(rows),
        "pallets": count_pallets(rows),
        "cajas_produccion": sum_cajas_produccion(rows),
        "cajas_equivalentes": sum_cajas_equivalentes(rows),
        "filas": len(rows),
    }


def _rank_key(entry):
    return (-entry["contenedores"], -entry["pallets"],
            -entry["cajas_equivalentes"])


def _por_fecha(rows):
    buckets = {}
    for row in rows:
        fecha = str(row.get(DATE_KEY) or "")[:10]
        buckets.setdefault(fecha, []).append(row)
    days = []
    for fecha in sorted(buckets):
        group = buckets[fecha]
        metrics = _group_metrics(group)
        days.append({
            "fecha": fecha,
            "contenedores": metrics["contenedores"],
            "pallets": metrics["pallets"],
            "cajas_produccion": metrics["cajas_produccion"],
            "cajas_equivalentes": metrics["cajas_equivalentes"],
            "paises": sorted({_raw(r.get("pais_destino")) for r in group
                              if _raw(r.get("pais_destino"))}),
        })
    return days


def _top_paises(rows):
    buckets = {}
    for row in rows:
        pais = _raw(row.get("pais_destino"))
        if not pais:
            continue
        buckets.setdefault(pais, []).append(row)
    ranked = [{"pais": pais, **_group_metrics(group)}
              for pais, group in buckets.items()]
    return sorted(ranked, key=lambda e: (_rank_key(e), e["pais"]))


def _por_puerto(rows):
    buckets = {}
    for row in rows:
        pais = _raw(row.get("pais_destino"))
        puerto = _raw(row.get("puerto_destino"))
        if not pais and not puerto:
            continue
        buckets.setdefault((pais, puerto), []).append(row)
    ranked = [{"pais": pais, "puerto": puerto, **_group_metrics(group)}
              for (pais, puerto), group in buckets.items()]
    return sorted(ranked,
                  key=lambda e: (_rank_key(e), e["pais"], e["puerto"]))


def _top_formatos(rows):
    buckets = {}
    for row in rows:
        formato = _raw(row.get("formato"))
        if not formato:
            continue
        buckets.setdefault(formato, []).append(row)
    ranked = [{"formato": formato, **_group_metrics(group)}
              for formato, group in buckets.items()]
    return sorted(ranked, key=lambda e: (_rank_key(e), e["formato"]))


def compute_analytics(rows):
    """Full analytics payload for the dashboard (pure).

    Returns ``{kpis, por_fecha, top_paises, por_puerto, top_formatos}``.
    Tolerates missing keys and unsorted input; never raises on ragged
    rows.
    """
    rows = list(rows)
    fechas = sorted({str(r.get(DATE_KEY) or "")[:10] for r in rows} - {""})
    return {
        "kpis": {
            "contenedores": count_contenedores(rows),
            "pallets": count_pallets(rows),
            "cajas_produccion": sum_cajas_produccion(rows),
            "cajas_equivalentes": sum_cajas_equivalentes(rows),
            "fecha_desde": fechas[0] if fechas else "",
            "fecha_hasta": fechas[-1] if fechas else "",
            "ultima_salida": fechas[-1] if fechas else "",
        },
        "por_fecha": _por_fecha(rows),
        "top_paises": _top_paises(rows),
        "por_puerto": _por_puerto(rows),
        "top_formatos": _top_formatos(rows),
    }
