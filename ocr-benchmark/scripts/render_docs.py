#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path("/Users/robert/workspace/36-labclaw/lab-manager")
OUT_DIR = ROOT / "ocr-benchmark" / "data" / "renders"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def render_pdf(path: Path) -> Path:
    out = OUT_DIR / path.stem
    run(["pdftoppm", "-png", "-f", "1", "-singlefile", str(path), str(out)])
    return out.with_suffix(".png")


def copy_image(path: Path) -> Path:
    out = OUT_DIR / f"{path.stem}{path.suffix.lower()}"
    if path.resolve() != out.resolve():
        shutil.copy2(path, out)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    docs = sorted(
        path
        for path in ROOT.iterdir()
        if path.is_file() and path.name.startswith("Scan")
    )
    for path in docs:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            rendered = render_pdf(path)
            print(f"rendered {path.name} -> {rendered.name}")
        elif suffix in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
            copied = copy_image(path)
            print(f"copied {path.name} -> {copied.name}")


if __name__ == "__main__":
    main()
