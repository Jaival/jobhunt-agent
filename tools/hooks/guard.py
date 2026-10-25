"""PreToolUse hook: refuse tool calls that could damage the workspace or leak the candidate's data.

Claude Code runs it before each matching tool call (the workspace's .claude/settings.json, installed by
setup_check.py --init, starts it through .claude/hooks/jobhunt_guard.py). It reads the call as JSON on stdin and
exits 2 with a one-line reason on stderr to block it; the model sees the reason and lists the block in the brief.

What it blocks (docs/spike-scheduled-tasks.md, "Browser and network policy"):
- writes into engine/, .claude/ and the master CV and letter: file tools by path, Bash/PowerShell by pattern;
- the tools that send or type data (Gmail send / reply / drafts, browser typing and form filling), also denied
  by the permission rules;
- curl, wget, Invoke-WebRequest, WebFetch and inline Python HTTP calls to hosts outside the allowlist (the job
  APIs, plus every host in companies.md and sources.md); to.indeed.com only as the redirect lookup;
- URLs that leak: the candidate's name, email, phone, address, birth date or a distinctive last name (also hidden
  in base64, base32, hex or double URL-encoding in any path segment or query value), a long encoded value, an IP
  address, a port or a scheme other than http(s). Browser navigation may go to any host but gets this check, and on
  a host outside companies.md and sources.md also a shorter value that decodes to text or looks random;
- browser scripts that make network calls (fetch, XMLHttpRequest, sendBeacon, WebSocket, ...).

Every call it sees refreshes data/guard.json (the heartbeat); blocks are appended to data/guard.log.
`python engine/tools/hooks/guard.py --status` prints whether the guard is active in this session: run through
Bash, the hook itself sees that call first, so a fresh heartbeat proves it ran.

Limits: plain words in a URL (`?cv=SAP+FI+5+years`) can't be told from a search query, so CV facts that aren't
personal markers pass, as does text encoded in a way it doesn't try (reversed, ciphered, split over several
parameters). A bare first name or common last name isn't a marker. It reads Bash as text, not as a shell would.
`cd engine && ...`, generated code or an encoded command get past it, and so can a page told something by which URL
is opened. The permission rules are the main
control; this is defence in depth. It never blocks because of its own error: a crash lets the call through and is
logged.
"""
import base64
import binascii
import datetime as dt
import ipaddress
import json
import os
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import atomic  # noqa: E402

