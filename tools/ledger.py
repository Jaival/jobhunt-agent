"""Seen-jobs ledger (data/seen_jobs.csv): every job the routine has screened, so nothing is processed twice.

A job matches the ledger by URL, by job id, or by normalised company + title (reposts count as seen). Two titles
at the same company are the same job when they have the same words in any order, after removing gender suffixes
((m/w/d), Werkstudent:in, Praktikantin, Kauffrau), punctuation and filler words (und, im, for, ...); a word split
by a hyphen matches the joined word (E-Commerce / eCommerce). Every other word must match exactly, so
"SAP FI" and "SAP CO", or Projektmanagement and Produktmanagement, stay different jobs.

A match expires after config.yaml `ledger_expiry_days` (default 90; 0 = never) when its verdict was screened,
skipped or closed: a job seen again after that counts as new, and `record` reuses its row (the note keeps the old
date and verdict). Tailored, applied, rejected and interview never expire.

Columns subscores (the five rubric sub-scores, "skills=4 seniority=5 ..."), engine_version and model came with
ledger_version 2 (data/seen_jobs.meta.json, so the CSV stays plain). Older ledgers load with them blank and get the
new header on the next save; `set` fills engine_version from engine/VERSION.

Usage (from the JobHunt folder):
    python engine/tools/ledger.py record                 add every job in data/candidates.json that isn't in the ledger
                                                  (verdict "screened"; "closed" when its page is gone; jobs the
                                                  reader couldn't read stay out, so the next run tries again)
    python engine/tools/ledger.py set <key|url|id> --verdict tailored|skipped|closed|applied|rejected|screened
                               [--score 72] [--subscores skills=4 seniority=5 language=3 location=5 hours=4]
                               [--model claude-opus-5-5] [--note "C1 German"]
    python engine/tools/ledger.py check "<company>" "<title>"   is this job already known?
                                                  (NEW, SEEN, or NEW (seen ..., expired))
    python engine/tools/ledger.py backfill               seed from the tracker, application folders and daily briefs
"""
import argparse
import csv
import datetime as dt
import itertools
import io
import json
import re
import sys
from pathlib import Path

import atomic
import score
import version
from config import CFG, ROOT
LEDGER = ROOT / "data" / "seen_jobs.csv"
META = LEDGER.with_name("seen_jobs.meta.json")
LEDGER_VERSION = 2
CANDIDATES = ROOT / "data" / "candidates.json"
FIELDS = ["key", "job_id", "source", "company", "title", "url", "first_seen", "verdict", "score", "note",
          "subscores", "engine_version", "model"]
EXPIRES = {"screened", "skipped", "closed"}  # verdicts whose match expires; every other verdict stays seen
EXPIRY_DAYS = CFG.get("ledger_expiry_days", 90)
if not isinstance(EXPIRY_DAYS, int) or isinstance(EXPIRY_DAYS, bool) or EXPIRY_DAYS < 0:
    sys.exit(f"config.yaml ledger_expiry_days must be a whole number of days (0 = never), not {EXPIRY_DAYS!r}")
FILLER = {"und", "and", "für", "fur", "for", "im", "in", "the", "der", "die", "das", "des", "mit", "with", "of",
          "zur", "zum", "am", "bei", "at", "a", "an", "to"}

LEGAL = r"\b(gmbh|mbh|ag|se|kg|kgaa|co|ohg|ug|e\.?\s?v|inc|ltd|llc|bv|b\.v|sa|gruppe|group|holding|deutschland|germany)\b"
GENDER = r"\((?:[mwfdxnb*/:|,\s.]|all genders?|alle|gn|mensch\*?|div\.?)+\)|\b(?:m/w/d|w/m/d|m/f/d|f/m/d|d/m/w|all genders)\b"


def norm_company(s):
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(LEGAL, " ", s)
    s = re.sub(r"[^a-z0-9äöüß]+", " ", s)
    return " ".join(s.split())


