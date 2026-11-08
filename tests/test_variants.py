"""Stale cv/variants.yaml entries (master text no longer in the master CV): only the ones a build uses stop it."""
from test_sample_workspace import APP

STALE = '\nold.bullet:\n  group: old\n  master: "A bullet the master CV no longer has."\n'


def add_stale(sample):
    path = sample / "cv" / "variants.yaml"
    path.write_text(path.read_text(encoding="utf-8") + STALE, encoding="utf-8")


def test_unused_stale_variant_only_warns(tool, sample):
    add_stale(sample)
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    assert "warning: cv/variants.yaml entries not in the master CV (unused here): old.bullet" in r.stdout


def test_reordered_stale_variant_fails(tool, sample):
    add_stale(sample)
    app = sample / APP / "application.md"
    app.write_text(app.read_text(encoding="utf-8").replace("  bullets:\n", "  bullets:\n    old: [bullet]\n", 1),
                   encoding="utf-8")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "variant(s) ['old.bullet']: master text not found exactly once" in r.stderr


def test_cv_map_check_lists_stale_variants(tool, sample):
    add_stale(sample)
    r = tool("cv_map.py", "check")
    assert r.returncode == 0, r.stdout
    assert "WARNING cv/variants.yaml: master text not in the master CV: old.bullet" in r.stdout