ROOT = Path(os.environ.get("JOBHUNT_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or TOOLS.parents[1])
HEARTBEAT = ROOT / "data" / "guard.json"
LOG = ROOT / "data" / "guard.log"
FRESH = 120   # seconds: --status counts the guard as active when it saw a call this recently

API_HOSTS = ["rest.arbeitsagentur.de", "arbeitnow.com", "jobs.personio.de", "jobs.personio.com", "api.ashbyhq.com",
             "boards-api.greenhouse.io", "api.lever.co", "api.eu.lever.co", "api.smartrecruiters.com",
             "myworkdayjobs.com"]
SEND_TOOLS = re.compile(r"^mcp__.+__(send_message|reply|forward|create_draft|update_draft|trash_\w+|\w*spam\w*|"
                        r"share_file|browser_type|browser_fill\w*|browser_select_option|browser_press_key|"
                        r"browser_set_\w+|browser_upload\w*|form_input)$")
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
NAVIGATE = re.compile(r"^mcp__.+__(browser_)?navigate$")
SCRIPT_TOOLS = re.compile(r"^mcp__.+__(browser_evaluate|javascript_tool)$")
NETWORK_JS = re.compile(r"\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource|\bimport\s*\(|"
                        r"window\.open|\blocation(\.href)?\s*=(?!=)|\.(src|href|action)\s*=(?!=)|\.submit\s*\(")
FETCHERS = re.compile(r"(?<![\w-])(curl|wget|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)(?:\.exe)?(?![\w-])", re.I)
PY_HTTP = re.compile(r"\b(requests|urllib|httpx|http\.client|aiohttp|urlopen)\b")
INLINE_CODE = re.compile(r"python3?(\.exe)?\s+-c|<<|-Command|\bnode\s+-e")
BARE = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d+)?(?:[/?#]\S*)?", re.I)   # host[/path] without a scheme
# Options of curl / wget / Invoke-WebRequest that take a value (skipped when looking for the target host).
SHORT_ARGS = {"-o", "-O", "-w", "-A", "-H", "-d", "-X", "-m", "-e", "-u", "-b", "-c", "-D", "-T", "-F", "-r", "-U",
              "-t", "-P"}
LONG_ARGS = {"--output", "--write-out", "--user-agent", "--header", "--data", "--data-raw", "--data-binary",
             "--data-urlencode", "--json", "--request", "--max-time", "--connect-timeout", "--referer", "--user",
             "--cookie", "--cookie-jar", "--dump-header", "--upload-file", "--form", "--retry", "--range",
             "--output-document", "--post-data", "--tries", "-outfile", "-method", "-headers", "-body",
             "-useragent", "-timeoutsec", "-contenttype"}
REDIRECT_LOOKUP = re.compile(r"-o\s+(/dev/null|NUL)\b|(?<!\S)(-I|--head|-\w*I)(?!\S)")
SENDS_DATA = re.compile(r"(?<!\S)(-d|--data\S*|-F|--form\S*|-T|--upload-file|--json|-X\s*(POST|PUT|PATCH))(?!\S)")
COPY_CMDS = {"cp", "copy", "copy-item", "xcopy", "robocopy", "ln", "unzip", "tar"}
RUNS_TOOL = re.compile(r"\s*python3?(\.exe)?\s+(\S*[/\\])?engine[/\\]tools[/\\]")
HOST = re.compile(r"(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)
WRITE_CMD = re.compile(r"(?<![\w-])(cp|mv|rm|rmdir|tee|touch|truncate|ln|chmod|dd|unzip|tar|sed\s+-i|perl\s+-i|"
                       r"Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item|Rename-Item|"
                       r"del|erase|copy|move|ren|xcopy|robocopy)(?![\w-])", re.I)
WRITE_CODE = re.compile(r"open\([^)]*,\s*['\"][^'\"]*[wax+]|write_text|write_bytes|\.unlink|rmtree|os\.remove|"
                        r"os\.rename|os\.replace|shutil\.(copy|move)|\.save\(|WriteAllText|\.touch\(")
ENCODED = re.compile(r"^(?:[0-9a-f]{64,}|[A-Za-z0-9+/_=-]{64,})$")
SLUG = re.compile(r"[A-Za-z0-9]{1,30}(?:[-_]+[A-Za-z0-9]{1,30})+")   # words and ids joined by hyphens
UUID = re.compile(r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}", re.I)
LABELED = re.compile(r"(?im)^[-*\s]*(?:address|adresse|anschrift|born|birth\w*|date of birth|dob|geboren\w*|"
                     r"geburt\w*)\s*[:=]\s*(.+)$")
STREET = re.compile(r"\b[^\W\d_][\w.-]*(?:stra(?:ß|ss)e|str\.|weg|platz|allee|gasse|damm)\s*\d+\s*[a-z]?\b", re.I)
PROFILE = re.compile(r"(?:linkedin\.com/in|xing\.com/profile)/([\w.%-]{4,})", re.I)
# Not markers on their own: mailbox names, and surnames that are everyday words (a job search may use them).
GENERIC_LOCAL = {"info", "kontakt", "contact", "bewerbung", "bewerbungen", "jobs", "karriere", "career", "careers",
                 "hello", "office", "mail", "post", "service", "support", "recruiting", "personal", "hallo"}
COMMON_NAMES = {"koch", "bauer", "schneider", "schmied", "schmid", "maurer", "richter", "lehrer", "jaeger", "jäger",
                "meister", "fuchs", "wolf", "klein", "gross", "groß", "lang", "krueger", "krüger", "vogel", "hahn",
                "stein", "berg", "wald", "winter", "sommer", "frank", "ernst", "kaiser", "koenig", "könig", "braun",
                "weiss", "weiß", "schwarz", "roth", "fisher", "baker", "smith", "miller", "young", "king", "hall"}


class Block(Exception):
    pass


# ---------- what the workspace protects and allows ----------

def config():
    try:
        import yaml
        return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def protected(cfg):
    """Workspace paths (resolved) that tool calls must not write: engine/, .claude/, the master files."""
    paths = [ROOT / "engine", ROOT / ".claude"]
    for key in ("master_cv", "master_letter"):
        if cfg.get(key):
            paths.append(ROOT / str(cfg[key]))
    return [p.resolve() for p in paths]


class Pii(list):
    """Regexes that must not appear anywhere in a URL; .weak (a distinctive last name) only in query values."""
    weak = ()


def marker(words):
    return re.compile(r"[\W_]*".join(re.escape(w.lower()) for w in words))


def personal(cfg):
    """Regexes for the candidate's name, emails, phone numbers, address and birth date (config.yaml, CLAUDE.md)."""
    out, out.weak = Pii(), []
    titles = set(re.findall(r"[a-zäöüß]{3,}", str((cfg.get("profile") or {}).get("include_titles")).lower()))
    for key in ("applicant", "name_in_master"):
        words = re.findall(r"\w+", str(cfg.get(key) or ""))
        if len(words) >= 2 and str(cfg.get(key)) != "Your Name":
            out.append(marker(words))
            last = words[-1].lower()
            if len(last) >= 4 and last.isalpha() and last not in COMMON_NAMES | titles:
                out.weak.append(re.compile(rf"(?<![^\W\d_]){last}(?![^\W\d_])"))
    try:
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    except OSError:
        text = ""
    for email in set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)):
        out.append(re.compile(re.escape(email.lower())))
        local = email.lower().split("@")[0]
        if len(local) >= 6 and local not in GENERIC_LOCAL:
            out.append(re.compile(re.escape(local)))
    for phone in set(re.findall(r"\+?\d[\d ()/.-]{7,}\d", text)):
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 8:
            out.append(re.compile(r"\D*".join(digits[-8:])))
    for value in LABELED.findall(text):
        words = re.findall(r"\w+", value)
        if len(words) >= 2 and len("".join(words)) >= 8:
            out.append(marker(words))
    for street in STREET.findall(text):
        out.append(marker(re.findall(r"\w+", street)))
    for slug in PROFILE.findall(text):
        out.append(re.compile(re.escape(unquote(slug).lower())))
    return out


def allowed_hosts():
    hosts = set(API_HOSTS)
    for name in ("companies.md", "sources.md"):
        try:
            hosts |= {h.lower() for h in HOST.findall((ROOT / name).read_text(encoding="utf-8"))}
        except OSError:
            pass
    return hosts


def host_ok(host, hosts):
    return any(host == h or host.endswith("." + h) for h in hosts)


# ---------- checks ----------

def unquoted(text):
    """URL-decoded until nothing changes (a double-encoded %2540 is still found)."""
    for _ in range(4):
        new = unquote(text)
        if new == text:
            break
        text = new
    return text


def chunks(parts):
    """(text, kind) for each path segment, query key and value and fragment part, URL-decoded but not split further;
    kind is "path", "query" or "joined" (the segments run together, for base64 that contains slashes)."""
    segs = [s for s in parts.path.split("/") if s]
    out = [(unquoted(s), "path") for s in segs] + [(unquoted("".join(segs)), "joined")] * (len(segs) > 1)
    for q in (parts.query, parts.fragment):
        for pair in re.split(r"[&;]", q):
            out += [(unquoted(x), "query") for x in pair.split("=", 1) if x]
    return out


def tokens(v):
    return [v] + [t for t in re.split(r"[\s.,;:|~]+", v) if t and t != v]


def decodings(v):
    """What a value may encode: hex, base64 / base64url (with or without padding, hyphens dropped) and base32."""
    out = []
    hexed = re.sub(r"(?i)0x|\\x|[\s:,._-]", "", v)
    if re.fullmatch(r"(?:[0-9a-f]{2}){4,}", hexed, re.I):
        out.append(bytes.fromhex(hexed))
    for w in {v, v.replace("-", "")}:
        if re.fullmatch(r"[A-Za-z0-9+/_=-]{8,}", w):
            b64 = w.replace("-", "+").replace("_", "/").rstrip("=")
            b64 = b64[:-1] if len(b64) % 4 == 1 else b64
            try:
                out.append(base64.b64decode(b64 + "=" * (-len(b64) % 4)))
            except (binascii.Error, ValueError):
                pass
    if re.fullmatch(r"[A-Za-z2-7]{8,}=*", v):
        try:
            out.append(base64.b32decode(v.rstrip("=").upper() + "=" * (-len(v.rstrip("=")) % 8)))
        except (binascii.Error, ValueError):
            pass
    return out


def expansions(v, depth=2):
    """v and the text hidden in it by up to `depth` layers of encoding."""
    seen, level = [v], [v]
    for _ in range(depth):
        level = [d.decode("utf-8", "ignore") for x in level for t in tokens(x) for d in decodings(t)]
        seen += level
    return seen


def is_text(data):
    """Bytes that read as words: mostly printable ASCII with some letters (random bytes and ids don't)."""
    s = data.decode("latin-1")
    return (len(s) >= 8 and sum(32 <= ord(c) < 127 or c in "\n\t" for c in s) >= 0.9 * len(s)
            and sum(c.isalpha() for c in s) >= max(6, 0.5 * len(s)))


def looks_random(t):
    """A mixed-case letters-and-digits run of 16+ characters that switches case like base64, not like CamelCase."""
    if len(t) < 16 or not re.fullmatch(r"[A-Za-z0-9+/_=]+", t) or UUID.fullmatch(t):
        return False
    letters = [c for c in t if c.isalpha()]
    switches = sum(a.isupper() != b.isupper() for a, b in zip(letters, letters[1:]))
    return len(letters) >= 4 and any(c.isdigit() for c in t) and switches >= 0.3 * len(letters)


def opaque(v):
    """True when v hides text (base64 / hex that decodes to words) or looks random, outside slugs, UUIDs and ids."""
    for t in tokens(v):
        if len(t) < 12 or UUID.fullmatch(t):
            continue
        if looks_random(t) or any(is_text(d) for d in decodings(t)):
            return True
    return False


def check_url(url, pii, hosts=None, known=None):
    """Raise Block when url leaks data, or (with hosts) when its host isn't allowed. Outside the hosts in
    `hosts` or `known` (which only widens the leak check, e.g. for browser navigation) a short encoded value
    that decodes to text or looks random is refused too."""
    if url in ("about:blank",):
        return
    parts = urlsplit(url if "://" in url else "https://" + url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https"):
        raise Block(f"only http(s) URLs, not {parts.scheme}:")
    try:
        ipaddress.ip_address(host)
        raise Block(f"{host} is an IP address; use the site's name")
    except ValueError:
        pass
    if parts.port not in (None, 80, 443):
        raise Block(f"port {parts.port} isn't allowed; only the default web ports")
    text = unquoted(url).lower()
    leak = ("the URL contains the candidate's name, email or phone number, or other personal data; never put "
            "personal data in a URL (for the candidate's own pages use projects.md and CLAUDE.md)")
    if any(p.search(text) for p in pii):
        raise Block(leak)
    trusted = hosts if hosts is not None else known
    unknown = trusted is not None and not host_ok(host, trusted)
    for value, kind in chunks(parts):
        for t in expansions(value):
            t = t.lower()
            weak = getattr(pii, "weak", ()) if kind == "query" else ()
            if any(p.search(t) for p in pii) or any(p.search(t) for p in weak):
                raise Block(leak)
        if kind == "joined":
            continue
        for t in tokens(value):
            if ENCODED.match(t) and not SLUG.fullmatch(t):
                raise Block("the URL carries a long encoded value; open the page without it")
        if unknown and opaque(value):
            raise Block(f"the URL carries an encoded or random-looking value to {host}, which isn't in companies.md "
                        "or sources.md; open the page without that parameter (job pages work without tracking values)")
    if hosts is not None and not host_ok(host, hosts):
        raise Block(f"{host} isn't an allowed API host for curl/WebFetch: read web pages with the obscura "
                    "browser, or add the company's API endpoint to companies.md")


def check_path(path, cwd, protect):
    p = Path(path)
    p = (p if p.is_absolute() else Path(cwd) / p).resolve()
    for q in protect:
        if p == q or q in p.parents:
            raise Block(f"{rel(q)} is read-only: the engine, Claude's settings and the master CV and letter are "
                        "never changed by a run (propose changes in the brief instead)")


def rel(p):
    try:
        return p.relative_to(ROOT.resolve()).as_posix() + ("" if p.suffix else "/")
    except ValueError:
        return str(p)


def path_patterns(protect):
    """(label, path regex, redirect regex) per protected path, as it can appear in a command."""
    root = ROOT.resolve()
    out = []
    for q in protect:
        forms = {q.as_posix()} | ({q.relative_to(root).as_posix()} if root in q.parents else set())
        alt = "|".join(re.escape(f).replace("/", r"[/\\]+") for f in sorted(forms, key=len, reverse=True))
        tail = r"""(?=$|[/\\\s'")])"""
        out.append((rel(q), re.compile(rf"""(?:^|(?<=[\s'"=(,]))(?:\./)?(?:{alt}){tail}""", re.I),
                    re.compile(rf""">{{1,2}}\s*['"]?(?:\./)?(?:{alt}){tail}""", re.I)))
    return out


def segments(cmd):
    return re.split(r"&&|\|\||;|\|", cmd)


def check_writes(cmd, protect):
    for label, path, redirect in path_patterns(protect):
        if redirect.search(cmd):
            raise Block(f"the command writes into {label}, which is read-only")
        for seg in segments(cmd):
            if not path.search(seg) or RUNS_TOOL.match(seg):
                continue
            m = WRITE_CMD.search(seg)
            if m and m.group(1).lower() in COPY_CMDS:
                args = seg[m.end():].split()
                hit = bool(args) and bool(path.search(args[-1]))   # only the last argument is written
            else:
                hit = bool(m) or bool(WRITE_CODE.search(seg))
            if hit:
                raise Block(f"the command changes {label}, which is read-only: the engine, Claude's settings and "
                            "the master CV and letter are never changed by a run (propose changes in the brief)")


def hostname(url):
    return (urlsplit(url if "://" in url else "https://" + url).hostname or "").lower()


def fetch_targets(seg):
    """Positional arguments of a curl/wget/Invoke-WebRequest call that look like a URL or host."""
    try:
        tokens = shlex.split(seg, posix=True)
    except ValueError:
        tokens = seg.split()
    out, skip = [], False
    for t in tokens[1:] if tokens else []:
        if skip:
            skip = False
            continue
        if t.startswith("-"):
            skip = t in SHORT_ARGS or t.lower() in LONG_ARGS
            continue
        if BARE.fullmatch(t) or t.lower().startswith(("http://", "https://")):
            out.append(t)
    return out


def check_network(cmd, pii, hosts):
    if not (FETCHERS.search(cmd) or (PY_HTTP.search(cmd) and INLINE_CODE.search(cmd))):
        return
    if re.search(r"(?<!\S)(-x|--proxy|--socks\S*|--connect-to|--resolve)(?!\S)", cmd):
        raise Block("proxy and host-override options aren't allowed")
    for seg in segments(cmd):
        urls = set(re.findall(r"https?://[^\s'\"<>`|;)]+", seg))
        if FETCHERS.search(seg):
            urls |= set(fetch_targets(seg[FETCHERS.search(seg).start():]))
        for u in urls:
            if hostname(u) == "to.indeed.com":
                if not REDIRECT_LOOKUP.search(seg) or SENDS_DATA.search(seg):
                    raise Block('to.indeed.com is allowed only as the redirect lookup: '
                                'curl -s -o /dev/null -w "%{redirect_url}" <short link>')
                check_url(u, pii)
            else:
                check_url(u, pii, hosts)
    if any(p.search(cmd.lower()) for p in pii):
        raise Block("the command would send the candidate's name, email or phone number over the network")


def check(call):
    tool = call.get("tool_name") or ""
    inp = call.get("tool_input") or {}
    cwd = call.get("cwd") or str(ROOT)
    if SEND_TOOLS.match(tool):
        raise Block(f"{tool} sends or types data; the routine never sends anything (drafts go in applications/)")
    cfg = config()
    if tool in FILE_TOOLS:
        check_path(inp.get("file_path") or inp.get("notebook_path") or "", cwd, protected(cfg))
    elif tool in SHELL_TOOLS:
        cmd = inp.get("command") or ""
        check_writes(cmd, protected(cfg))
        check_network(cmd, personal(cfg), allowed_hosts())
    elif tool == "WebFetch":
        check_url(inp.get("url") or "", personal(cfg), allowed_hosts())
    elif NAVIGATE.match(tool):
        check_url(inp.get("url") or "", personal(cfg), known=allowed_hosts())
    elif SCRIPT_TOOLS.match(tool):
        script = inp.get("expression") or inp.get("script") or inp.get("text") or json.dumps(inp)
        if NETWORK_JS.search(script):
            raise Block("page scripts may only read the page: no fetch, XMLHttpRequest, sendBeacon, WebSocket, "
                        "window.open or changing location/src/href")
    elif tool.startswith("mcp__") and tool.endswith(("__computer", "__browser_batch")):
        text = json.dumps(inp)
        if re.search(r'"action":\s*"(type|key)"', text):
            raise Block("typing into a page isn't allowed; the routine only reads pages")
        pii = personal(cfg)
        hosts = allowed_hosts()
        for u in re.findall(r'"url":\s*"([^"]+)"', text):
            check_url(u, pii, known=hosts)


# ---------- heartbeat, log, status ----------

def now():
    return dt.datetime.now(dt.timezone.utc)


def beat(call, blocked=None):
    if os.environ.get("JOBHUNT_GUARD_SELFTEST"):  # setup_check.py proving the hook starts: not a real call
        return
    try:
        state = json.loads(HEARTBEAT.read_text(encoding="utf-8")) if HEARTBEAT.exists() else {}
    except (OSError, ValueError):
        state = {}
    sid = call.get("session_id") or ""
    if state.get("session_id") != sid:
        state = {"session_id": sid, "calls": 0, "blocked": 0}
    state["calls"] += 1
    state["blocked"] += bool(blocked)
    state["last_seen"] = now().isoformat(timespec="seconds")
    try:
        atomic.write_text(HEARTBEAT, json.dumps(state) + "\n")
        if blocked:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"time": state["last_seen"], "session_id": sid, "tool": call.get("tool_name"),
                                    "agent": call.get("agent_type"), "reason": blocked}) + "\n")
    except OSError:
        pass  # a read-only or missing data/ folder must not block the call


