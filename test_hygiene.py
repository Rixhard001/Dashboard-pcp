"""Packaging and boundary-hygiene tests (PR2 task 3.3). No live calls."""
from pathlib import Path

HERE = Path(__file__).resolve().parent

ERP_MARKERS = ("gestagro", "iniciar_sesion", "api-packing", "api-iam",
               "GESTAGRO_USUARIO", "GESTAGRO_PASSWORD", "p_personal_id",
               "fecha_recepcion", "build_matrix", "1MstQPor")


def _sources():
    return {name: (HERE / name).read_text(encoding="utf-8")
            for name in ("app.py", "sheet_reader.py", "analytics.py",
                         "campaign_reader.py", "campaign_analytics.py")}


def test_dashboard_config_has_no_erp_references():
    for name, source in _sources().items():
        lowered = source.lower()
        for marker in ERP_MARKERS:
            assert marker.lower() not in lowered, (name, marker)


def test_dashboard_has_no_write_capability():
    for name, source in _sources().items():
        assert "write_matrix" not in source, name
        assert ".update(" not in source, name
        assert "delete_rows" not in source, name


def test_sheet_isolation_pinpoints_pallet_sheet_only():
    for name, source in _sources().items():
        assert "1MstQPor" not in source, name
    assert "1Svr0a4lwiw1b4Eujr_aMJwfd3N1kbVfSTa1IjzBMbQ4" in _sources()[
        "sheet_reader.py"]


def test_requirements_pins_server_and_sheet_deps_without_lan_tls():
    pinned = (HERE / "requirements.txt").read_text(encoding="utf-8")
    for dep in ("flask==", "gunicorn==", "gspread==", "google-auth=="):
        assert dep in pinned, dep
    lowered = pinned.lower()
    assert "truststore" not in lowered  # LAN CA juggling is writer-only
    assert "requests" not in lowered  # dashboard never calls HTTP APIs


def test_dockerfile_serves_gunicorn_on_port():
    docker = (HERE / "Dockerfile").read_text(encoding="utf-8")
    assert "gunicorn" in docker
    assert "PORT" in docker
    assert "app:app" in docker


def test_env_example_documents_dashboard_vars_with_no_values():
    entries = {}
    for line in (HERE / ".env.example").read_text(encoding="utf-8"
                                                  ).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        entries[key.strip()] = value.strip().strip('"').strip("'")
    assert "GOOGLE_CREDENTIALS_JSON" in entries
    for key, value in entries.items():
        assert value == "" or key in {"SPREADSHEET_ID", "PALLET_WORKSHEET",
                                      "GOOGLE_OAUTH_TOKEN_PATH",
                                      "PORT"}, key


def test_gitignore_covers_secrets_and_caches():
    ignored = (HERE / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignored
    assert "token" in ignored
    assert "__pycache__" in ignored


def test_dockerfile_copies_every_local_module_the_app_imports():
    source = (HERE / "app.py").read_text(encoding="utf-8")
    docker = (HERE / "Dockerfile").read_text(encoding="utf-8")
    local = [name for name in ("analytics", "campaign_analytics",
                               "campaign_reader", "sheet_reader")
             if f"import {name}" in source]
    assert local, "app.py should import its local modules"
    for name in local:
        assert f"{name}.py" in docker, f"Dockerfile must copy {name}.py"
