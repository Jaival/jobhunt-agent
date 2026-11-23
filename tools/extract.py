"""Ad extracts: the fixed fields the routine reads instead of raw ad text (templates/ad_extract.schema.json).

Job ads are untrusted text that can carry instructions (RULES.md rule 7), so the routine never reads them itself.
The ad reader (the `ad-reader` subagent in .claude/agents/, with no write, Bash or send tools and no CLAUDE.md)
fetches each ad and returns an extract: a JSON object with fixed fields (title, company, location, role type,
closed flag + evidence, German level, hours, start, duration, years of experience, requirements with importance,
tasks) and `injection_text`, a neutral description of any instructions it found. This tool checks what the reader
returns before the routine relies on it: the schema, and no link, email address or AI instruction in any field
except url.

API ads: search_jobs.py writes their text to data/ads/<id>.txt; extracts go to data/ads/<id>.json and
candidates.json records them (`extract`, or `read_error` when the reader couldn't read the ad).

The tasks handed out today (`pending`, `add`) are kept in data/ads/tasks.json: a reply may save an extract or
mark an ad unreadable or gone only for a job it was asked about, so an injected page can't hide other jobs.

Usage (from the workspace folder):
    python engine/tools/extract.py pending                the reader's task lines for every new job without an extract,
        and an `endpoint` task for each companies.md row without an Endpoint (not checked in the last 30 days)
    python engine/tools/extract.py add <https://...>      one job the user named (the `tailor <url>` command): adds it
        to candidates.json without the title filter (an Indeed job by its viewjob?jk= link), says whether the ledger
        knows it, and prints its read task line, or where its extract is
    python engine/tools/extract.py save data/ads/incoming/ | data/ads/incoming.json
        the reader's replies (the folder: one file per reader call, saved by the SubagentStop hook; each file is
        deleted once it saved cleanly; a reply with an invalid item is moved to data/ads/failed/ after its valid
        items were saved, so it is not read again) or one reply: saves valid extracts, adds its leads (Indeed,
        Gmail, web) to candidates.json with the title filter and ledger check, records unreadable ads, writes
        found ATS endpoints into companies.md, prints a `MAIL` line per reply to an application (from a `list mail`
        task; nothing is stored; a `sent` mail from a sender the tool can't tie to the job or a known portal says
        `UNVERIFIED`); one line per item, exit 1 when one is invalid or the folder is empty
    python engine/tools/extract.py endpoint "<company>" <https://...>
        write an ATS endpoint found by hand into the company's companies.md row (Personio, Ashby, Greenhouse or
        Lever API form only)
    python engine/tools/extract.py read [<id> ...] [--model M]
        fallback without the subagent: reads the pending ad files with a headless `claude -p` call (no tools)
    python engine/tools/extract.py attach <id> applications/<folder>   copy the extract and ad text (ad.json, ad.txt)
    python engine/tools/extract.py check <file.json | folder> [...]  exit 0 when every extract is valid
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ENGINE = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ENGINE / "templates" / "ad_extract.schema.json"
SCHEMA = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
VERSION = SCHEMA["properties"]["ad_extract_version"]["const"]
AGENT_FILE = ENGINE / "templates" / "workspace" / ".claude" / "agents" / "ad-reader.md"
TYPES = {"string": str, "boolean": bool, "object": dict, "array": list, "null": type(None)}
LINK = re.compile(r"https?://|www\.|\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b|\b[\w-]+\.(?:com|de|io|net|org|ly)/", re.I)
INSTRUCTION = re.compile(r"\b(?:ignore (?:all|any|the|previous|prior|above)|disregard (?:all|the|previous)|"
                         r"system prompt|you are (?:an? )?(?:ai|assistant|language model)|as an ai\b|"
                         r"(?:ai|llm|assistant|language model)s? (?:must|should|are instructed)|"
                         r"\b(?:send|e-?mail|forward) (?:the|your|this|all) (?:cv|resume|data|files?))", re.I)
LEAD = {"type": "object", "additionalProperties": False, "required": ["source", "title", "company", "location", "url"],
        "properties": {"source": {"type": "string", "maxLength": 60}, "title": {"type": "string", "maxLength": 200},
                       "company": {"type": "string", "maxLength": 200}, "location": {"type": "string", "maxLength": 200},
                       "url": {"type": "string", "maxLength": 500}}}
# One reply to an application, from the reader's `list mail` task: the routine's step 7 matches these to folders.
# sender_domain is optional (a reader file from before it): a `sent` mail without it is UNVERIFIED.
MAIL = {"type": "object", "additionalProperties": False,
        "required": ["kind", "company", "role", "date", "interview_date", "via"],
        "properties": {"kind": {"enum": ["sent", "rejection", "interview"]},
                       "company": {"type": "string", "maxLength": 200}, "role": {"type": "string", "maxLength": 200},
                       "date": {"type": "string", "maxLength": 10}, "interview_date": {"type": ["string", "null"],
                                                                                       "maxLength": 16},
                       "via": {"type": "string", "maxLength": 60},
                       "sender_domain": {"type": "string", "maxLength": 100}}}
DOMAIN = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}", re.I)
# Senders whose "application received" mail counts as proof: the portals candidates apply through.
PORTALS = ("personio.de", "personio.com", "ashbyhq.com", "greenhouse.io", "lever.co", "join.com", "indeed.com",
           "indeedemail.com", "adp.com", "smartrecruiters.com", "myworkday.com", "myworkdayjobs.com", "workday.com",
           "successfactors.com", "successfactors.eu", "softgarden.io", "softgarden.de", "recruitee.com", "workable.com",
           "teamtailor.com", "bamboohr.com", "onlyfy.io", "dvinci.de", "dvinci-hr.com", "concludis.de", "rexx-systems.com")
# One ATS endpoint from the reader's `endpoint` task; url "" with ats "none" when the company has none.
ENDPOINT = {"type": "object", "additionalProperties": False, "required": ["company", "ats", "url"],
            "properties": {"company": {"type": "string", "maxLength": 200},
                           "ats": {"enum": ["Personio", "Ashby", "Greenhouse", "Lever", "none"]},
                           "url": {"type": "string", "maxLength": 500}}}
# The API forms search_jobs.py reads, host matched exactly (companies.md is also the guard's host allowlist).
ATS_FORMS = {"Personio": re.compile(r"https://[a-z0-9-]+\.jobs\.personio\.(?:de|com)/xml(?:\?language=[a-z]{2})?", re.I),
             "Ashby": re.compile(r"https://api\.ashbyhq\.com/posting-api/job-board/[\w.-]+", re.I),
             "Greenhouse": re.compile(r"https://boards-api\.greenhouse\.io/v1/boards/[\w.-]+/jobs(?:\?content=true)?", re.I),
             "Lever": re.compile(r"https://api(?:\.eu)?\.lever\.co/v0/postings/[\w.-]+(?:\?mode=json)?", re.I)}
RECHECK_DAYS = 30
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
UNREADABLE = {"type": "object", "additionalProperties": False, "required": ["id", "url", "reason"],
              "properties": {"id": {"type": "string", "maxLength": 500}, "url": {"type": "string", "maxLength": 500},
                             "reason": {"type": "string", "maxLength": 200}}}


def is_type(value, name):
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[name])


def validate(value, schema, where="extract"):
    """Problems with value against the subset of JSON Schema the extract schema uses."""
    if "const" in schema:
        return [] if value == schema["const"] else [f"{where}: must be {schema['const']!r}, got {value!r}"]
    if "enum" in schema:
        return [] if value in schema["enum"] else [f"{where}: {value!r} is not one of {schema['enum']}"]
    types = schema.get("type")
    types = [types] if isinstance(types, str) else types or []
    if types and not any(is_type(value, t) for t in types):
        return [f"{where}: expected {' or '.join(types)}, got {type(value).__name__}"]
    out = []
    if isinstance(value, str) and len(value) > schema.get("maxLength", len(value)):
        out.append(f"{where}: longer than {schema['maxLength']} characters")
    if is_type(value, "number"):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            out.append(f"{where}: {value} is outside {schema.get('minimum')}-{schema.get('maximum')}")
    if isinstance(value, list):
        if len(value) > schema.get("maxItems", len(value)):
            out.append(f"{where}: more than {schema['maxItems']} items")
        for i, item in enumerate(value):
            out += validate(item, schema.get("items", {}), f"{where}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        out += [f"{where}: missing {k}" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            out += [f"{where}: unknown field {k}" for k in value if k not in props]
        for k, v in value.items():
            if k in props:
                out += validate(v, props[k], f"{where}.{k}" if where != "extract" else k)
    return out


CONTROL = re.compile(r"[\x00-\x1f\x7f]+")


def clean(value):
    """value with every run of control characters (line breaks, tabs, escape codes) in its strings made a space."""
    if isinstance(value, str):
        return CONTROL.sub(" ", value).strip()
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    return value


def strings(value, where):
    """(field, text) for every string in value, at any depth."""
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from strings(v, f"{where}[{i}]")
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from strings(v, f"{where}.{k}")


def text_problems(data, where="", skip=("url",)):
    """Links, email addresses and instructions in the fields of data other than url (or the keys in skip)."""
    out = []
    for key, value in data.items():
        if key in skip:
            continue
        for field, text in strings(value, where + key):
            if LINK.search(text):
                out.append(f"{field}: holds a link or an email address (only url may)")
            if key != "injection_text" and INSTRUCTION.search(text):
                out.append(f"{field}: reads like an instruction; describe it in injection_text instead")
    return out


def url_problems(url, where="url"):
    if not isinstance(url, str) or not url.startswith("https://"):
        return [f"{where}: must start with https://"]
    if re.search(r"""[\s"'`$\\<>|;\x00-\x1f\x7f]""", url):
        return [f"{where}: holds a character a job link doesn't need (space, quote, backtick, $, backslash, "
                "<, >, | or ;)"]
    if urlparse(url).hostname == "to.indeed.com":
        return [f"{where}: an Indeed short link; use https://de.indeed.com/viewjob?jk=<jk>"]
    return []


