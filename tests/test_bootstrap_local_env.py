"""Regression tests for the local bootstrap script."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def test_bootstrap_local_env_script_creates_env(tmp_path):
    """bootstrap_local_env.sh should succeed under pipefail and write a usable .env."""
    repo_root = Path(__file__).resolve().parents[1]
    temp_root = tmp_path / "lab-manager"
    scripts_dir = temp_root / "scripts"
    scripts_dir.mkdir(parents=True)

    shutil.copy2(repo_root / "scripts" / "bootstrap_local_env.sh", scripts_dir)

    result = subprocess.run(
        ["bash", str(scripts_dir / "bootstrap_local_env.sh"), "QA Lab"],
        cwd=temp_root,
        capture_output=True,
        text=True,
        env={**os.environ},
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    env_file = temp_root / ".env"
    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert 'LAB_NAME="QA Lab"' in content
    assert "SECURE_COOKIES=false" in content
    assert "POSTGRES_PASSWORD=" in content
    assert "ADMIN_PASSWORD=" in content
