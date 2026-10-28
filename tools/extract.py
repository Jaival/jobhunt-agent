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

Usage (from the workspace folder):
    python engine/tools/extract.py pending                the reader's task lines for every new job without an extract
    python engine/tools/extract.py save data/ads/incoming.json
        the reader's reply: saves valid extracts, adds its leads (Indeed, Gmail, web) to candidates.json with the
        title filter and ledger check, records unreadable ads; one line per item, exit 1 when one is invalid
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


def text_problems(data, where=""):
    """Links, email addresses and instructions in the fields of data other than url."""
    out = []
    for key, value in data.items():
        if key == "url":
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
    todo = pending(load_candidates())
    for j in todo:
        print(f"read {j['id']} | {how(j)} | {j['title']} | {j['company']} | {j['url']}")
    print(f"{len(todo)} ad(s) to read")
    return 0


def cmd_save(a):
    data = json.loads(Path(a.reply).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - {"extracts", "leads", "unreadable"}:
        print("FAILED  the reply must be one JSON object with extracts, leads and unreadable", file=sys.stderr)
        return 1
    cands, bad = load_candidates(), 0
    for ext in data.get("extracts") or []:
        found = problems(ext)
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
        if found:
            bad += 1
            print("\n".join(["FAILED  unreadable"] + [f"  {x}" for x in found]))
            continue
        job = next((j for j in cands["jobs"] if item["id"] in (j["id"], j["url"])), None)
        if job:
            job["read_error"] = item["reason"]
        print(f"UNREAD  {item['id']}: {item['reason']}")
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
    s = sub.add_parser("save")
    s.add_argument("reply")
    r = sub.add_parser("read")
    r.add_argument("ids", nargs="*")
    r.add_argument("--model")
    t = sub.add_parser("attach")
    t.add_argument("id")
    t.add_argument("folder")
    c = sub.add_parser("check")
    c.add_argument("paths", nargs="+")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    return {"pending": cmd_pending, "save": cmd_save, "read": cmd_read, "attach": cmd_attach, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