def problems(data):
    """Everything wrong with one extract; [] when it is safe to use."""
    if not isinstance(data, dict):
        return ["the extract isn't a JSON object"]
    return validate(data, SCHEMA) + url_problems(data.get("url")) + text_problems(data)


def lead_problems(lead):
    if not isinstance(lead, dict):
        return ["the lead isn't a JSON object"]
    return validate(lead, LEAD, "lead") + url_problems(lead.get("url"), "lead.url") + text_problems(lead, "lead.")


def mail_problems(mail):
    if not isinstance(mail, dict):
        return ["the mail item isn't a JSON object"]
    found = validate(mail, MAIL, "mail") + text_problems(mail, "mail.", skip=("url", "sender_domain"))
    for key in ("date", "interview_date"):
        if isinstance(mail.get(key), str) and not DATE.match(mail[key]):
            found.append(f"mail.{key}: must start with YYYY-MM-DD")
    if isinstance(mail.get("sender_domain"), str) and not DOMAIN.fullmatch(mail["sender_domain"]):
        found.append("mail.sender_domain: must be a domain like personio.de, not an address or a link")
    return found


def base_domain(host):
    return ".".join(host.lower().removeprefix("www.").split(".")[-2:])


def sender_known(domain):
    """True when a mail from this domain can confirm an application: a known portal, or the site of a draft's job
    link (applications/<folder>/job.md)."""
    domain = domain.lower()
    if any(domain == p or domain.endswith("." + p) for p in PORTALS):
        return True
    import appdirs
    for _, folder in appdirs.iter_folders():
        job_md = folder / "job.md"
        text = job_md.read_text(encoding="utf-8", errors="replace") if job_md.exists() else ""
        if any(base_domain(h) == base_domain(domain) for h in re.findall(r"https?://([\w.-]+)", text)):
            return True
    return False