def norm_title(s):
    s = (s or "").lower()
    s = re.sub(GENDER, " ", s, flags=re.I)
    s = re.sub(r"werkstudent\s?\*?\s?:?in(nen)?\b", "werkstudent", s)
    s = re.sub(r"[^a-z0-9äöüß+#]+", " ", s)
    return " ".join(s.split())


def make_key(company, title):
    return f"{norm_company(company)}|{norm_title(title)}"


# Feminine job-title endings: Praktikantin, Managerin, Ingenieurinnen -> the masculine form, so both match.
FEMININE = re.compile(r"(ent|ant|er|or|eur|ist|log|ekt|at)(in|innen)$")
FEMININE_WORDS = ((r"kauffrau|kaufleute", "kaufmann"), (r"fachfrau|fachleute", "fachmann"))


def title_words(title):
    """The words of a title that decide whether two titles are the same job."""
    words = set()
    for w in norm_title(title).split():
        if w in FILLER:
            continue
        for pattern, repl in FEMININE_WORDS:
            w = re.sub(pattern, repl, w)
        words.add(FEMININE.sub(lambda m: m.group(1), w))
    return frozenset(words)


def same_words(wa, wb):
    """Two title_words sets name the same job: equal, or equal once hyphen-split words are joined."""
    if wa == wb:
        return True
    a, b = sorted(wa - wb), sorted(wb - wa)
    if not a or not b or len(a) > 3 or len(b) > 3:
        return False
    return bool({"".join(p) for p in itertools.permutations(a)} & {"".join(p) for p in itertools.permutations(b)})


def load():
    if not LEDGER.exists():
        return []
    with LEDGER.open(encoding="utf-8", newline="") as f:
        return [{k: r.get(k) or "" for k in FIELDS} for r in csv.DictReader(f)]  # older ledgers: new columns blank


