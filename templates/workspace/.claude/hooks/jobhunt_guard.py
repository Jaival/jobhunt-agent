"""Starts the engine's guard (engine/tools/hooks/guard.py) for Claude Code's PreToolUse hook.

Installed by engine/tools/setup_check.py --init. It lets every call through when the engine has no guard (an
older engine after a rollback): a hook command whose file is missing would exit 2 and block every tool call.
"""
import runpy
import sys
from pathlib import Path

guard = Path(__file__).resolve().parents[2] / "engine" / "tools" / "hooks" / "guard.py"
if guard.is_file():
    sys.argv = [str(guard)]
    runpy.run_path(str(guard), run_name="__main__")
