"""Shared test helpers. Run from the engine folder: python -m pytest tests"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[1]
TOOLS = ENGINE / "tools"
SAMPLE = ENGINE / "examples" / "sample-workspace"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(SAMPLE))


@pytest.fixture
def sample(tmp_path):
    """A fresh copy of the sample workspace with its CV and letter written."""
    import make_docs
    root = tmp_path / "workspace"
    shutil.copytree(SAMPLE, root)
    make_docs.write(root)
    return root


@pytest.fixture
def tool(sample):
    """tool("cv_map.py", "check") runs an engine tool against the sample workspace."""
    def run(name, *args):
        env = {**os.environ, "JOBHUNT_ROOT": str(sample), "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([sys.executable, str(TOOLS / name), *map(str, args)], cwd=sample, env=env,
                              capture_output=True, text=True, encoding="utf-8")
    return run
