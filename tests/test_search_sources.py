"""search_jobs.py sources with requests stubbed: Arbeitnow paging and errors, the four watchlist parsers."""
import json
import os
import subprocess
import sys

from conftest import TOOLS

# argv: tools dir, function name, JSON {"since": "YYYY-MM-DD", "replies": {url fragment: reply}}; a reply is
# {"json": ...}, {"xml": "<...>"}, {"status": 500} or {"down": true}; for Arbeitnow the key is "page=<n>".
SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
fn, spec = sys.argv[2], json.loads(sys.argv[3])
sys.argv = ["search_jobs.py"]
import requests, search_jobs as s

class Resp:
    def __init__(self, r): self.r = r; self.content = (r.get("xml") or "").encode()
    def raise_for_status(self):
        if self.r.get("status", 200) >= 400: raise requests.HTTPError(f"{self.r['status']} Server Error")
    def json(self):
        if "json" not in self.r: raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self.r["json"]

def fake_get(url, params=None, **kw):
    key = f"page={params['page']}" if params and "page" in params else url
    r = next((v for k, v in spec["replies"].items() if k in key), {"status": 404})
    if r.get("down"): raise requests.ConnectionError("down")
    return Resp(r)
s.requests.get = fake_get
s.time.sleep = lambda _: None
status = {}
jobs = getattr(s, fn)(spec["since"], status)
print(json.dumps({"jobs": jobs, "status": status}))
"""

NEW = 4102444800  # 2100-01-01
OLD = 946684800  # 2000-01-01


def call(sample, fn, since, replies):
    env = {**os.environ, "JOBHUNT_ROOT": str(sample), "PYTHONIOENCODING": "utf-8", "JOBHUNT_OFFLINE": "1"}
    r = subprocess.run([sys.executable, "-c", SCRIPT, str(TOOLS), fn, json.dumps({"since": since, "replies": replies})],
                       cwd=sample, env=env, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    return out["jobs"], out["status"]


def an(slug, created):
    return {"slug": slug, "title": f"Werkstudent {slug}", "company_name": "Acme", "location": "Mannheim",
            "remote": False, "created_at": created, "url": f"https://www.arbeitnow.com/jobs/{slug}",
            "description": "<p>Text</p>"}


def test_arbeitnow_stops_at_the_first_page_with_old_jobs(sample):
    jobs, status = call(sample, "arbeitnow", "2099-01-01",
                        {"page=1": {"json": {"data": [an("a", NEW), an("b", NEW)]}},
                         "page=2": {"json": {"data": [an("c", NEW), an("d", OLD)]}},
                         "page=3": {"json": {"data": [an("e", NEW)]}}})
    assert [j["id"] for j in jobs] == ["an-a", "an-b", "an-c"] and status["fetched"] == 4


def test_a_failed_arbeitnow_page_keeps_the_pages_already_read(sample):
    for bad in ({"status": 500}, {"down": True}, {"json": {"data": [{"slug": "x"}]}}, {"xml": "<html>"}):
        jobs, status = call(sample, "arbeitnow", "2099-01-01",
                            {"page=1": {"json": {"data": [an("a", NEW)]}}, "page=2": bad})
        assert [j["id"] for j in jobs] == ["an-a"], bad
        assert len(status["errors"]) == 1 and status["errors"][0].startswith("page 2:"), bad


def test_arbeitnow_says_when_the_page_cap_cut_the_window(sample):
    replies = {f"page={n}": {"json": {"data": [an(f"j{n}", NEW)]}} for n in range(1, 8)}
    jobs, status = call(sample, "arbeitnow", "2099-01-01", replies)
    assert len(jobs) == 7 and "7 pages" in status["warning"]
    jobs, status = call(sample, "arbeitnow", "2099-01-01", {"page=1": {"json": {"data": [an("a", NEW), an("b", OLD)]}}})
    assert "warning" not in status


def watch(sample, *rows):
    """Write companies.md with one table row per (company, endpoint), in the template's column layout."""
    table = ["| Company | Careers page | ATS | Endpoint | Last checked |",
             "|---------|--------------|-----|----------|--------------|"]
    table += [f"| {company} | | | {url} | |" for company, url in rows]
    (sample / "companies.md").write_text("# Company watchlist\n\n" + "\n".join(table) + "\n", encoding="utf-8")


