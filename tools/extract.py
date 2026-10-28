"""Ad extracts: the fixed fields the routine reads instead of raw ad text (templates/ad_extract.schema.json).

Job ads are untrusted text that can carry instructions (RULES.md rule 7). The ad reader turns each ad into an
extract: a JSON object with fixed fields (title, company, location, role type, closed flag + evidence, German
level, hours, start, duration, years of experience, requirements with importance, tasks) and `injection_text`
for any instructions found. `check` proves an extract is well-formed before the routine relies on it: it follows
the schema, and no field except url and injection_text holds a link, an email address or an instruction to an AI.

Usage (from the workspace folder):
    python engine/tools/extract.py check <file.json | folder> [...]
        exit 0 when every extract is valid, 1 otherwise (one line per problem)
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "templates" / "ad_extract.schema.json"
SCHEMA = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
VERSION = SCHEMA["properties"]["ad_extract_version"]["const"]
TYPES = {"string": str, "boolean": bool, "object": dict, "array": list, "null": type(None)}
LINK = re.compile(r"https?://|www\.|\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b|\b[\w-]+\.(?:com|de|io|net|org|ly)/", re.I)
INSTRUCTION = re.compile(r"\b(?:ignore (?:all|any|the|previous|prior|above)|disregard (?:all|the|previous)|"
                         r"system prompt|you are (?:an? )?(?:ai|assistant|language model)|as an ai\b|"
                         r"(?:ai|llm|assistant|language model)s? (?:must|should|are instructed)|"
                         r"\b(?:send|e-?mail|forward) (?:the|your|this|all) (?:cv|resume|data|files?))", re.I)


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


def problems(data):
    """Everything wrong with one extract; [] when it is safe to use."""
    if not isinstance(data, dict):
        return ["the extract isn't a JSON object"]
    out = validate(data, SCHEMA)
    if isinstance(data.get("url"), str) and not data["url"].startswith("https://"):
        out.append("url: must start with https://")
    for key, value in data.items():
        if key in ("url", "injection_text"):
            continue
        for field, text in strings(value, key):
            if LINK.search(text):
                out.append(f"{field}: holds a link or an email address (only url may)")
            if INSTRUCTION.search(text):
                out.append(f"{field}: reads like an instruction; quote it in injection_text instead")
    return out


def check_file(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"can't read it ({e})"]
    return problems(data)


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
    c = sub.add_parser("check")
    c.add_argument("paths", nargs="+")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    return cmd_check(a)


if __name__ == "__main__":
    sys.exit(main())
