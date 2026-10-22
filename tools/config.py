"""Workspace root and personal settings for every tool.

The tools live in <workspace>/engine/tools/ (the public jobhunt-agent repo); everything personal lives in
the workspace around it: config.yaml, the master CV, applications/, tracker/, data/ and so on.

ROOT is $JOBHUNT_ROOT if set, otherwise the folder two levels above this file (engine/tools -> engine ->
workspace). CFG is <ROOT>/config.yaml; see templates/workspace/config.yaml for the keys.
"""
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("JOBHUNT_ROOT") or Path(__file__).resolve().parents[2])
CONFIG = ROOT / "config.yaml"

if not CONFIG.exists():
    sys.exit(f"config.yaml not found in {ROOT}. Copy engine/templates/workspace/config.yaml there and fill it in.")
CFG = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}

REQUIRED = ("applicant", "file_prefix", "master_cv", "master_letter", "variants", "letter_city")
missing = [k for k in REQUIRED if not CFG.get(k)]
if missing:
    sys.exit(f"config.yaml is missing: {', '.join(missing)}")


def path(key):
    """A path from config.yaml, relative to the workspace."""
    return ROOT / CFG[key]