def mail_line(mail):
    sender = mail.get("sender_domain") or ""
    unverified = mail["kind"] == "sent" and not (sender and sender_known(sender))
    return (f"MAIL    {mail['kind']}{' UNVERIFIED' if unverified else ''} | {mail['company']} | {mail['role'] or '-'} | "
            f"{mail['date']} | via {mail['via']}"
            + (f" | interview {mail['interview_date']}" if mail["interview_date"] else "")
            + (f" | from {sender or 'an unknown sender'}" if unverified else ""))


def check_file(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"can't read it ({e})"]
    return problems(data)


# ---------- the workspace's ad files ----------

def file_stem(job_id):
    return re.sub(r"[^\w.-]+", "_", job_id)[:120]


def ads_dir():
    from config import ROOT  # here, not at the top: check and the eval run without a workspace
    return ROOT / "data" / "ads"


def lead_id(url):
    """indeed-<jk> for Indeed, otherwise web-<hash of the URL>."""
    u = urlparse(url)
    jk = parse_qs(u.query).get("jk", [""])[0] if u.hostname and u.hostname.endswith("indeed.com") else ""
    return f"indeed-{jk}" if jk else "web-" + hashlib.sha1(url.encode()).hexdigest()[:12]


def has_extract(job_id):
    path = ads_dir() / f"{file_stem(job_id)}.json"
    return path.exists() and not check_file(path)


