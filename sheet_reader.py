"""Read-only Sheet access for the dashboard.

Reads the pallet tab plus the campaign tabs written by the LAN runner.
There is intentionally no write path here: freshness is published by the
scheduled writer on the company network. No login, token-writing, or
report-fetching code lives in this folder.
"""
import json
import os
import time

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SPREADSHEET_ID = os.environ.get(
    "SPREADSHEET_ID", "1Svr0a4lwiw1b4Eujr_aMJwfd3N1kbVfSTa1IjzBMbQ4")
TAB = os.environ.get("PALLET_WORKSHEET", "Pallets exportados")
TOKEN_PATH = os.environ.get("GOOGLE_OAUTH_TOKEN_PATH",
                            "token_pallet_readonly.json")
# Full scope on purpose: Google rejects refreshing this token with the
# readonly subset (invalid_scope). The dashboard stays read-only by code:
# this folder has no write path, only get_all_records().
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_cache = {"ts": 0.0, "data": None}
_tab_cache = {}
CACHE_TTL = 3600  # 1 hora: los filtros reutilizan la memoria sin releer el Sheet.


def _load_creds():
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    if raw:
        creds = Credentials.from_authorized_user_info(
            json.loads(raw), scopes=SCOPES)
    else:
        if not os.path.exists(TOKEN_PATH):
            raise SystemExit(
                "Falta GOOGLE_CREDENTIALS_JSON o el archivo "
                f"{TOKEN_PATH} (credencial de solo lectura del Sheet)")
        creds = Credentials.from_authorized_user_file(
            TOKEN_PATH, scopes=SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def read_all(force=False):
    """Return pallet rows as dicts; cached for CACHE_TTL unless forced."""
    now = time.time()
    if (not force and _cache["data"] is not None
            and now - _cache["ts"] < CACHE_TTL):
        return _cache["data"]
    client = gspread.authorize(_load_creds())
    rows = client.open_by_key(SPREADSHEET_ID).worksheet(TAB).get_all_records()
    _cache["ts"] = now
    _cache["data"] = rows
    return rows


def refresh():
    """Drop the cache, re-read the Sheet, and return the fresh rows."""
    return read_all(force=True)


def last_updated():
    """Visible `Ultima actualizacion` stamp of the last Sheet read."""
    if not _cache["ts"]:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(_cache["ts"]))


def read_tab(tab, force=False):
    """Read any tab as dicts; cached per tab, missing tabs read as empty."""
    now = time.time()
    entry = _tab_cache.get(tab)
    if not force and entry is not None and now - entry["ts"] < CACHE_TTL:
        return entry["data"]
    client = gspread.authorize(_load_creds())
    try:
        rows = client.open_by_key(SPREADSHEET_ID).worksheet(
            tab).get_all_records()
    except gspread.WorksheetNotFound:
        rows = []
    _tab_cache[tab] = {"ts": now, "data": rows}
    return rows


def tab_updated(tab):
    """Visible read stamp for one tab ('' when it was never read)."""
    entry = _tab_cache.get(tab)
    if not entry or not entry["ts"]:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["ts"]))
