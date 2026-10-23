"""Title filter and role-type guess, built from the `profile:` block of config.yaml (routine step 3).

Every list entry is a word or a regular-expression fragment, matched case-insensitively anywhere in the
title ("sales", "werkstudent", r"\bit\b"). Onboarding writes the profile; see
templates/workspace/config.yaml for the keys:

    role_types             which role types to keep: Werkstudent, HiWi, Internship, Thesis, Junior
                           (titles without a role word count as Junior)
    include_titles         a title must match one of these (empty = every title in the field passes)
    junior_include_titles  optional narrower list for Junior roles (default: include_titles)
    junior_exclude_titles  optional extra drops for Junior roles only
    exclude_titles         always dropped (default: seniority words, apprenticeships, unsolicited applications)
    score_bonus            skills that add points when scoring (read by Claude, not by this module)
"""
import re

ROLE_TYPES = [
    ("Thesis", re.compile(r"masterarbeit|abschlussarbeit|thesis|bachelorarbeit", re.I)),
    ("HiWi", re.compile(r"hiwi|studentische hilfskraft|wissenschaftliche hilfskraft|studentische aushilfe", re.I)),
    ("Internship", re.compile(r"praktik|intern\b|internship", re.I)),
    ("Werkstudent", re.compile(r"werkstudent|working student|studentische|student\b", re.I)),
]
JUNIOR = re.compile(r"junior|einsteiger|berufseinstieg|graduate|absolvent|entry", re.I)
STUDENT_TYPES = ("Werkstudent", "HiWi", "Internship", "Thesis")
ALL_TYPES = STUDENT_TYPES + ("Junior",)
DEFAULT_EXCLUDE = ["senior", r"\blead\b", "principal", "staff", "head of", "director", "manager", "leiter",
                   "ausbildung", "azubi", "unsolicited", "initiativ"]


def role_type(title):
    for name, rx in ROLE_TYPES:
        if rx.search(title):
            return name
    return "Junior" if JUNIOR.search(title) else "Other"


def _rx(words):
    """One case-insensitive regex from a list of fragments, or None for an empty list."""
    words = [w for w in (words or []) if str(w).strip()]
    return re.compile("|".join(f"(?:{w})" for w in words), re.I) if words else None


class Scope:
    def __init__(self, profile):
        if not isinstance(profile, dict):
            raise ValueError("config.yaml has no profile: block (run the setup: engine/ONBOARDING.md)")
        unknown = set(profile.get("role_types") or ALL_TYPES) - set(ALL_TYPES)
        if unknown:
            raise ValueError(f"profile.role_types: unknown {sorted(unknown)}; use {list(ALL_TYPES)}")
        self.types = set(profile.get("role_types") or ALL_TYPES)
        self.include = _rx(profile.get("include_titles"))
        self.junior_include = _rx(profile.get("junior_include_titles")) or self.include
        self.junior_exclude = _rx(profile.get("junior_exclude_titles"))
        excl = profile.get("exclude_titles")
        self.exclude = _rx(DEFAULT_EXCLUDE if excl is None else excl)

    def in_scope(self, title):
        if self.exclude and self.exclude.search(title):
            return False
        rt = role_type(title)
        if rt in STUDENT_TYPES:
            return rt in self.types and (not self.include or bool(self.include.search(title)))
        # Junior and unlabelled titles
        if "Junior" not in self.types:
            return False
        if self.junior_exclude and self.junior_exclude.search(title):
            return False
        return not self.junior_include or bool(self.junior_include.search(title))
