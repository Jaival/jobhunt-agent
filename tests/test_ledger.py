"""Ledger matching: reposts count as seen, different jobs at the same company don't (S1-5)."""
import os

import pytest

from conftest import SAMPLE

os.environ["JOBHUNT_ROOT"], _old = str(SAMPLE), os.environ.get("JOBHUNT_ROOT")
import ledger  # noqa: E402  (config.py reads JOBHUNT_ROOT on import)
if _old is None:
    del os.environ["JOBHUNT_ROOT"]
else:
    os.environ["JOBHUNT_ROOT"] = _old


def index(*titles, company="Acme GmbH"):
    idx = ledger.Index([])
    for i, t in enumerate(titles):
        idx.add(company=company, title=t, url=f"https://example.org/{i}", verdict="screened")
    return idx


@pytest.mark.parametrize("seen, new", [
    ("Werkstudent SAP FI (m/w/d)", "Werkstudent SAP CO (m/w/d)"),
    ("Werkstudent HR", "Werkstudent IT"),
    ("Junior Marketing Manager", "Senior Marketing Manager"),
    ("Werkstudent Marketing", "Werkstudent Marketing und Kommunikation"),
    ("Praktikum Frontend Development", "Praktikum Backend Development"),
    ("Working Student Data Analyst", "Working Student Data Engineer"),
])
def test_different_jobs_stay_apart(seen, new):
    assert index(seen).find("Acme AG", new) is None


@pytest.mark.parametrize("seen, new", [
    ("Werkstudent SAP FI (m/w/d)", "Werkstudent:in SAP FI (w/m/d)"),   # gender suffixes
    ("Werkstudent Marketing (all genders)", "Werkstudent - Marketing"),  # punctuation
    ("Marketing Werkstudent", "Werkstudent Marketing"),                  # word order
    ("Werkstudent im Marketing", "Werkstudent Marketing"),               # filler word
    ("Werkstudentin Online-Marketing", "Werkstudent Online Marketing"),  # small spelling change in a long word
    ("Working Student E-Commerce", "Working Student eCommerce"),
])
def test_reposts_still_match(seen, new):
    assert index(seen).find("Acme AG", new) is not None


def test_other_company_never_matches():
    assert index("Werkstudent Marketing").find("Beta GmbH", "Werkstudent Marketing") is None


def test_picks_the_right_one_of_several():
    idx = index("Werkstudent SAP FI", "Werkstudent SAP CO")
    assert idx.find("Acme", "Werkstudent SAP CO (m/w/d)")["title"] == "Werkstudent SAP CO"