def how(job):
    """Where the reader finds a job's ad, as in its task line."""
    root = ads_dir().parent.parent
    text = ads_dir() / f"{file_stem(job['id'])}.txt"
    if text.exists():
        return f"file {text.relative_to(root).as_posix()}"
    if job["id"].startswith("indeed-"):
        return f"indeed {job['id'][7:]}"
    return f"url {job.get('external_url') or job['url']}"


def pending(cands):
    return [j for j in cands["jobs"] if not j.get("seen") and not j.get("read_error") and not has_extract(j["id"])]


def tasks_file():
    return ads_dir() / "tasks.json"


def load_tasks():
    """Today's handed-out tasks: {"date", "ids", "endpoints"}; a list from an earlier day counts as empty."""
    import datetime as dt
    today = dt.date.today().isoformat()
    try:
        data = json.loads(tasks_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict) or data.get("date") != today:
        data = {}
    return {"date": today, "ids": list(data.get("ids") or []), "endpoints": list(data.get("endpoints") or [])}


def hand_out(ids=(), endpoints=()):
    """Add task ids and endpoint companies to today's list in data/ads/tasks.json."""
    import atomic
    tasks = load_tasks()
    tasks["ids"] = list(dict.fromkeys(tasks["ids"] + list(ids)))
    tasks["endpoints"] = list(dict.fromkeys(tasks["endpoints"] + [c.casefold() for c in endpoints]))
    atomic.write_text(tasks_file(), json.dumps(tasks, ensure_ascii=False, indent=1))


def asked_about(item_id, cands, tasks):
    """Problem text when item_id names a job in candidates.json that no task handed out today; None otherwise."""
    job = next((j for j in cands["jobs"] if item_id in (j["id"], j["url"])), None)
    if job and job["id"] not in tasks["ids"]:
        return f"{job['id']} wasn't handed out by extract.py pending or add today; a reply may only answer its own tasks"
    return None


# ---------- companies.md: the watchlist endpoints ----------

def endpoint_ats(url):
    """The ATS whose API form url has (exact host), or None."""
    return next((name for name, form in ATS_FORMS.items() if isinstance(url, str) and form.fullmatch(url)), None)


def companies_file():
    from config import ROOT
    return ROOT / "companies.md"


