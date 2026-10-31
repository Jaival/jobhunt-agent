"""On-request workflows as workspace skills (S3-3): each skill exists, is installed, and keeps its old phrases."""
import pytest
import yaml

import permissions

SKILLS = permissions.TEMPLATE.parent / "skills"
ENGINE = permissions.TEMPLATE.parents[3]
PHRASES = {"ats-review": ["run the ATS review", "check my CV"],
           "update-engine": ["update the engine", "upgrade the engine"],
           "remap-cv": ["remap my CV"],
           "onboarding": ["setup_check.py reports anything as TODO"]}


@pytest.mark.parametrize("name", PHRASES)
def test_skill_keeps_its_trigger_phrases(name):
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    front = yaml.safe_load(text.split("---\n", 2)[1])
    assert front["name"] == name
    assert all(p in front["description"] for p in PHRASES[name])
    assert f"skill `{name}`" in (ENGINE / "RULES.md").read_text(encoding="utf-8")   # fallback without the skill


def test_routine_is_only_the_daily_run():
    routine = (ENGINE / "ROUTINE.md").read_text(encoding="utf-8")
    assert "On request (" not in routine


def test_install_copies_the_skills(tmp_path):
    added = permissions.install(tmp_path, {})
    assert {f"file .claude/skills/{n}/SKILL.md" for n in PHRASES} <= set(added)
