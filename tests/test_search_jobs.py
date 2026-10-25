"""search_jobs.py --details: a failed detail fetch must not lose the search (S1-4)."""
import json
import os
import subprocess
import sys

from conftest import TOOLS

# Runs search_jobs.main() in the workspace with the sources stubbed out and the detail endpoint failing for one job.
SCRIPT = r"""
import sys
sys.path.insert(0, sys.argv[1])
sys.argv = ["search_jobs.py", "--details"]
import requests, search_jobs as s

def job(ref, title):
    return dict(id=f"ba-{ref}", source="Arbeitsagentur", title=title, company="Acme GmbH", location="Mannheim",
                posted="2099-01-01", region="Baden-Württemberg", plz="68159", url=f"https://example.org/{ref}", ref=ref)

s.arbeitsagentur = lambda since, days, status: [job("1", "Werkstudent Marketing"), job("2", "Werkstudent Content")]
s.arbeitnow = lambda since, status: []
s.watchlist = lambda since, status: []

class Resp:
    def __init__(self, code): self.status_code = code
    def raise_for_status(self):
        if self.status_code >= 400: raise requests.HTTPError(f"{self.status_code} Server Error")
    def json(self):  # an error page is HTML, not JSON
        if self.status_code >= 400: raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return {"stellenangebotsBeschreibung": "Full ad text", "externeURL": ""}

calls = []
def fake_get(url, **kw):
    calls.append(url)
    return Resp(500 if len(calls) == 1 else 200)
s.requests.get = fake_get
s.time.sleep = lambda _: None
sys.exit(s.main())
"""


def test_details_failure_keeps_candidates(sample):
    env = {**os.environ, "JOBHUNT_ROOT": str(sample), "PYTHONIOENCODING": "utf-8", "JOBHUNT_OFFLINE": "1"}
    r = subprocess.run([sys.executable, "-c", SCRIPT, str(TOOLS)], cwd=sample, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    data = json.loads((sample / "data" / "candidates.json").read_text(encoding="utf-8"))
    jobs = {j["ref"]: j for j in data["jobs"]}
    assert set(jobs) == {"1", "2"}
    assert "500" in jobs["1"]["detail_error"] and "text" not in jobs["1"]
    assert jobs["2"]["text"] == "Full ad text" and "detail_error" not in jobs["2"]
    assert data["status"]["Arbeitsagentur"]["details"] == "1 ok, 1 failed"
    assert "details 1 ok, 1 failed" in r.stdout and "no ad text (detail_error)" in r.stdout