def watch_rows(lines):
    """(line index, cells) for each company row of the companies.md table: | Company | Careers page | ATS |
    Endpoint | Last checked |."""
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.split("|")]
        if (line.lstrip().startswith("|") and len(cells) >= 7 and cells[1] and cells[1] != "Company"
                and not set(cells[1]) <= set("-: ")):
            yield i, cells


def endpoint_tasks():
    """companies.md rows without an Endpoint that weren't checked in the last RECHECK_DAYS days."""
    import datetime as dt
    path = companies_file()
    if not path.exists():
        return []
    cutoff = (dt.date.today() - dt.timedelta(days=RECHECK_DAYS)).isoformat()
    out = []
    for _, cells in watch_rows(path.read_text(encoding="utf-8").splitlines()):
        checked = DATE.match(cells[5])
        if not cells[4] and (not checked or checked.group(0) < cutoff):
            out.append((cells[1], cells[2] or "-"))
    return out


def write_endpoint(company, ats, url, replace):
    """Write ats / url / today into the company's companies.md row; the summary line, or FAILED with the reason."""
    import datetime as dt

    import atomic
    path = companies_file()
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []
    row = next(((i, cells) for i, cells in watch_rows([ln.rstrip("\r\n") for ln in lines])
                if cells[1].casefold() == company.casefold()), None)
    if not row:
        return f"FAILED  endpoint: no row for {company} in companies.md"
    i, cells = row
    if cells[4] and not replace:
        return f"FAILED  endpoint: {cells[1]} already has an endpoint in companies.md"
    if ats != "none":
        cells[3], cells[4] = ats, url
    cells[5] = dt.date.today().isoformat()
    end = lines[i][len(lines[i].rstrip("\r\n")):]
    lines[i] = "| " + " | ".join(cells[1:-1]) + " |" + end
    atomic.write_text(path, "".join(lines))
    return f"ENDPOINT {cells[1]}: " + (f"{ats} {url}" if ats != "none" else "none found")


def endpoint_problems(item):
    if not isinstance(item, dict):
        return ["the endpoint isn't a JSON object"]
    found = validate(item, ENDPOINT, "endpoint") + text_problems(item, "endpoint.")
    if found:
        return found
    if item["ats"] == "none":
        return [] if item["url"] == "" else ["endpoint.url: must be empty when ats is none"]
    if endpoint_ats(item["url"]) != item["ats"]:
        return [f"endpoint.url: not a {item['ats']} API endpoint of the form search_jobs.py reads "
                "(companies.md lists the forms)"]
    return []


def load_candidates():
    import ledger
    if not ledger.CANDIDATES.exists():
        return {"generated": "", "since": "", "status": {}, "jobs": []}
    return json.loads(ledger.CANDIDATES.read_text(encoding="utf-8"))


def write_candidates(cands):
    import atomic
    import ledger
    atomic.write_text(ledger.CANDIDATES, json.dumps(cands, ensure_ascii=False, indent=1))


def store(extract, cands):
    """Write a valid extract to data/ads/<id>.json and point its job in candidates.json at it; the summary line."""
    import atomic
    path = ads_dir() / f"{file_stem(extract['id'])}.json"
    atomic.write_text(path, json.dumps(extract, ensure_ascii=False, indent=1) + "\n")
    job = next((j for j in cands["jobs"] if j["id"] == extract["id"]), None)
    if job:
        job["extract"] = path.relative_to(ads_dir().parent.parent).as_posix()
        job.pop("read_error", None)
        if not job["title"]:  # a job from `add`: the extract names it
            import ledger
            job.update({k: extract[k] for k in ("title", "company", "location", "role_type")})
            job["key"] = ledger.make_key(job["company"], job["title"])
    inj = len(extract["injection_text"])
    return (f"OK      {extract['id']}: {extract['role_type']}, German {extract['german_required']}, "
            f"{'CLOSED' if extract['closed'] else 'open'}, {len(extract['requirements'])} requirements"
            + (f", {inj} injection attempt(s)" if inj else "") + ("" if job else " (not in candidates.json)"))


