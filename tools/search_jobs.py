"""Search the API sources, filter titles, mark what is new against the seen-jobs ledger.

Sources: Arbeitsagentur API (search terms from sources.md; the home area from config.yaml, then search.areas or
one nationwide pass),
Arbeitnow API (German site only), and the Personio / Ashby / Greenhouse / Lever endpoints listed in
companies.md. Indeed (connector) and Gmail alerts stay manual tool calls in the routine.

Titles are filtered by the profile: block in config.yaml (role types, include / exclude words; scope.py), and
locations by search.regions when it is set (for example [Bayern]; scope.Region).
Writes data/candidates.json (all in-scope jobs, each marked new / seen) and prints the new ones.
It does not change the ledger: after scoring, run `python engine/tools/ledger.py record`.

Usage (from the JobHunt folder):
    python engine/tools/search_jobs.py [--days 3] [--details]
      --details  also fetch the full ad text of new Arbeitsagentur jobs into candidates.json (candidates.json is
                 written first, so a failed fetch loses no jobs; jobs whose text couldn't be fetched get detail_error)
"""
import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atomic  # noqa: E402
import ledger  # noqa: E402
import version  # noqa: E402
from config import CFG  # noqa: E402
from scope import Region, Scope, role_type, search_areas  # noqa: E402

ROOT = ledger.ROOT
OUT = ROOT / "data" / "candidates.json"
BA_SEARCH = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
BA_DETAIL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/"
# Say who we are instead of posing as a browser, so a source can see the traffic and contact the project.
UA = {"User-Agent": f"jobhunt-agent/{version.version()} (+https://github.com/Jaival/jobhunt-agent)"}
BA_HEADERS = {"X-API-Key": "jobboerse-jobsuche", **UA}
ARBEITNOW = "https://www.arbeitnow.com/api/job-board-api"
GIVE_UP = 3  # detail fetches failing in a row before the rest are skipped

# Title filter (routine step 3): built from the profile: block in config.yaml, see scope.py.
try:
    SCOPE = Scope(CFG.get("profile"))
except ValueError as e:
    sys.exit(str(e))
in_scope = SCOPE.in_scope
REGION = Region(CFG.get("search"))


def search_terms():
    text = (ROOT / "sources.md").read_text(encoding="utf-8")
    block = text.split("## Search terms", 1)[1].split("\n## ", 1)[0].split("Locations:", 1)[0]
    return list(dict.fromkeys(l[2:].strip() for l in block.splitlines() if l.startswith("- ")))


# ---------- sources ----------

def arbeitsagentur(since, days, status):
    jobs = {}
    for term in search_terms():
        for where in search_areas(CFG.get("search")):
            try:
                r = requests.get(BA_SEARCH, headers=BA_HEADERS, timeout=30,
                                 params={"was": term, "size": 100, "veroeffentlichtseit": days, **where})
                r.raise_for_status()
                data = r.json()
            except Exception as e:  # keep going; report in the status line
                status.setdefault("errors", []).append(f"{term}: {e}")
                continue
            for x in data.get("ergebnisliste") or data.get("stellenangebote") or []:
                ref = x.get("referenznummer") or x.get("refnr")
                if ref:
                    jobs[ref] = x
            time.sleep(0.3)
    status["fetched"] = len(jobs)
    out = []
    for ref, x in jobs.items():
        posted = x.get("datumErsteVeroeffentlichung", "")
        if posted < since:
            continue
        loc = (x.get("stellenlokationen") or [{}])[0].get("adresse", {}) or x.get("arbeitsort") or {}
        out.append(dict(id=f"ba-{ref}", source="Arbeitsagentur", title=x.get("stellenangebotsTitel", ""),
                        company=x.get("firma", ""), location=loc.get("ort", ""), posted=posted,
                        region=loc.get("region", ""), plz=str(loc.get("plz") or ""),
                        url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}", ref=ref))
    return out


def ba_detail(ref):
    r = requests.get(BA_DETAIL + base64.b64encode(ref.encode()).decode(), headers=BA_HEADERS, timeout=30)
    r.raise_for_status()
    j = r.json()
    return j.get("stellenangebotsBeschreibung") or "", j.get("externeURL") or ""


def fetch_details(jobs, status):
    """Full ad text for the Arbeitsagentur jobs. A job whose text couldn't be read gets detail_error and stays in
    candidates.json; after GIVE_UP failures in a row (endpoint down) the rest are skipped, not each timed out."""
    ok = failed = in_a_row = 0
    todo = [j for j in jobs if j.get("ref")]
    for i, j in enumerate(todo):
        if in_a_row >= GIVE_UP:
            j["detail_error"] = f"skipped: the detail endpoint failed {GIVE_UP} times in a row"
            failed += 1
            continue
        if i:
            time.sleep(0.3)
        try:
            j["text"], j["external_url"] = ba_detail(j["ref"])
            if not j["text"].strip():
                raise ValueError("no ad text in the response" + (" (the ad is on external_url)" if j["external_url"] else ""))
            ok += 1
            in_a_row = 0
        except Exception as e:  # keep going; the job stays in candidates.json without its text
            j["detail_error"] = f"{type(e).__name__}: {e}"
            failed += 1
            in_a_row += 1
    if todo:
        status["details"] = f"{ok} ok" + (f", {failed} failed" if failed else "")


def write(jobs, status, since):
    atomic.write_text(OUT, json.dumps({"generated": dt.datetime.now().isoformat(timespec="minutes"), "since": since,
                                       "status": status, "jobs": jobs}, ensure_ascii=False, indent=1))


def arbeitnow(since, status):
    out, cutoff = [], dt.datetime.fromisoformat(since).timestamp()
    for page in range(1, 8):
        data = requests.get(ARBEITNOW, params={"page": page}, headers=UA, timeout=30).json().get("data", [])
        status["fetched"] = status.get("fetched", 0) + len(data)
        for x in data:
            if x["created_at"] < cutoff or not x["url"].startswith("https://www.arbeitnow.com/"):
                continue
            text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x.get("description", ""))))
            out.append(dict(id=f"an-{x['slug']}", source="Arbeitnow", title=x["title"], company=x["company_name"],
                            location=x.get("location", ""), remote=x.get("remote"),
                            posted=f"{dt.date.fromtimestamp(x['created_at']):%Y-%m-%d}", url=x["url"], text=text))
        if not data or min(x["created_at"] for x in data) < cutoff:
            break
        time.sleep(1)
    return out


