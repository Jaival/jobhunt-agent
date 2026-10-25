"""The eval seed (S1-12): every ad is well-formed, holds no contact data, and its title_filter label matches scope.py."""
import re

import pytest
import yaml

from conftest import ENGINE, SAMPLE
from scope import Scope

ADS = sorted((ENGINE / "tests" / "evals" / "ads").glob("*.md"))
SCOPE = Scope(yaml.safe_load((SAMPLE / "config.yaml").read_text(encoding="utf-8"))["profile"])
ROLE_TYPES = {"Werkstudent", "Internship", "HiWi", "Thesis", "Junior", "Other"}
GERMAN = {"none", "basic", "B2", "C1+", "unknown"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.I)
PHONE = re.compile(r"(?:\+49|\(0\d+\)|\b0\d{2,5})[\d /()-]{5,}\d")


def load(path):
    _, front, body = path.read_text(encoding="utf-8").split("---\n", 2)
    return yaml.safe_load(front), body


def test_seed_size():
    assert len(ADS) >= 30


@pytest.mark.parametrize("path", ADS, ids=lambda p: p.stem)
def test_ad(path):
    meta, body = load(path)
    exp = meta["expected"]
    assert meta["title"] and meta["company"] and meta["url"].startswith("https://") and len(body) > 300
    assert exp["title_filter"] == ("pass" if SCOPE.in_scope(meta["title"]) else "drop")
    assert exp["role_type"] in ROLE_TYPES and exp["german_required"] in GERMAN and exp["note"]
    if exp["in_scope"]:
        low, high = exp["score"]
        assert 0 <= low <= high <= 100
        if exp["hard_mismatch"]:
            assert high < 60
    else:
        assert exp["score"] is None and exp["hard_mismatch"] is None
    assert not EMAIL.search(body) and not PHONE.search(body)