def test_watchlist_reads_personio_xml(sample):
    watch(sample, ("Acme", "https://acme.jobs.personio.de/xml"))
    pos = "<position><id>{}</id><name>Werkstudent {}</name><office>Mannheim</office>{}</position>"
    xml = ("<workzag-jobs>" + pos.format(7, "A", "<createdAt>2026-05-01T10:00:00+00:00</createdAt>")
           + pos.format(8, "B", "<createdAt>2025-05-01T10:00:00+00:00</createdAt>") + pos.format(9, "C", "")
           + "</workzag-jobs>")
    jobs, status = call(sample, "watchlist", "2026-01-01", {"acme.jobs.personio.de": {"xml": xml}})
    assert [j["id"] for j in jobs] == ["personio-7", "personio-9"] and status["Acme"] == "ok"
    assert jobs[0]["url"] == "https://acme.jobs.personio.de/job/7" and jobs[0]["posted"] == "2026-05-01"
    assert jobs[0]["title"] == "Werkstudent A" and jobs[0]["location"] == "Mannheim"


def test_watchlist_reads_ashby(sample):
    watch(sample, ("Acme", "https://api.ashbyhq.com/posting-api/job-board/acme"))
    job = lambda i, date: {"id": i, "title": f"Werkstudent {i}", "location": "Berlin", "publishedAt": date,
                           "jobUrl": f"https://jobs.ashbyhq.com/acme/{i}"}
    reply = {"json": {"jobs": [job("a1", "2026-05-01T00:00:00Z"), job("a2", "2025-05-01T00:00:00Z"), job("a3", None)]}}
    jobs, status = call(sample, "watchlist", "2026-01-01", {"api.ashbyhq.com": reply})
    assert [j["id"] for j in jobs] == ["ashby-a1", "ashby-a3"] and status["Acme"] == "ok"
    assert jobs[0]["url"] == "https://jobs.ashbyhq.com/acme/a1" and jobs[0]["posted"] == "2026-05-01"
    assert jobs[0]["location"] == "Berlin"


def test_watchlist_reads_greenhouse(sample):
    watch(sample, ("Acme", "https://boards-api.greenhouse.io/v1/boards/acme/jobs"))
    job = lambda i, date: {"id": i, "title": f"Werkstudent {i}", "location": {"name": "Berlin"}, "updated_at": date,
                           "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{i}"}
    reply = {"json": {"jobs": [job(5, "2026-05-01T00:00:00Z"), job(6, "2025-05-01T00:00:00Z"), job(7, None)]}}
    jobs, status = call(sample, "watchlist", "2026-01-01", {"greenhouse.io": reply})
    assert [j["id"] for j in jobs] == ["gh-5", "gh-7"] and status["Acme"] == "ok"
    assert jobs[0]["url"] == "https://boards.greenhouse.io/acme/jobs/5" and jobs[0]["posted"] == "2026-05-01"
    assert jobs[0]["location"] == "Berlin"


def test_watchlist_reads_lever(sample):
    watch(sample, ("Acme", "https://api.lever.co/v0/postings/acme?mode=json"))
    job = lambda i, ms: {"id": i, "text": f"Werkstudent {i}", "categories": {"location": "Berlin"}, "createdAt": ms,
                         "hostedUrl": f"https://jobs.lever.co/acme/{i}"}
    reply = {"json": [job("l1", 1777593600000), job("l2", 1746057600000)]}  # 2026-05-01, 2025-05-01 UTC
    jobs, status = call(sample, "watchlist", "2026-01-01", {"api.lever.co": reply})
    assert [j["id"] for j in jobs] == ["lever-l1"] and status["Acme"] == "ok"
    assert jobs[0]["url"] == "https://jobs.lever.co/acme/l1" and jobs[0]["posted"].startswith("2026-0")
    assert jobs[0]["title"] == "Werkstudent l1" and jobs[0]["location"] == "Berlin"


def test_one_failed_watchlist_company_keeps_the_others(sample):
    watch(sample, ("Broken", "https://api.ashbyhq.com/posting-api/job-board/broken"),
          ("Acme", "https://boards-api.greenhouse.io/v1/boards/acme/jobs"))
    reply = {"json": {"jobs": [{"id": 5, "title": "Werkstudent", "location": {"name": "Berlin"},
                                "updated_at": "2026-05-01T00:00:00Z", "absolute_url": "https://boards.greenhouse.io/acme/jobs/5"}]}}
    jobs, status = call(sample, "watchlist", "2026-01-01", {"job-board/broken": {"status": 500}, "greenhouse.io": reply})
    assert [j["id"] for j in jobs] == ["gh-5"]
    assert status["Broken"].startswith("error") and status["Acme"] == "ok"