def add_lead(lead, cands):
    """Add a lead to candidates.json the way search_jobs.py adds API jobs; the summary line."""
    import ledger
    import search_jobs
    from scope import role_type
    job_id = lead_id(lead["url"])
    if any(j["id"] == job_id or j["url"] == lead["url"] for j in cands["jobs"]):
        return f"LEAD    {job_id}: already in candidates.json"
    if not search_jobs.in_scope(lead["title"]):
        return f"LEAD    {job_id}: dropped by the title filter: {lead['title']}"
    hit = ledger.Index(ledger.load()).find(lead["company"], lead["title"], lead["url"], job_id)
    cands["jobs"].append(dict(id=job_id, source=lead["source"], title=lead["title"], company=lead["company"],
                              location=lead["location"], posted="", url=lead["url"], role_type=role_type(lead["title"]),
                              key=ledger.make_key(lead["company"], lead["title"]), seen=bool(hit),
                              seen_as=f"{hit['first_seen']} {hit['verdict']} {hit['score']}".strip() if hit else ""))
    return f"LEAD    {job_id}: {'SEEN' if hit else 'NEW'} {lead['title']} | {lead['company']} | {lead['location']}"


# ---------- the fallback reader ----------

def claude_json(system, user, schema, model=None):
    """One headless `claude -p` call with no tools and no MCP servers: (structured output, model name, cost)."""
    with tempfile.TemporaryDirectory() as tmp:  # an empty cwd: no project CLAUDE.md or settings
        prompt_file = Path(tmp) / "system.md"
        prompt_file.write_text(system, encoding="utf-8")
        cmd = ["claude", "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config",
               "--no-session-persistence", "--json-schema", json.dumps(schema),
               "--system-prompt-file", str(prompt_file)] + (["--model", model] if model else [])
        r = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8", cwd=tmp, timeout=600)
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        out = {}
    if r.returncode:  # the JSON's result says why (a usage limit, say); otherwise stderr does
        why = out.get("result") or r.stderr or r.stdout
        raise RuntimeError(f"claude -p exited {r.returncode}: {str(why).strip()[:300]}")
    if out.get("is_error") or not isinstance(out.get("structured_output"), dict):
        raise RuntimeError(f"claude -p gave no structured answer: {str(out.get('result'))[:300]}")
    usage = out.get("modelUsage") or {}
    main_model = max(usage, key=lambda m: usage[m].get("costUSD", 0)) if usage else "unknown"
    return out["structured_output"], main_model, out.get("total_cost_usd") or 0


def reader_prompt():
    """The ad-reader agent's instructions (without its frontmatter) and the schema, for a call without tools."""
    body = AGENT_FILE.read_text(encoding="utf-8").split("---\n", 2)[2]
    return (body + "\n\n## This call\nThere are no tools: the ad text is in the message. Return only the extract "
            "object for this one ad.\n\n## engine/templates/ad_extract.schema.json\n" + SCHEMA_FILE.read_text(encoding="utf-8"))


def read_text(job, text, model=None):
    """Extract one ad from its text with the fallback reader: (extract, model, cost)."""
    user = (f"read {job['id']} | the text below | {job['title']} | {job['company']} | {job['url']}\n"
            f"Location from the listing: {job.get('location') or 'not given'}\n\nAd text:\n\n{text}")
    return claude_json(reader_prompt(), user, SCHEMA, model)


# ---------- commands ----------

def cmd_pending(a):
    todo, find = pending(load_candidates()), endpoint_tasks()
    hand_out([j["id"] for j in todo], [company for company, _ in find])
    for j in todo:
        print(f"read {j['id']} | {how(j)} | {j['title']} | {j['company']} | {j['url']}")
    for company, page in find:
        print(f"endpoint | {company} | {page}")
    print(f"{len(todo)} ad(s) to read" + (f", {len(find)} endpoint(s) to find" if find else ""))
    return 0


