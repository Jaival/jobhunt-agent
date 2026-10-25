"""search_jobs.py --details: a failed detail fetch must not lose the search (S1-4)."""
import json
import os
import subprocess
import sys

from conftest import TOOLS

# Runs search_jobs.main() in the workspace with the sources stubbed out. argv: tools dir, JSON {ref: behaviour},
# where behaviour is "ok", "500" (an HTML error page), "empty" (200 without ad text) or "down" (connection error).
SCRIPT = r"""
import base64, json, sys
sys.path.insert(0, sys.argv[1])
plan = json.loads(sys.argv[2])
sys.argv = ["search_jobs.py", "--details"]
import requests, search_jobs as s

def job(ref):
    return dict(id=f"ba-{ref}", source="Arbeitsagentur", title=f"Werkstudent Marketing {ref}", company="Acme GmbH",
                location="Mannheim", posted="2099-01-01", region="Baden-Württemberg", plz="68159",
                url=f"https://example.org/{ref}", ref=ref)

s.arbeitsagentur = lambda since, days, status: [job(ref) for ref in plan]
s.arbeitnow = lambda since, status: []
s.watchlist = lambda since, status: []

class Resp:
    def __init__(self, how): self.how = how
    def raise_for_status(self):
        if self.how == "500": raise requests.HTTPError("500 Server Error")
    def json(self):
        if self.how == "500": raise ValueError("Expecting value: line 1 column 1 (char 0)")  # HTML, not JSON
        if self.how == "empty": return {"externeURL": "https://acme.example/job"}
        return {"stellenangebotsBeschreibung": "Full ad text", "externeURL": ""}

def fake_get(url, **kw):
    ref = base64.b64decode(url.rsplit("/", 1)[1]).decode()
    print("GET", ref, kw["headers"]["User-Agent"])
    if plan[ref] == "down": raise requests.ConnectionError()
    return Resp(plan[ref])
s.requests.get = fake_get
s.time.sleep = lambda _: None
sys.exit(s.main())
"""


def run(sample, plan):
    env = {**os.environ, "JOBHUNT_ROOT": str(sample), "PYTHONIOENCODING": "utf-8", "JOBHUNT_OFFLINE": "1"}
    r = subprocess.run([sys.executable, "-c", SCRIPT, str(TOOLS), json.dumps(plan)], cwd=sample, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    data = json.loads((sample / "data" / "candidates.json").read_text(encoding="utf-8"))
    return r.stdout, data["status"]["Arbeitsagentur"], {j["ref"]: j for j in data["jobs"]}


def test_details_failure_keeps_candidates(sample):
    out, status, jobs = run(sample, {"1": "500", "2": "ok", "3": "empty"})
    assert set(jobs) == {"1", "2", "3"}
    assert jobs["1"]["detail_error"].startswith("HTTPError: 500") and "text" not in jobs["1"]
    assert jobs["2"]["text"] == "Full ad text" and "detail_error" not in jobs["2"]
    assert "no ad text" in jobs["3"]["detail_error"] and jobs["3"]["external_url"] == "https://acme.example/job"
    assert status["details"] == "1 ok, 2 failed"
    assert "details 1 ok, 2 failed" in out and out.count("no ad text (detail_error)") == 2
    assert not list((sample / "data").glob("*.tmp"))


def test_names_itself_in_the_user_agent(sample):
    out, _, _ = run(sample, {"1": "ok"})
    version = (TOOLS.parent / "VERSION").read_text(encoding="utf-8").strip()
    assert f"jobhunt-agent/{version} (+https://github.com/Jaival/jobhunt-agent)" in out  # S1-10
    assert "Mozilla" not in out


def test_gives_up_when_the_endpoint_is_down(sample):
    out, status, jobs = run(sample, {str(i): "down" for i in range(1, 6)})
    assert out.count("GET ") == 3  # not 5 x a 30 s timeout
    assert jobs["1"]["detail_error"].startswith("ConnectionError")  # named even though the message is empty
    assert all(jobs[r]["detail_error"].startswith("skipped") for r in ("4", "5"))
    assert status["details"] == "0 ok, 5 failed"


# Paging (S1-7): a fake Arbeitsagentur search. argv: tools dir, JSON {term: total results, or "fail2" for 150 results
# whose second page errors}.
PAGING = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
plan = json.loads(sys.argv[2])
sys.argv = ["search_jobs.py"]
import requests, search_jobs as s

s.search_terms = lambda: list(plan)
s.search_areas = lambda search: [{"wo": "Mannheim", "umkreis": 50}]
s.arbeitnow = lambda since, status: []
s.watchlist = lambda since, status: []
s.time.sleep = lambda _: None

class Resp:
    def __init__(self, data): self.data = data
    def raise_for_status(self): pass
    def json(self): return self.data

def fake_get(url, params, **kw):
    term, page, size = params["was"], params["page"], params["size"]
    print("GET", term, page)
    total = 150 if plan[term] == "fail2" else plan[term]
    if plan[term] == "fail2" and page == 2:
        raise requests.ConnectionError("reset")
    n = range((page - 1) * size, min(page * size, total))
    return Resp({"maxErgebnisse": total, "page": page, "size": size, "ergebnisliste": [
        dict(referenznummer=f"{term}-{i}", stellenangebotsTitel=f"Werkstudent Marketing {term} {i}", firma=f"Firma {i}",
             datumErsteVeroeffentlichung="2099-01-01",
             stellenlokationen=[{"adresse": {"ort": "Mannheim", "plz": "68159", "region": "BADEN_WUERTTEMBERG"}}])
        for i in n]})
s.requests.get = fake_get
sys.exit(s.main())
"""


def run_paging(sample, plan):
    env = {**os.environ, "JOBHUNT_ROOT": str(sample), "PYTHONIOENCODING": "utf-8", "JOBHUNT_OFFLINE": "1"}
    r = subprocess.run([sys.executable, "-c", PAGING, str(TOOLS), json.dumps(plan)], cwd=sample, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    status = json.loads((sample / "data" / "candidates.json").read_text(encoding="utf-8"))["status"]["Arbeitsagentur"]
    return r.stdout, status


def test_paging_follows_pages_until_done(sample):
    out, status = run_paging(sample, {"a": 50, "b": 100, "c": 250})
    assert [l for l in out.splitlines() if l.startswith("GET")] == [
        "GET a 1", "GET b 1", "GET c 1", "GET c 2", "GET c 3"]  # b: exactly one full page, no empty second call
    assert status["fetched"] == 400 and "page_limit" not in status and "WARNING" not in out


def test_paging_warns_at_the_limit(sample):
    out, status = run_paging(sample, {"broad": 450})
    assert out.count("GET broad") == 3 and status["fetched"] == 300
    assert status["page_limit"] == ["broad (Mannheim): 300 of 450"]
    line = next(l for l in out.splitlines() if l.startswith("Arbeitsagentur:"))
    assert line.endswith("page limit hit in 1 searches")  # in the status line
    assert "WARNING page limit: broad (Mannheim): 300 of 450" in out


def test_paging_error_keeps_earlier_pages(sample):
    out, status = run_paging(sample, {"flaky": "fail2", "ok": 10})
    assert status["fetched"] == 110  # page 1 of flaky kept, then the next term
    assert status["errors"] == ["flaky page 2: reset"] and "page_limit" not in status
