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
SAMPLE_DE = ENGINE / "examples" / "sample-workspace-de"
sys.path.insert(0, str(TOOLS))


def make_workspace(src, dst):
    """A fresh copy of a sample workspace with its CV and letter written by its make_docs.py."""
    import importlib.util
    shutil.copytree(src, dst)
    spec = importlib.util.spec_from_file_location(f"make_docs_{src.name}", src / "make_docs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.write(dst)
    return dst


def runner(root):
    """run("cv_map.py", "check") runs an engine tool against the workspace at root."""
    def run(name, *args):
        env = {**os.environ, "JOBHUNT_ROOT": str(root), "PYTHONIOENCODING": "utf-8", "JOBHUNT_OFFLINE": "1"}
        return subprocess.run([sys.executable, str(TOOLS / name), *map(str, args)], cwd=root, env=env,
                              capture_output=True, text=True, encoding="utf-8")
    return run


@pytest.fixture
def sample(tmp_path):
    """The marketing-student sample workspace (single-column English CV)."""
    return make_workspace(SAMPLE, tmp_path / "workspace")


@pytest.fixture
def tool(sample):
    return runner(sample)


@pytest.fixture
def sample_de(tmp_path):
    """The German mechanical-engineer sample workspace (plain-paragraph German CV and letter)."""
    return make_workspace(SAMPLE_DE, tmp_path / "workspace-de")


@pytest.fixture
def tool_de(sample_de):
    return runner(sample_de)