def watchlist(since, status):
    """Personio / Ashby / Greenhouse / Lever endpoints from the companies.md table."""
    out = []
    for line in (ROOT / "companies.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 6 or not cells[4].startswith("https://"):
            continue
        company, url = cells[1], cells[4].split()[0]
        try:
            if "personio" in url and url.endswith("/xml"):
                root = ET.fromstring(requests.get(url, headers=UA, timeout=30).content)
                for p in root.iter("position"):
                    created = (p.findtext("createdAt") or "")[:10]
                    jid = p.findtext("id")
                    out.append(dict(id=f"personio-{jid}", source=f"Watchlist ({company})", title=p.findtext("name") or "",
                                    company=company, location=p.findtext("office") or "", posted=created,
                                    url=url.replace("/xml", f"/job/{jid}")))
            elif "api.ashbyhq.com" in url:
                for j in requests.get(url, headers=UA, timeout=30).json().get("jobs", []):
                    out.append(dict(id=f"ashby-{j['id']}", source=f"Watchlist ({company})", title=j["title"],
                                    company=company, location=j.get("location", ""),
                                    posted=(j.get("publishedAt") or "")[:10], url=j.get("jobUrl", "")))
            elif "greenhouse.io" in url:
                for j in requests.get(url, headers=UA, timeout=30).json().get("jobs", []):
                    out.append(dict(id=f"gh-{j['id']}", source=f"Watchlist ({company})", title=j["title"],
                                    company=company, location=(j.get("location") or {}).get("name", ""),
                                    posted=(j.get("updated_at") or "")[:10], url=j.get("absolute_url", "")))
            elif "api.lever.co" in url:
                for j in requests.get(url, headers=UA, timeout=30).json():
                    out.append(dict(id=f"lever-{j['id']}", source=f"Watchlist ({company})", title=j["text"],
                                    company=company, location=(j.get("categories") or {}).get("location", ""),
                                    posted=f"{dt.date.fromtimestamp(j['createdAt'] / 1000):%Y-%m-%d}",
                                    url=j.get("hostedUrl", "")))
            else:
                continue
            status[company] = "ok"
        except Exception as e:
            status[company] = f"error: {e}"
    return [j for j in out if not j["posted"] or j["posted"] >= since]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=3, help="posted within the last N days (default 3)")
    ap.add_argument("--details", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    since = f"{dt.date.today() - dt.timedelta(days=a.days):%Y-%m-%d}"
    status = {"Arbeitsagentur": {}, "Arbeitnow": {}, "Watchlist": {}}

    found = []
    for name, fn in (("Arbeitsagentur", lambda s: arbeitsagentur(since, a.days, s)),
                     ("Arbeitnow", lambda s: arbeitnow(since, s)),
                     ("Watchlist", lambda s: watchlist(since, s))):
        try:
            jobs = fn(status[name])
            status[name]["in_window"] = len(jobs)
            found += jobs
        except Exception as e:
            status[name]["error"] = str(e)

    idx = ledger.Index(ledger.load())
    seen_keys, jobs = set(), []
    for j in found:
        if not in_scope(j["title"]) or not REGION.keep(j):
            continue
        key = ledger.make_key(j["company"], j["title"])
        if key in seen_keys:  # same job on several sources this run
            continue
        seen_keys.add(key)
        hit = idx.find(j["company"], j["title"], j["url"], j["id"])
        j.update(role_type=role_type(j["title"]), key=key,
                 seen=bool(hit), seen_as=f"{hit['first_seen']} {hit['verdict']} {hit['score']}".strip() if hit else "")
        jobs.append(j)

    new = [j for j in jobs if not j["seen"]]
    write(jobs, status, since)  # before the details, so a crash there can't lose the search
    if a.details:
        fetch_details(new, status["Arbeitsagentur"])
        write(jobs, status, since)

    for name, s in status.items():
        print(f"{name}: " + ", ".join(f"{k} {v}" for k, v in s.items() if k != "errors")
              + (f", {len(s['errors'])} errors" if s.get("errors") else ""))
    print(f"\nIn scope: {len(jobs)} ({len(new)} new, {len(jobs) - len(new)} already seen). Written to {OUT.relative_to(ROOT)}\n")
    for j in sorted(new, key=lambda j: (j["role_type"], j["posted"])):
        print(f"NEW  {j['posted']}  [{j['role_type']}] {j['title']} | {j['company']} | {j['location']} | {j['url']}"
              + (" | no ad text (detail_error)" if "detail_error" in j else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
