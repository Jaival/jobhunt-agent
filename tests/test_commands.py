"""Commands (S4-5): `extract.py add` puts one named job on the reader's list, `ledger.py show` finds a job's row.
The skills tailor, why, sent and job-status (tests/test_skills.py) call these and the daily run's other tools."""
import json

from test_extract import GOOD

URL = "https://jobs.example/acme/werkstudent-marketing"


def jobs(sample):
    return json.loads((sample / "data" / "candidates.json").read_text(encoding="utf-8"))["jobs"]


def test_add_puts_the_job_on_the_readers_list(tool, sample):
    r = tool("extract.py", "add", URL)
    assert r.returncode == 0, r.stderr
    job_id = jobs(sample)[0]["id"]
    assert r.stdout.splitlines() == ["NEW     not in the ledger", f"read {job_id} | url {URL} | unknown | unknown | {URL}"]
    assert tool("extract.py", "add", URL).returncode == 0 and len(jobs(sample)) == 1    # once only
    assert f"read {job_id} | url {URL}" in tool("extract.py", "pending").stdout


def test_saved_extract_names_the_added_job_and_the_ledger_records_it(tool, sample):
    tool("extract.py", "add", URL)
    job_id = jobs(sample)[0]["id"]
    reply = {"extracts": [{**GOOD, "id": job_id, "url": URL}], "leads": [], "unreadable": []}
    (sample / "data" / "ads").mkdir(parents=True, exist_ok=True)
    (sample / "data" / "ads" / "incoming.json").write_text(json.dumps(reply), encoding="utf-8")
    assert tool("extract.py", "save", "data/ads/incoming.json").returncode == 0
    job = jobs(sample)[0]
    assert job["company"] == GOOD["company"] and job["title"] == GOOD["title"] and job["role_type"] == "Werkstudent"
    assert tool("extract.py", "add", URL).stdout.splitlines()[1] == f"EXTRACT data/ads/{job_id}.json"

    assert tool("ledger.py", "record", "--model", "m").returncode == 0
    assert tool("ledger.py", "set", URL, "--verdict", "tailored", "--score", "78", "--subscores", "skills=4",
                "seniority=5", "language=3", "location=5", "hours=4").returncode == 0
    assert tool("extract.py", "add", URL).stdout.startswith("SEEN    ")

    for which in (URL, "golf club marketing"):
        r = tool("ledger.py", "show", *which.split())
        assert r.returncode == 0, r.stderr
        assert f"Golf Club St.Leon-Rot | {GOOD['title']} | {URL}" in r.stdout
        assert "verdict tailored, score 78" in r.stdout
        assert "sub-scores skills=4 seniority=5 language=3 location=5 hours=4" in r.stdout


def test_add_refuses_a_short_link_and_show_reports_unknown_jobs(tool):
    r = tool("extract.py", "add", "https://to.indeed.com/aabbcc")
    assert r.returncode == 1 and "Indeed short link" in r.stderr
    r = tool("ledger.py", "show", "Nowhere", "GmbH")
    assert r.returncode == 1 and "NOT FOUND" in r.stderr
