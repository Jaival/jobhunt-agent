"""Ledger matching: reposts count as seen, different jobs at the same company don't (S1-5)."""
import pytest


def index(ledger, *titles, company="Acme GmbH"):
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
    ("Werkstudent Projektmanagement", "Werkstudent Produktmanagement"),
    ("Elektriker (m/w/d)", "Elektroniker (m/w/d)"),
    ("Logistik Werkstudent", "Logistiker Werkstudent"),
])
def test_different_jobs_stay_apart(ledger_mod, seen, new):
    assert index(ledger_mod, seen).find("Acme AG", new) is None


@pytest.mark.parametrize("seen, new", [
    ("Werkstudent SAP FI (m/w/d)", "Werkstudent:in SAP FI (w/m/d)"),          # gender suffixes
    ("Werkstudent Marketing (all genders)", "Werkstudent - Marketing"),         # punctuation
    ("Marketing Werkstudent", "Werkstudent Marketing"),                         # word order
    ("Werkstudent im Marketing", "Werkstudent Marketing"),                      # filler word
    ("Praktikant Online-Marketing", "Praktikantin Online Marketing"),           # feminine form
    ("Junior Projektmanager (m/w/d)", "Junior Projektmanagerin"),
    ("Industriekaufmann Vertrieb (m/w/d)", "Industriekauffrau Vertrieb (m/w/d)"),
    ("Kaufmann / Kauffrau für Büromanagement", "Kauffrau für Büromanagement"),
    ("Working Student E-Commerce", "Working Student eCommerce"),                # hyphenated word
    ("Werkstudent E-Commerce und Marketing", "Marketing Werkstudent eCommerce"),
])
def test_reposts_still_match(ledger_mod, seen, new):
    assert index(ledger_mod, seen).find("Acme AG", new) is not None


def test_words_that_only_look_feminine_stay(ledger_mod):
    assert ledger_mod.title_words("Werkstudent Berlin Medizin Admin") == {"werkstudent", "berlin", "medizin", "admin"}


def test_other_company_never_matches(ledger_mod):
    assert index(ledger_mod, "Werkstudent Marketing").find("Beta GmbH", "Werkstudent Marketing") is None


def test_picks_the_right_one_of_several(ledger_mod):
    idx = index(ledger_mod, "Werkstudent SAP FI", "Werkstudent SAP CO")
    assert idx.find("Acme", "SAP CO Werkstudent (m/w/d)")["title"] == "Werkstudent SAP CO"  # word path, not the key


def test_rows_from_an_older_ledger_match(ledger_mod):
    # Rows keep the key they were saved with; matching re-reads their title, so no migration is needed.
    row = dict.fromkeys(ledger_mod.FIELDS, "")
    row.update(key="acme|industriekauffrau vertrieb", company="Acme", title="Industriekauffrau Vertrieb")
    assert ledger_mod.Index([row]).find("Acme", "Industriekaufmann Vertrieb") is row
