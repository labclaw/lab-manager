"""Test that all Alembic migration revisions form a valid chain.

Verifies that:
1. Every down_revision references a revision that exists on disk
2. The migration chain has exactly one root (down_revision=None)
3. alembic heads reports a single head without errors
4. No phantom/orphan revision references exist
"""

import os
import subprocess
import importlib.util
from pathlib import Path


def _load_migrations():
    """Load all migration modules and return {revision_id: down_revision}."""
    vdir = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "lab_manager"
        / "alembic"
        / "versions"
    )
    migrations = {}
    for f in sorted(os.listdir(vdir)):
        if not f.endswith(".py") or f.startswith("_"):
            continue
        path = os.path.join(vdir, f)
        spec = importlib.util.spec_from_file_location(f[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rev = getattr(mod, "revision", None)
        down = getattr(mod, "down_revision", None)
        if rev:
            migrations[rev] = {"down": down, "file": f}
    return migrations


def test_all_down_revisions_exist_on_disk():
    """Every down_revision must reference a revision file that exists."""
    migrations = _load_migrations()
    all_revs = set(migrations.keys())

    for rev, info in migrations.items():
        down = info["down"]
        if down is None:
            continue
        # Handle tuple down_revision (merge migrations)
        if isinstance(down, tuple):
            for parent in down:
                assert parent in all_revs, (
                    f"Migration {rev} ({info['file']}) references phantom "
                    f"down_revision '{parent}' which does not exist on disk"
                )
        else:
            assert down in all_revs, (
                f"Migration {rev} ({info['file']}) references phantom "
                f"down_revision '{down}' which does not exist on disk"
            )


def test_single_root_migration():
    """There must be exactly one root migration (down_revision=None)."""
    migrations = _load_migrations()
    roots = [rev for rev, info in migrations.items() if info["down"] is None]
    assert len(roots) == 1, (
        f"Expected exactly 1 root migration, found {len(roots)}: {roots}"
    )


def test_alembic_heads_succeeds():
    """alembic heads command must exit with code 0 and report a single head."""
    result = subprocess.run(
        ["alembic", "heads"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert result.returncode == 0, (
        f"alembic heads failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    assert len(lines) == 1, f"Expected exactly 1 head, got {len(lines)}: {lines}"


def test_no_stale_pycache():
    """__pycache__ in alembic/versions should not contain stale .pyc files."""
    vdir = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "lab_manager"
        / "alembic"
        / "versions"
    )
    pycache = vdir / "__pycache__"
    if not pycache.exists():
        return  # No cache is fine

    py_files = {
        f[:-3] for f in os.listdir(vdir) if f.endswith(".py") and not f.startswith("_")
    }
    for pyc in os.listdir(pycache):
        if not pyc.endswith(".pyc"):
            continue
        # Extract module name from cpython-312.pyc
        base = pyc.rsplit(".cpython-", 1)[0]
        assert base in py_files, (
            f"Stale bytecode in __pycache__: {pyc} (no matching .py file)"
        )