def save(rows):
    """Write the whole ledger at once (atomic.py): a run stopped mid-save keeps the old ledger."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    atomic.write_text(LEDGER, buf.getvalue(), newline="")
    atomic.write_text(META, json.dumps({"ledger_version": LEDGER_VERSION}) + "\n")


class Index:
    def __init__(self, rows):
        self.rows = rows
        self.by_key = {r["key"]: r for r in rows}
        self.by_url = {r["url"]: r for r in rows if r["url"]}
        self.by_id = {r["job_id"]: r for r in rows if r["job_id"]}
        self.by_company = {}  # company key -> [(title_words, row)]
        for r in rows:
            self.by_company.setdefault(r["key"].split("|")[0], []).append((title_words(r["title"]), r))

    def find(self, company="", title="", url="", job_id=""):
        """The row this job matches, or None when there is none or it has expired."""
        r = self.match(company, title, url, job_id)
        return None if r and self.expired(r) else r

    @staticmethod
    def expired(row, today=None):
        if not EXPIRY_DAYS or row["verdict"] not in EXPIRES:
            return False
        try:
            seen = dt.date.fromisoformat(row["first_seen"])
        except ValueError:  # blank or hand-edited: keep it seen
            return False
        return ((today or dt.date.today()) - seen).days > EXPIRY_DAYS

    def match(self, company="", title="", url="", job_id=""):
        """The row this job matches, expired or not."""
        if url and url in self.by_url:
            return self.by_url[url]
        if job_id and job_id in self.by_id:
            return self.by_id[job_id]
        key = make_key(company, title)
        if key in self.by_key:
            return self.by_key[key]
        comp = key.split("|")[0]
        words = title_words(title)
        for w, r in self.by_company.get(comp, []) if comp else []:
            if same_words(words, w):
                return r
        return None

    def add(self, **kw):
        row = {k: "" for k in FIELDS}
        row.update({k: ("" if v is None else str(v)) for k, v in kw.items() if k in FIELDS})
        row["key"] = row["key"] or make_key(row["company"], row["title"])
        row["first_seen"] = row["first_seen"] or f"{dt.date.today():%Y-%m-%d}"
        self.rows.append(row)
        self.by_key[row["key"]] = row
        if row["url"]:
            self.by_url[row["url"]] = row
        if row["job_id"]:
            self.by_id[row["job_id"]] = row
        self.by_company.setdefault(row["key"].split("|")[0], []).append((title_words(row["title"]), row))
        return row


# ---------- backfill ----------

def backfill(idx):
    added = 0
    import openpyxl
    ws = openpyxl.load_workbook(ROOT / "tracker" / "Job_Application_Tracker.xlsx", read_only=True)["Applications"]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))
    for r in rows:
        d = dict(zip(hdr, r))
        if not d.get("Company"):
            continue
        if not idx.find(d["Company"], d["Title"], d.get("Job URL") or "", d.get("Job ID") or ""):
            date = d.get("Date")
            idx.add(job_id=d.get("Job ID"), source="backfill:tracker", company=d["Company"], title=d["Title"],
                    url=d.get("Job URL"), verdict=(d.get("Status") or "applied").lower(), score=d.get("Fit Score"),
                    first_seen=f"{date:%Y-%m-%d}" if hasattr(date, "strftime") else "")
            added += 1
    import appdirs
    for job in sorted(d / "job.md" for _, d in appdirs.iter_folders() if (d / "job.md").exists()):
        text = job.read_text(encoding="utf-8")
        title = re.search(r"^#\s+(.+)$", text, re.M)
        comp = re.search(r"\*\*Company:\*\*\s*([^,(\n]+)", text)
        url = re.search(r"\*\*URL:\*\*\s*(https?://\S+)", text)
        if not title:
            continue
        company = comp.group(1).strip() if comp else job.parent.name.split("_")[1]
        u = url.group(1).rstrip(").,") if url else ""
        if not idx.find(company, title.group(1), u):
            idx.add(source="backfill:folder", company=company, title=title.group(1), url=u,
                    verdict="tailored", first_seen=job.parent.name[:10], note=job.parent.name)
            added += 1
    # Briefs: bold list items "- **Company, Title, Place (score).**" and the links in them.
    item = re.compile(r"^\s*-\s+\*\*([^*]+?)\s*\((\d{2})[^)]*\)\.?\*\*(.*)$", re.M)
    for brief in sorted((ROOT / "daily").glob("*.md")):
        text = brief.read_text(encoding="utf-8")
        for m in item.finditer(text):
            parts = [p.strip() for p in m.group(1).split(",")]
            if len(parts) < 2:
                continue
            company, title = parts[0], parts[1]
            u = first_url(m.group(3))
            if not idx.find(company, title, u):
                idx.add(source="backfill:brief", company=company, title=title, url=u, verdict="screened",
                        score=m.group(2), first_seen=brief.stem)
                added += 1
        for row in re.finditer(r"^\|\s*\d\s*\|[^|]*\|([^|]+)\|([^|]+)\|\s*(\d{2})\s*\|.*?\((https?://[^)]+)\)", text, re.M):
            title, company, sc, u = (g.strip() for g in row.groups())
            if not idx.find(company, title, u):
                idx.add(source="backfill:brief", company=company, title=title, url=u, verdict="screened",
                        score=sc, first_seen=brief.stem)
                added += 1
        # Any other Arbeitsagentur / Arbeitnow link in a brief: seed it by id (skipped lists are free text).
        for u in re.findall(r"https?://www\.(?:arbeitsagentur\.de/jobsuche/jobdetail/[\w-]+|arbeitnow\.com/jobs/companies/[\w-]+/[\w-]+)", text):
            job_id = ("ba-" + u.rsplit("/", 1)[1]) if "arbeitsagentur" in u else ("an-" + u.rsplit("/", 1)[1])
            if not idx.find(url=u, job_id=job_id):
                company, title = (u.rsplit("/", 2)[1:] if "arbeitnow" in u else ("", ""))
                idx.add(key=f"url|{u}", job_id=job_id, source="backfill:brief-link", company=company,
                        title=re.sub(r"-\d+$", "", title).replace("-", " "), url=u, verdict="screened",
                        first_seen=brief.stem)
                added += 1
    return added


def first_url(text):
    m = re.search(r"https?://[^\s)>\]]+", text or "")
    return m.group(0) if m else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("record")
    s = sub.add_parser("set")
    s.add_argument("which")
    s.add_argument("--verdict", required=True)
    s.add_argument("--score")
    s.add_argument("--note")
    s.add_argument("--subscores", nargs=len(score.CRITERIA), metavar="CRITERION=N")
    s.add_argument("--model")
    c = sub.add_parser("check")
    c.add_argument("company")
    c.add_argument("title")
    sub.add_parser("backfill")
    a = ap.parse_args()
    idx = Index(load())

    if a.cmd == "check":
        r = idx.match(a.company, a.title)
        if r and idx.expired(r):
            print(f"NEW (seen {r['first_seen']} {r['verdict']} {r['score']}, expired) {r['url']}")
        else:
            print(f"SEEN {r['first_seen']} {r['verdict']} {r['score']} {r['url']}" if r else "NEW")
        return 0
    if a.cmd == "backfill":
        n = backfill(idx)
        save(idx.rows)
        print(f"backfill: {n} rows added, {len(idx.rows)} in ledger")
        return 0
    if a.cmd == "record":
        cands = json.loads(CANDIDATES.read_text(encoding="utf-8"))
        n = unread = 0
        for j in cands["jobs"]:
            error = j.get("read_error")
            if error and error != "gone":  # the reader couldn't read it: not seen, the next run tries again
                unread += 1
                continue
            verdict = "closed" if error else "screened"
            r = idx.match(j["company"], j["title"], j["url"], j["id"])
            if r and idx.expired(r):  # seen again after the expiry: the same row starts over
                old = f"seen {r['first_seen']} {r['verdict']} {r['score']}".strip()
                r.update(job_id=j["id"], url=j["url"], first_seen=f"{dt.date.today():%Y-%m-%d}", verdict=verdict,
                         score="", note=f"posted {j.get('posted') or '?'}; {old}")
                n += 1
            elif not r:
                idx.add(job_id=j["id"], source=j["source"], company=j["company"], title=j["title"], url=j["url"],
                        verdict=verdict, note=f"posted {j.get('posted') or '?'}")
                n += 1
        save(idx.rows)
        print(f"recorded {n} new jobs, {len(idx.rows)} in ledger"
              + (f"; {unread} unread job(s) left out, the next run tries them again" if unread else ""))
        return 0
    if a.cmd == "set":
        r = idx.by_key.get(a.which) or idx.by_url.get(a.which) or idx.by_id.get(a.which)
        if not r:
            print(f"FAILED: '{a.which}' is not in the ledger", file=sys.stderr)
            return 1
        if a.subscores:
            try:
                sub = score.parse(a.subscores)
            except ValueError as e:
                print(f"FAILED: {e}", file=sys.stderr)
                return 1
            if set(sub) != set(score.CRITERIA) or max(sub.values()) > 5:
                print(f"FAILED: --subscores needs each of {', '.join(score.CRITERIA)} once, 0 to 5", file=sys.stderr)
                return 1
            r["subscores"] = " ".join(f"{k}={sub[k]}" for k in score.CRITERIA)
        if a.model:
            r["model"] = a.model
        r["engine_version"] = version.version()
        r["verdict"] = a.verdict
        if a.score:
            r["score"] = a.score
        if a.note:
            r["note"] = a.note
        save(idx.rows)
        print(f"OK {r['key']}: {r['verdict']} {r['score']}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