def cmd_add(a):
    import ledger
    found = url_problems(a.url)
    if found:
        print(f"FAILED: {found[0]}", file=sys.stderr)
        return 1
    cands, job_id = load_candidates(), lead_id(a.url)
    job = next((j for j in cands["jobs"] if a.url == j["url"] or job_id == j["id"]), None)
    if not job:
        job = dict(id=job_id, source="manual", title="", company="", location="", posted="", url=a.url, role_type="",
                   key="", seen=False, seen_as="")
        cands["jobs"].append(job)
        write_candidates(cands)
    idx = ledger.Index(ledger.load())
    hit = idx.by_url.get(a.url) or idx.by_id.get(job["id"])   # by link only: the title isn't known yet
    print(f"SEEN    {hit['first_seen']} {hit['verdict']} {hit['score']} {hit['company']} | {hit['title']}" if hit
          else "NEW     not in the ledger")
    if has_extract(job["id"]):
        print(f"EXTRACT data/ads/{file_stem(job['id'])}.json")
    else:
        hand_out([job["id"]])
        print(f"read {job['id']} | {how(job)} | {job['title'] or 'unknown'} | {job['company'] or 'unknown'} | {job['url']}")
    return 0


def cmd_save(a):
    path = Path(a.reply)
    if path.suffix == ".json":
        return save_reply(path)
    # the folder: missing until the hook saved a first reply
    files = sorted(path.glob("*.json"), key=lambda f: f.stat().st_mtime)
    if not files:
        print(f"no reader replies in {path.as_posix()}/")
        return 1
    bad = 0
    for f in files:  # one file per reader call, saved by .claude/hooks/reader_reply.py
        print(f"== {f.name}")
        failed = save_reply(f)
        bad += failed
        if not failed:
            f.unlink()
        else:  # set aside: a replay would report the same failure, and re-apply its "gone" marks, on every run
            aside = path.with_name("failed") / f.name
            aside.parent.mkdir(parents=True, exist_ok=True)
            f.replace(aside)
            print(f"        kept as {aside.as_posix()} (not read again)")
    return 1 if bad else 0


