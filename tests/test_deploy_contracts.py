"""Regression tests for deploy/runtime contracts."""

from pathlib import Path

from fastapi.testclient import TestClient

from lab_manager.config import get_settings


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scans_and_devices_mount_from_configured_paths(tmp_path, monkeypatch):
    """Configured scan/device paths are served instead of hardcoded sample dirs."""
    scans_dir = tmp_path / "scans"
    scans_dir.mkdir()
    (scans_dir / "scan.txt").write_text("scan", encoding="utf-8")

    devices_dir = tmp_path / "devices"
    devices_dir.mkdir()
    (devices_dir / "device.txt").write_text("device", encoding="utf-8")

    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("SCANS_DIR", str(scans_dir))
    monkeypatch.setenv("DEVICES_DIR", str(devices_dir))
    get_settings.cache_clear()

    from lab_manager.api.app import create_app

    try:
        with TestClient(create_app()) as client:
            assert client.get("/scans/scan.txt").status_code == 200
            assert client.get("/lab-devices/device.txt").status_code == 200
    finally:
        get_settings.cache_clear()


def test_scans_and_devices_unmounted_when_unconfigured(monkeypatch):
    """Fresh installs should not expose bundled sample asset mounts."""
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.delenv("SCANS_DIR", raising=False)
    monkeypatch.delenv("DEVICES_DIR", raising=False)
    get_settings.cache_clear()

    from lab_manager.api.app import create_app

    try:
        app = create_app()
        mount_names = {
            route.name for route in app.routes if getattr(route, "name", None)
        }
        assert "scans" not in mount_names
        assert "devices" not in mount_names
    finally:
        get_settings.cache_clear()


def test_incomplete_spa_build_falls_back_to_legacy_ui(tmp_path, monkeypatch):
    """If the hashed JS bundle is missing, serve the legacy UI instead of a blank page."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<html><body>legacy ui</body></html>", encoding="utf-8"
    )
    (static_dir / "sw.js").write_text(
        "self.addEventListener('fetch', ()=>{});", encoding="utf-8"
    )
    (static_dir / "manifest.json").write_text("{}", encoding="utf-8")

    dist_dir = static_dir / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        '<html><body><div id="root"></div><script type="module" src="/assets/index-missing.js"></script><link rel="stylesheet" href="/assets/index.css"></body></html>',
        encoding="utf-8",
    )
    (assets_dir / "index.css").write_text("body{}", encoding="utf-8")

    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()

    import lab_manager.api.app as app_module

    original_static_dir = app_module.STATIC_DIR
    app_module.STATIC_DIR = static_dir
    try:
        with TestClient(app_module.create_app()) as client:
            response = client.get("/")
            assert response.status_code == 200
            assert "legacy ui" in response.text
            assert client.get("/assets/index-missing.js").status_code == 404
    finally:
        app_module.STATIC_DIR = original_static_dir
        get_settings.cache_clear()


def test_dockerfile_uses_migration_entrypoint():
    """Production image should boot through the migration-aware entrypoint."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh" in dockerfile
    assert 'CMD ["docker-entrypoint.sh"]' in dockerfile


def test_entrypoint_uses_built_virtualenv_binaries():
    """Container startup should not sync or download dependencies at runtime."""
    entrypoint = (REPO_ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "/app/.venv/bin/alembic upgrade head" in entrypoint
    assert (
        "exec /app/.venv/bin/uvicorn lab_manager.api.app:create_app --factory --host 0.0.0.0 --port 8000"
        in entrypoint
    )
    assert "uv run alembic upgrade head" not in entrypoint
    assert "exec uv run uvicorn" not in entrypoint


def test_compose_defaults_to_empty_asset_mounts():
    """Default compose config should not bind sample lab assets."""
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "shenlab-docs" not in compose
    assert "shenlab-devices" not in compose
    assert "./docker/empty/scans" in compose
    assert "./docker/empty/devices" in compose
    assert "SCANS_DIR: ${SCANS_DIR:+/app/scans}" in compose
    assert "DEVICES_DIR: ${DEVICES_DIR:+/app/lab-devices}" in compose
