"""LabClaw Lab Manager — inventory management with OCR document intake."""

from pathlib import Path as _Path


def _read_version() -> str:
    try:
        from importlib.metadata import version

        return version("lab-manager")
    except Exception:
        _version_file = _Path(__file__).resolve().parents[2] / "VERSION"
        try:
            return _version_file.read_text().strip()
        except OSError:
            return "0.0.0"


__version__ = _read_version()