def save_reply(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:  # ValueError: bad JSON or bytes that aren't UTF-8
        print(f"FAILED  {path.name} can't be read as UTF-8 JSON: {type(e).__name__}", file=sys.stderr)
        return 1
    if not isinstance(data, dict) or set(data) - {"extracts", "leads", "unreadable", "mail", "endpoints"}:
        print("FAILED  the reply must be one JSON object with extracts, leads, unreadable, mail and endpoints",
              file=sys.stderr)
        return 1
    data = clean(data)
    cands, tasks, bad = load_candidates(), load_tasks(), 0
    for mail in data.get("mail") or []:
        found = mail_problems(mail)
        bad += bool(found)
        print("\n".join(["FAILED  mail"] + [f"  {x}" for x in found]) if found else mail_line(mail))
    for ext in data.get("extracts") or []:
        found = problems(ext)
        if not found:
            found = [x for x in [asked_about(ext["id"], cands, tasks)] if x]
        if found:
            bad += 1
            print("\n".join([f"FAILED  {ext.get('id', '?') if isinstance(ext, dict) else '?'}"] + [f"  {x}" for x in found]))
        else:
            print(store(ext, cands))
    for lead in data.get("leads") or []:
        found = lead_problems(lead)
        if found:
            bad += 1
            print("\n".join(["FAILED  lead"] + [f"  {x}" for x in found]))
        else:
            print(add_lead(lead, cands))
    for item in data.get("unreadable") or []:
        found = validate(item, UNREADABLE, "unreadable") + (text_problems({"reason": item["reason"]})
                                                             if isinstance(item, dict) and "reason" in item else [])
        if not found:
            found = [x for x in [asked_about(item["id"], cands, tasks)] if x]
        if found:
            bad += 1
            print("\n".join(["FAILED  unreadable"] + [f"  {x}" for x in found]))
            continue
        job = next((j for j in cands["jobs"] if item["id"] in (j["id"], j["url"])), None)
        if job:
            job["read_error"] = item["reason"]
        print(f"CLOSED  {item['id']}: page gone" if item["reason"] == "gone"
              else f"UNREAD  {item['id']}: {item['reason']}")
    for item in data.get("endpoints") or []:
        found = endpoint_problems(item)
        if not found and item["company"].casefold() not in tasks["endpoints"]:
            found = [f"{item['company']} wasn't handed out as an endpoint task by extract.py pending today"]
        line = "FAILED  endpoint" if found else write_endpoint(item["company"], item["ats"], item["url"], replace=False)
        bad += line.startswith("FAILED")
        print("\n".join([line] + [f"  {x}" for x in found]))
    write_candidates(cands)
    return 1 if bad else 0


def cmd_read(a):
    cands = load_candidates()
    todo = [j for j in (pending(cands) if not a.ids else [j for j in cands["jobs"] if j["id"] in a.ids])
            if (ads_dir() / f"{file_stem(j['id'])}.txt").exists()]
    bad = 0
    for j in todo:
        text = (ads_dir() / f"{file_stem(j['id'])}.txt").read_text(encoding="utf-8")
        try:
            ext, _, _ = read_text(j, text, a.model)
            ext = clean(ext)
        except (RuntimeError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            bad += 1
            print(f"FAILED  {j['id']}: {e}")
            continue
        ext.update(id=j["id"], url=j["url"])
        found = problems(ext)
        bad += bool(found)
        print(store(ext, cands) if not found else "\n".join([f"FAILED  {j['id']}"] + [f"  {x}" for x in found]))
    write_candidates(cands)
    print(f"{len(todo)} ad file(s) read")
    return 1 if bad else 0


def cmd_attach(a):
    import appdirs
    folder = appdirs.find(a.folder)
    if not folder:
        print(f"FAILED: no application folder '{a.folder}'", file=sys.stderr)
        return 1
    copied = []
    for suffix, name in ((".json", "ad.json"), (".txt", "ad.txt")):
        src = ads_dir() / f"{file_stem(a.id)}{suffix}"
        if src.exists():
            shutil.copyfile(src, folder / name)
            copied.append(name)
    if not copied:
        print(f"FAILED: no extract or ad text for {a.id} in data/ads/", file=sys.stderr)
        return 1
    print(f"OK {folder.name}: {', '.join(copied)}")
    return 0


def cmd_endpoint(a):
    ats = endpoint_ats(a.url)
    if not ats:
        print(f"FAILED  {a.url} isn't a Personio, Ashby, Greenhouse or Lever API endpoint (companies.md lists the "
              "forms)", file=sys.stderr)
        return 1
    line = write_endpoint(a.company, ats, a.url, replace=True)
    print(line)
    return 1 if line.startswith("FAILED") else 0


def cmd_check(a):
    files = []
    for p in map(Path, a.paths):
        files += sorted(p.glob("*.json")) if p.is_dir() else [p]
    bad = 0
    for f in files:
        found = check_file(f)
        bad += bool(found)
        print(f"OK      {f}" if not found else "\n".join([f"FAILED  {f}"] + [f"  {x}" for x in found]))
    print(f"{len(files) - bad} of {len(files)} extracts valid")
    return 1 if bad or not files else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pending")
    ad = sub.add_parser("add")
    ad.add_argument("url")
    s = sub.add_parser("save")
    s.add_argument("reply")
    r = sub.add_parser("read")
    r.add_argument("ids", nargs="*")
    r.add_argument("--model")
    t = sub.add_parser("attach")
    t.add_argument("id")
    t.add_argument("folder")
    e = sub.add_parser("endpoint")
    e.add_argument("company")
    e.add_argument("url")
    c = sub.add_parser("check")
    c.add_argument("paths", nargs="+")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    return {"pending": cmd_pending, "add": cmd_add, "save": cmd_save, "read": cmd_read, "attach": cmd_attach, "endpoint": cmd_endpoint,
            "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
