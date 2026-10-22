"""Search the API sources, filter titles, mark what is new against the seen-jobs ledger.

Sources: Arbeitsagentur API (search terms from sources.md, home area from config.yaml + nationwide),
Arbeitnow API (German site only), and the Personio / Ashby / Greenhouse / Lever endpoints listed in
companies.md. Indeed (connector) and Gmail alerts stay manual tool calls in the routine.

Writes data/candidates.json (all in-scope jobs, each marked new / seen) and prints the new ones.
It does not change the ledger: after scoring, run `python engine/tools/ledger.py record`.

Usage (from the JobHunt folder):
    python engine/tools/search_jobs.py [--days 3] [--details]
      --details  also fetch the full ad text of new Arbeitsagentur jobs into candidates.json
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
import ledger  # noqa: E402
from config import CFG  # noqa: E402

ROOT = ledger.ROOT
OUT = ROOT / "data" / "candidates.json"
BA_SEARCH = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
BA_DETAIL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/"
BA_HEADERS = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": "Mozilla/5.0"}
ARBEITNOW = "https://www.arbeitnow.com/api/job-board-api"

# Title filter (CLAUDE.md "What I'm looking for"; routine step 3).
DROP = re.compile(r"senior|\blead\b|principal|staff|architect|architekt|manager|leiter|head of|director|"
                  r"vertrieb|sales|marketing|recruit|buchhalt|accounting|finanz|einkauf|procurement|"
                  r"ausbildung|azubi|dozent|logopäd|lager|empfang|bar &|service \(|social media|design|"
                  r"elektro|mechan|maschinenbau|gebäude|tga|flight|unsolicited|initiativ|"
                  r"fachinformatiker|wirtschaftsinformatiker", re.I)
INFRA = re.compile(r"devops|cloud|platform|plattform|infrastru|\bsre\b|reliabil|linux|system ?admin|"
                   r"systemadmin|system engineer|systems engineer|kubernetes|network|netzwerk|it-admin|"
                   r"\bit\b|informatik|security|sicherheit", re.I)
SOFTWARE = re.compile(r"software|backend|frontend|full.?stack|entwickl|developer|web|app|mobile|python|"
                      r"test|qa\b|quality|automation|automatisierung|engineer", re.I)
JUNIOR = re.compile(r"junior|einsteiger|berufseinstieg|graduate|absolvent|entry", re.I)
ROLE_TYPES = [
    ("Thesis", re.compile(r"masterarbeit|abschlussarbeit|thesis|bachelorarbeit", re.I)),
    ("HiWi", re.compile(r"hiwi|studentische hilfskraft|wissenschaftliche hilfskraft|studentische aushilfe", re.I)),
    ("Internship", re.compile(r"praktik|intern\b|internship", re.I)),
    ("Werkstudent", re.compile(r"werkstudent|working student|studentische|student\b", re.I)),
]


def role_type(title):
    for name, rx in ROLE_TYPES:
        if rx.search(title):
            return name
    return "Junior" if JUNIOR.search(title) else "Other"


def in_scope(title):
    if DROP.search(title):
        return False
    rt = role_type(title)
    if rt in ("Werkstudent", "HiWi", "Internship", "Thesis"):
        return bool(INFRA.search(title) or SOFTWARE.search(title))
    return bool(INFRA.search(title)) and not re.search(r"informatik", title, re.I)  # junior/unlabelled: infra only


def search_terms():
    text = (ROOT / "sources.md").read_text(encoding="utf-8")
    block = text.split("## Search terms", 1)[1].split("\n## ", 1)[0].split("Locations:", 1)[0]
    return list(dict.fromkeys(l[2:].strip() for l in block.splitlines() if l.startswith("- ")))


# ---------- sources ----------

def arbeitsagentur(since, days, status):
    jobs = {}
    for term in search_terms():
        for where in (CFG.get("search", {}).get("home") or {}, {}):
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
        loc = (x.get("stellenlokationen") or [{}])[0].get("adresse", {})
        out.append(dict(id=f"ba-{ref}", source="Arbeitsagentur", title=x.get("stellenangebotsTitel", ""),
                        company=x.get("firma", ""), location=loc.get("ort", ""), posted=posted,
                        url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}", ref=ref))
    return out


def ba_detail(ref):
    r = requests.get(BA_DETAIL + base64.b64encode(ref.encode()).decode(), headers=BA_HEADERS, timeout=30)
    j = r.json()
    return j.get("stellenangebotsBeschreibung") or "", j.get("externeURL") or ""


def arbeitnow(since, status):
    out, cutoff = [], dt.datetime.fromisoformat(since).timestamp()
    for page in range(1, 8):
        data = requests.get(ARBEITNOW, params={"page": page}, timeout=30).json().get("data", [])
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
                root = ET.fromstring(requests.get(url, timeout=30).content)
                for p in root.iter("position"):
                    created = (p.findtext("createdAt") or "")[:10]
                    jid = p.findtext("id")
                    out.append(dict(id=f"personio-{jid}", source=f"Watchlist ({company})", title=p.findtext("name") or "",
                                    company=company, location=p.findtext("office") or "", posted=created,
                                    url=url.replace("/xml", f"/job/{jid}")))
            elif "api.ashbyhq.com" in url:
                for j in requests.get(url, timeout=30).json().get("jobs", []):
                    out.append(dict(id=f"ashby-{j['id']}", source=f"Watchlist ({company})", title=j["title"],
                                    company=company, location=j.get("location", ""),
                                    posted=(j.get("publishedAt") or "")[:10], url=j.get("jobUrl", "")))
            elif "greenhouse.io" in url:
                for j in requests.get(url, timeout=30).json().get("jobs", []):
                    out.append(dict(id=f"gh-{j['id']}", source=f"Watchlist ({company})", title=j["title"],
                                    company=company, location=(j.get("location") or {}).get("name", ""),
                                    posted=(j.get("updated_at") or "")[:10], url=j.get("absolute_url", "")))
            elif "api.lever.co" in url:
                for j in requests.get(url, timeout=30).json():
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
        if not in_scope(j["title"]):
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
    if a.details:
        for j in new:
            if j.get("ref"):
                j["text"], j["external_url"] = ba_detail(j["ref"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated": dt.datetime.now().isoformat(timespec="minutes"), "since": since,
                               "status": status, "jobs": jobs}, ensure_ascii=False, indent=1), encoding="utf-8")

    for name, s in status.items():
        print(f"{name}: " + ", ".join(f"{k} {v}" for k, v in s.items() if k != "errors")
              + (f", {len(s['errors'])} errors" if s.get("errors") else ""))
    print(f"\nIn scope: {len(jobs)} ({len(new)} new, {len(jobs) - len(new)} already seen). Written to {OUT.relative_to(ROOT)}\n")
    for j in sorted(new, key=lambda j: (j["role_type"], j["posted"])):
        print(f"NEW  {j['posted']}  [{j['role_type']}] {j['title']} | {j['company']} | {j['location']} | {j['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
