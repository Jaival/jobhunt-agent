"""Starts the engine's reader-reply hook (engine/tools/hooks/reader_reply.py) for Claude Code's SubagentStop hook.

Installed by engine/tools/setup_check.py --init. It does nothing when the engine has no such hook (an older engine
after a rollback); the routine then writes the ad reader's reply itself.
"""
import runpy
import sys
from pathlib import Path

hook = Path(__file__).resolve().parents[2] / "engine" / "tools" / "hooks" / "reader_reply.py"
if hook.is_file():
    sys.argv = [str(hook)]
    runpy.run_path(str(hook), run_name="__main__")
