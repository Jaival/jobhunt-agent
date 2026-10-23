import pytest
import yaml

from conftest import SAMPLE
from scope import Scope, role_type

MARKETING = yaml.safe_load((SAMPLE / "config.yaml").read_text(encoding="utf-8"))["profile"]


@pytest.mark.parametrize("title, expected", [
    ("Werkstudent Online Marketing (m/w/d)", "Werkstudent"),
    ("Working Student Social Media", "Werkstudent"),
    ("Studentische Hilfskraft Kommunikation", "HiWi"),
    ("Praktikum Content Creation", "Internship"),
    ("Masterarbeit Markenführung", "Thesis"),
    ("Junior Brand Manager", "Junior"),
    ("Content Marketing Specialist", "Other"),
])
def test_role_type(title, expected):
    assert role_type(title) == expected


@pytest.mark.parametrize("title, keep", [
    ("Werkstudent Online Marketing (m/w/d)", True),
    ("Praktikum Social Media & Content", True),
    ("Junior Content Marketing", True),
    ("Content Marketing Specialist", True),           # no role word counts as junior
    ("Werkstudent Software Development", False),      # not her field
    ("Senior Marketing Manager", False),              # seniority
    ("Werkstudent Vertrieb und Marketing", False),    # sales is excluded
    ("Studentische Hilfskraft Kommunikation", False), # HiWi isn't in her role_types
    ("Masterarbeit Marketing", False),                # nor Thesis
    ("Ausbildung Kaufmann für Marketingkommunikation", False),
])
def test_marketing_profile(title, keep):
    assert Scope(MARKETING).in_scope(title) is keep


def test_junior_lists():
    s = Scope({"role_types": ["Werkstudent", "Junior"], "include_titles": ["devops", "software"],
               "junior_include_titles": ["devops"], "junior_exclude_titles": ["informatik"]})
    assert s.in_scope("Werkstudent Software Engineering")
    assert not s.in_scope("Junior Software Engineer")          # junior list is narrower
    assert s.in_scope("Junior DevOps Engineer")
    assert not s.in_scope("Junior DevOps Informatik")


def test_empty_include_keeps_every_field():
    s = Scope({"role_types": ["Werkstudent"], "include_titles": []})
    assert s.in_scope("Werkstudent Buchhaltung")
    assert not s.in_scope("Junior Buchhalter")                  # Junior not chosen


def test_default_excludes():
    s = Scope({"role_types": ["Junior"]})
    assert not s.in_scope("Lead Designer")
    assert not s.in_scope("Initiativbewerbung")


def test_bad_profiles():
    with pytest.raises(ValueError, match="no profile"):
        Scope(None)
    with pytest.raises(ValueError, match="unknown"):
        Scope({"role_types": ["Trainee"]})
