"""Seen-jobs ledger (data/seen_jobs.csv): every job the routine has screened, so nothing is processed twice.

A job matches the ledger by URL, by job id, or by normalised company + title (reposts count as seen). Two titles
at the same company are the same job when they have the same words in any order, ignoring gender suffixes,
punctuation and filler words; words of 6+ letters may differ slightly (Werkstudentin / Werkstudent). Short words
must match exactly, so "SAP FI" and "SAP CO" stay different jobs.

Usage (from the JobHunt folder):
    python engine/tools/ledger.py record                 add every job in data/candidates.json that isn't in the ledger
                                                  (verdict "screened")
    python engine/tools/ledger.py set <key|url|id> --verdict tailored|skipped|closed|applied|rejected|screened
                               [--score 72] [--note "C1 German"]
    python engine/tools/ledger.py check "<company>" "<title>"   is this job already known?
    python engine/tools/ledger.py backfill               seed from the tracker, application folders and daily briefs
"""
import argparse
import csv
import datetime as dt
import difflib
import io
import json
import re
import sys
from pathlib import Path

import atomic
from config import ROOT
LEDGER = ROOT / "data" / "seen_jobs.csv"
CANDIDATES = ROOT / "data" / "candidates.json"
FIELDS = ["key", "job_id", "source", "company", "title", "url", "first_seen", "verdict", "score", "note"]
SIMILAR_WORD = 0.85  # two title words this similar (both 6+ letters) count as the same word
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


def same_title(a, b):
    """Two normalised titles (norm_title) name the same job: see the module docstring."""
    if a == b or a.replace(" ", "") == b.replace(" ", ""):  # "e commerce" = "ecommerce"
        return True
    wa, wb = set(a.split()) - FILLER, set(b.split()) - FILLER
    if not wa or len(wa) != len(wb):
        return wa == wb
    rest = wb - wa
    for w in wa - wb:
        near = [v for v in rest if min(len(w), len(v)) >= 6 and difflib.SequenceMatcher(None, w, v).ratio() >= SIMILAR_WORD]
        if not near:
            return False
        rest.discard(max(near, key=lambda v: difflib.SequenceMatcher(None, w, v).ratio()))
    return True


def load():
    if not LEDGER.exists():
        return []
    with LEDGER.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save(rows):
    """Write the whole ledger at once (atomic.py): a run stopped mid-save keeps the old ledger."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    atomic.write_text(LEDGER, buf.getvalue(), newline="")


class Index:
    def __init__(self, rows):
        self.rows = rows
        self.by_key = {r["key"]: r for r in rows}
        self.by_url = {r["url"]: r for r in rows if r["url"]}
        self.by_id = {r["job_id"]: r for r in rows if r["job_id"]}
        self.by_company = {}
        for r in rows:
            self.by_company.setdefault(r["key"].split("|")[0], []).append(r)

    def find(self, company="", title="", url="", job_id=""):
        if url and url in self.by_url:
            return self.by_url[url]
        if job_id and job_id in self.by_id:
            return self.by_id[job_id]
        key = make_key(company, title)
        if key in self.by_key:
            return self.by_key[key]
        comp, t = key.split("|")
        for r in self.by_company.get(comp, []) if comp else []:
            if same_title(t, r["key"].split("|")[1]):
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
        self.by_company.setdefault(row["key"].split("|")[0], []).append(row)
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
    c = sub.add_parser("check")
    c.add_argument("company")
    c.add_argument("title")
    sub.add_parser("backfill")
    a = ap.parse_args()
    idx = Index(load())

    if a.cmd == "check":
        r = idx.find(a.company, a.title)
        print(f"SEEN {r['first_seen']} {r['verdict']} {r['score']} {r['url']}" if r else "NEW")
        return 0
    if a.cmd == "backfill":
        n = backfill(idx)
        save(idx.rows)
        print(f"backfill: {n} rows added, {len(idx.rows)} in ledger")
        return 0
    if a.cmd == "record":
        cands = json.loads(CANDIDATES.read_text(encoding="utf-8"))
        n = 0
        for j in cands["jobs"]:
            if not idx.find(j["company"], j["title"], j["url"], j["id"]):
                idx.add(job_id=j["id"], source=j["source"], company=j["company"], title=j["title"], url=j["url"],
                        verdict="screened", note=f"posted {j.get('posted') or '?'}")
                n += 1
        save(idx.rows)
        print(f"recorded {n} new jobs, {len(idx.rows)} in ledger")
        return 0
    if a.cmd == "set":
        r = idx.by_key.get(a.which) or idx.by_url.get(a.which) or idx.by_id.get(a.which)
        if not r:
            print(f"FAILED: '{a.which}' is not in the ledger", file=sys.stderr)
            return 1
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
