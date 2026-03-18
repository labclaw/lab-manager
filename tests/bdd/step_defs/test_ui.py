"""Test module for UI BDD scenarios — collects all ui_*.feature files."""

import glob
import os

from pytest_bdd import scenario

# Import all shared UI step definitions so pytest-bdd can find them.
from ui_common import *  # noqa: F401,F403

_FEATURE_DIR = os.path.join(os.path.dirname(__file__), "..", "features")


# Auto-collect all UI feature files and register each scenario.
def _collect_ui_scenarios():
    """Dynamically generate @scenario decorators for all ui_*.feature files."""
    features = glob.glob(os.path.join(_FEATURE_DIR, "ui_*.feature"))
    for feature_path in sorted(features):
        rel_path = os.path.relpath(feature_path, _FEATURE_DIR)
        abs_path = os.path.abspath(feature_path)
        # Read feature file to find scenario names
        with open(abs_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("Scenario:") or line.startswith("Scenario Outline:"):
                    scenario_name = line.split(":", 1)[1].strip()
                    # Create a unique test function name
                    func_name = (
                        "test_"
                        + rel_path.replace(".feature", "")
                        .replace("/", "_")
                        .replace("-", "_")
                        + "_"
                        + scenario_name.lower()
                        .replace(" ", "_")
                        .replace("-", "_")
                        .replace("'", "")
                        .replace('"', "")
                        .replace("(", "")
                        .replace(")", "")
                        .replace(",", "")
                    )
                    # Truncate to valid Python identifier length
                    func_name = func_name[:200]
                    globals()[func_name] = scenario(
                        os.path.join("..", "features", rel_path),
                        scenario_name,
                    )


_collect_ui_scenarios()