def status():
    try:
        state = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
        age = (now() - dt.datetime.fromisoformat(state["last_seen"])).total_seconds()
    except (OSError, ValueError, KeyError):
        state, age = {}, None
    if age is None or age > FRESH:
        print("guard NOT active: no tool call reached engine/tools/hooks/guard.py in this session. The task must be "
              "a local Code-tab task on this folder; run python engine/tools/setup_check.py --init")
        return 1
    reasons = []
    if state.get("blocked") and LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("session_id") == state.get("session_id"):
                reasons.append(f"{e.get('tool')}: {e.get('reason')}")
    print(f"guard active: {state.get('calls', 0)} call(s) checked, {state.get('blocked', 0)} blocked this session")
    for r in reasons[-10:]:
        print(f"  blocked {r}")
    return 0


def main():
    if sys.argv[1:] == ["--status"]:
        return status()
    try:
        call = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except ValueError:
        return 0
    try:
        check(call)
    except Block as e:
        beat(call, str(e))
        print(f"guard: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # never block because of the guard's own bug
        beat(call)
        try:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"time": now().isoformat(timespec="seconds"), "error": repr(e)}) + "\n")
        except OSError:
            pass
        return 0
    beat(call)
    return 0


if __name__ == "__main__":
    sys.exit(main())
