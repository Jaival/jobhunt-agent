"""Fit score (routine step 4): five 0-5 sub-scores from engine/rubric.md in, the 0-100 score and its reasons out.

The model judges each criterion against the written anchors in rubric.md; the arithmetic is here, so the same
sub-scores always give the same total:
- skills sets the base: 5 -> 95, 4 -> 88, 3 -> 70, 2 -> 58, 1 -> 35, 0 -> 15;
- seniority, language, location and hours each take points off below 5: 4 -> 2, 3 -> 5, 2 -> 8, 1 -> 20, 0 -> 30,
  times the criterion's weight (1 by default);
- `bonus_points` (3) for each config.yaml `profile.score_bonus` skill the ad names, at most two;
- a 0 for a blocker criterion (seniority, language, location, hours) is a hard mismatch, which halves the total,
  so it always lands below 60, under every threshold the routine acts on.
These levels were set against the labelled ads in tests/evals (tests/evals/README.md). config.yaml can change them:
    scoring:
      weights: {location: 2, hours: 0}     # deductions count double for location, not at all for hours
      blockers: [seniority, location]      # which criteria give a hard mismatch at 0
      bonus_points: 5

Usage (from the workspace folder):
    python engine/tools/score.py skills=4 seniority=5 language=3 location=5 hours=4 [--ad data/ads/<id>.json] [--json]
        --ad   the job's extract: its title, requirements and tasks are searched for the score_bonus skills
"""
import argparse
import json
import re
import sys
from pathlib import Path

CRITERIA = ("skills", "seniority", "language", "location", "hours")
OTHERS = CRITERIA[1:]
SKILLS_BASE = {5: 95, 4: 88, 3: 70, 2: 58, 1: 35, 0: 15}
DEDUCTION = {5: 0, 4: 2, 3: 5, 2: 8, 1: 20, 0: 30}
WEIGHTS = dict.fromkeys(OTHERS, 1)
BLOCKERS = list(OTHERS)
BONUS_POINTS, MAX_BONUS_TERMS = 3, 2


def settings(cfg):
    """The scoring settings from a config.yaml dict. Raises ValueError on a bad `scoring:` block."""
    s = cfg.get("scoring") or {}
    if not isinstance(s, dict) or set(s) - {"weights", "blockers", "bonus_points"}:
        raise ValueError("config.yaml scoring: may only hold weights, blockers and bonus_points")
    weights = {**WEIGHTS, **(s.get("weights") or {})}
    if set(weights) - set(OTHERS) or not all(isinstance(w, (int, float)) and w >= 0 for w in weights.values()):
        raise ValueError(f"config.yaml scoring.weights: numbers of 0 or more for {', '.join(OTHERS)}")
    blockers = s.get("blockers", BLOCKERS)
    if not isinstance(blockers, list) or set(blockers) - set(CRITERIA):
        raise ValueError(f"config.yaml scoring.blockers: a list drawn from {', '.join(CRITERIA)}")
    bonus = s.get("bonus_points", BONUS_POINTS)
    if not isinstance(bonus, (int, float)) or bonus < 0:
        raise ValueError("config.yaml scoring.bonus_points: a number of 0 or more")
    terms = [str(t) for t in ((cfg.get("profile") or {}).get("score_bonus") or [])]
    return {"weights": weights, "blockers": blockers, "bonus_points": bonus, "bonus_terms": terms}


def ad_text(extract):
    """The parts of an extract the score bonus looks at."""
    reqs = [f"{r['requirement']} {r['ad_wording']}" for r in extract.get("requirements", [])]
    return "\n".join([extract.get("title", ""), *reqs, *extract.get("tasks", [])])


def compute(sub, st, text=""):
    """The fit score for sub-scores {criterion: 0-5}, with the reasons. Raises ValueError on bad sub-scores."""
    if set(sub) != set(CRITERIA) or not all(isinstance(v, int) and 0 <= v <= 5 for v in sub.values()):
        raise ValueError(f"sub-scores: a whole number from 0 to 5 for each of {', '.join(CRITERIA)}")
    w = st["weights"]
    total = SKILLS_BASE[sub["skills"]]
    reasons = [f"skills {sub['skills']}/5: base {total}"]
    for c in OTHERS:
        off = DEDUCTION[sub[c]] * w[c]
        total -= off
        reasons.append(f"{c} {sub[c]}/5" + (f": -{off:g}" if off else ""))
    found = [t for t in st["bonus_terms"] if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", text, re.I)][:MAX_BONUS_TERMS]
    if found and st["bonus_points"]:
        total += st["bonus_points"] * len(found)
        reasons.append(f"bonus +{st['bonus_points'] * len(found):g} for {', '.join(found)}")
    mismatch = [c for c in st["blockers"] if sub[c] == 0]
    if mismatch:
        total /= 2
        reasons.append(f"halved: hard mismatch ({', '.join(mismatch)})")
    return {"score": max(0, min(100, round(total))), "hard_mismatch": mismatch, "subscores": dict(sub),
            "bonus": found, "reasons": reasons}


def parse(pairs):
    sub = {}
    for p in pairs:
        key, _, value = p.partition("=")
        if key not in CRITERIA or not value.isdigit():
            raise ValueError(f"'{p}': write criterion=N, e.g. skills=4 ({', '.join(CRITERIA)})")
        sub[key] = int(value)
    return sub


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("subscores", nargs="+", metavar="criterion=N")
    ap.add_argument("--ad", help="the job's extract (data/ads/<id>.json)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from config import CFG  # here, not at the top: eval_run.py uses compute() without a workspace
    try:
        st = settings(CFG)
        text = ad_text(json.loads(Path(a.ad).read_text(encoding="utf-8"))) if a.ad else ""
        result = compute(parse(a.subscores), st, text)
    except (ValueError, OSError, json.JSONDecodeError, KeyError) as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        mismatch = ", ".join(result["hard_mismatch"]) or "none"
        print(f"score {result['score']}  hard mismatch: {mismatch}\n  " + "; ".join(result["reasons"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
