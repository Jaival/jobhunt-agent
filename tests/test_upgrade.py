"""upgrade.py migrate: an old config.yaml (an edited engine's keys) becomes this engine's, with a CV map."""
import yaml

import upgrade

OLD_CONFIG = """# my settings
applicant: Jonas Becker
file_prefix: Jonas_Becker
master_cv: cv/Jonas_Becker_Lebenslauf.docx
master_letter: cv/Jonas_Becker_Anschreiben.docx
variants: cv/variants.yaml
letter_city: Regensburg   # date line
name_in_master: Jonas Michael Becker
letter_languages: [de, en]
internship_months: 6
search:
  home: {wo: Regensburg, umkreis: 50}
  keep_titles: [simulation, berechnung, konstruktion]
  drop_titles: [senior, praktik]
  regions: [Bayern]
cv_layout:
  headline: 1
  sections: [PROFIL, TECHNISCHE KOMPETENZEN, BERUFSERFAHRUNG, PROJEKTE, AUSBILDUNG]
  projects: PROJEKTE
  technical: TECHNISCHE KOMPETENZEN
letter_layout: {recipient: [4, 6], date: 8, subject: 10, greeting: 12, closing: 15}
"""


def test_migrate_edited_engine_config(tool_de, sample_de):
    (sample_de / "config.yaml").write_text(OLD_CONFIG, encoding="utf-8")
    (sample_de / "cv" / "layout.yaml").unlink()
    r = tool_de("upgrade.py", "migrate")
    assert r.returncode == 0, r.stderr + r.stdout
    text = (sample_de / "config.yaml").read_text(encoding="utf-8")
    cfg = yaml.safe_load(text)
    assert cfg["config_version"] == 2 and text.startswith("# my settings\nconfig_version: 2")
    assert "letter_city: Regensburg   # date line" in text                   # untouched lines keep their comments
    assert cfg["profile"]["include_titles"] == ["simulation", "berechnung", "konstruktion"]
    assert cfg["profile"]["exclude_titles"] == ["senior", "praktik"]
    assert cfg["search"] == {"home": {"wo": "Regensburg", "umkreis": 50}, "regions": ["Bayern"]}
    assert cfg["internship_duration"] == "6 months" and cfg["layout"] == "cv/layout.yaml"
    assert not {"cv_layout", "letter_layout", "internship_months"} & set(cfg)
    assert "CV map: OK" in r.stdout, r.stdout
    assert "section projects: ['FEM-Analyse Radträger', 'Formula Student Fahrwerk'" in r.stdout
    assert "letter recipient: 3 line(s)" in r.stdout and "letter closing: Mit freundlichen" in r.stdout
    assert "date: Regensburg, 01.10.2026" in r.stdout
    r = tool_de("build_application.py", "applications/2026-10-23_Beispiel-Werke_Berechnungsingenieur", "--no-pdf")
    assert r.returncode == 0, r.stderr
    assert tool_de("setup_check.py", "--init", "--json").returncode == 0


def test_same_title_results_as_keep_titles():
    """A profile from keep_titles keeps exactly what the edited engine kept: drop wins, then keep, any role type."""
    from scope import Scope
    keep, drop = ["simulation", "berechnung"], ["senior", "praktik"]
    s = Scope({"role_types": upgrade.STOCK_PROFILE["role_types"], "include_titles": keep, "exclude_titles": drop})
    import re
    old = lambda t: not re.search("|".join(drop), t, re.I) and bool(re.search("|".join(keep), t, re.I))
    for title in ["Simulationsingenieur (m/w/d)", "Senior Berechnungsingenieur", "Praktikum Simulation",
                  "Werkstudent Berechnung", "Konstrukteur", "Berechnungsingenieur", "Student Assistant Simulation"]:
        assert s.in_scope(title) == old(title), title


def test_set_and_drop_key():
    text = "# head\na: 1  # keep\nb:\n  x: 1\n# about c\nc: 3\n"
    t = upgrade.set_key(text, "b", {"y": 2})
    assert t == "# head\na: 1  # keep\nb: {y: 2}\n# about c\nc: 3\n"
    assert upgrade.drop_key(t, "b") == "# head\na: 1  # keep\nc: 3\n"
    assert upgrade.set_key(text, "d", [1, 2]).endswith("c: 3\nd: [1, 2]\n")
