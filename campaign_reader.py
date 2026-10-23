"""Read-only access to the campaign tabs written by the LAN runner.

The dashboard never talks to the ERP: it only reads the three Sheet tabs
that `pallet-writer/campaign_cli.py` refreshes from inside the company
network. Missing tabs (first deploy) read as empty instead of failing.
"""
import os

import sheet_reader

TABS = {
    "recepcion": os.environ.get("CAMPAIGN_RECEPCION_TAB", "Recepcion jabas"),
    "abastecimiento": os.environ.get("CAMPAIGN_ABASTECIMIENTO_TAB",
                                     "Abastecimiento jabas"),
    "produccion": os.environ.get("CAMPAIGN_PRODUCCION_TAB",
                                 "Produccion cajas"),
}


def read(force=False):
    """All three datasets, keyed by source name."""
    return {name: sheet_reader.read_tab(tab, force=force)
            for name, tab in TABS.items()}


def refresh():
    """Drop the tab cache and re-read the three tabs."""
    return read(force=True)


def last_updated():
    """Newest read stamp across the campaign tabs."""
    stamps = [sheet_reader.tab_updated(tab) for tab in TABS.values()]
    return max(stamps) if stamps and any(stamps) else ""
