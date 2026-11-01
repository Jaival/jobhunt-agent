"""Title filter and role-type guess, built from the `profile:` block of config.yaml (routine step 3).

Every list entry is a word or a regular-expression fragment, matched case-insensitively ("sales", "werkstudent",
r"\bit\b"). Include words match anywhere in the title. Exclude words match at the start of a word only, so
"art" drops "Art Direction" but not "Startup", and "senior" still drops "Seniorberater". The seniority words in
SENIORITY (manager, staff, leiter, lead) drop only Junior and unlabelled titles, and match anywhere, as German
compounds need ("Teamleiter", "Projektmanager"): "Werkstudent Produktmanagement" or "Praktikum
Leiterplattendesign" stays. Onboarding writes the profile; see
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
# Exclude entries that say a role leads others. A student role can carry them ("Werkstudent Produktmanager"), so
# they drop only Junior and unlabelled titles.
SENIORITY = {"manager", "staff", "leiter", "lead", r"\blead\b"}


def role_type(title):
    for name, rx in ROLE_TYPES:
        if rx.search(title):
            return name
    return "Junior" if JUNIOR.search(title) else "Other"


def _rx(words, start=""):
    """One case-insensitive regex from a list of fragments, or None for an empty list. start=r"\b" makes each
    fragment match only at the start of a word."""
    words = [w for w in (words or []) if str(w).strip()]
    return re.compile("|".join(f"{start}(?:{w})" for w in words), re.I) if words else None


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
        excl = profile.get("exclude_titles")
        excl = DEFAULT_EXCLUDE if excl is None else excl
        senior = [w for w in excl if str(w).strip().lower() in SENIORITY]
        self.exclude = _rx([w for w in excl if w not in senior], r"\b")
        # German seniority titles are compounds (Teamleiter, Projektmanager): these match anywhere in the word.
        self.junior_exclude = _rx(senior + list(profile.get("junior_exclude_titles") or []))

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


def search_areas(search):
    """Arbeitsagentur location passes from config.yaml search: the home area, then search.areas (a list of
    {wo, umkreis}); without search.areas, one nationwide pass."""
    search = search or {}
    areas = [search.get("home") or {}]
    areas += search["areas"] if search.get("areas") is not None else [{}]
    return [a for i, a in enumerate(areas) if a not in areas[:i]]


class Region:
    """config.yaml search.regions (federal states, e.g. [Bayern]): keep only jobs inside them.

    Arbeitsagentur jobs are matched by the ad's region field, else by postcode prefix (search.region_plz); other
    sources by place names in the location (search.region_places, plus the region names). A job without any
    location is kept and marked location_check, so the routine checks it while scoring."""

    def __init__(self, search):
        search = search or {}
        self.regions = [str(r).lower() for r in search.get("regions") or []]
        self.plz = [str(p) for p in search.get("region_plz") or []]
        self.places = [str(p).lower() for p in search.get("region_places") or []] + self.regions
        if "bayern" in self.regions:
            self.places.append("bavaria")

    def keep(self, job):
        if not self.regions:
            return True
        region = (job.get("region") or "").lower()
        if region:
            return region in self.regions
        plz = str(job.get("plz") or "")
        if plz and self.plz:
            return any(plz.startswith(p) for p in self.plz)
        loc = (job.get("location") or "").lower()
        if not loc:
            job["location_check"] = True
            return True
        return any(p in loc for p in self.places)
