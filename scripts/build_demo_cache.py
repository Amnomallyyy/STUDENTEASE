"""Run the demo flow against a live backend so the LLM answers for the demo CV get recorded for offline replay.

Start the server in RECORD mode first (real provider keys in .env), then run this script:

    LLM_CACHE_PATH=demo/cached_responses.json LLM_CACHE_RECORD=1 uvicorn backend.main:app --port 8000
    python scripts/build_demo_cache.py

    # PowerShell
    $env:LLM_CACHE_PATH="demo/cached_responses.json"; $env:LLM_CACHE_RECORD="1"; uvicorn backend.main:app --port 8000

While LLM_CACHE_RECORD=1 the adapter writes every complete_json() answer into the "llm" section of
demo/cached_responses.json, keyed by sha256(schema + prompt). At the venue the server runs with only
LLM_CACHE_PATH set (no RECORD), so the same prompts are answered from the file without a network or an API
key. The prompt embeds the CV text, so rerun this after regenerating the demo PDFs.

Flow (the same one the judges run, see demo/README.md):
    DELETE /profile
    POST   /profile/cv       demo_cv.pdf, target_role=Data Analyst, Karachi coordinates
    GET    /career/roadmap
    POST   /analyzer/run     github_username + linkedin_export.pdf

Commit the updated demo/cached_responses.json afterwards.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
KARACHI = {"lat": 24.8607, "lng": 67.0011, "city": "Karachi"}
TARGET_ROLE = "Data Analyst"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252, which cannot print the LLM's punctuation
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000", help="backend URL (default: http://localhost:8000)")
    parser.add_argument(
        "--github-username",
        default=(DEMO / "github_username.txt").read_text(encoding="utf-8").strip(),
        help="GitHub username for the analyzer (default: demo/github_username.txt)",
    )
    parser.add_argument("--timeout", type=float, default=180, help="seconds per request (LLM calls can be slow)")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    s = requests.Session()

    health = s.get(f"{base}/health", timeout=10)
    health.raise_for_status()
    print("health:", health.json())

    print("DELETE /profile ->", s.delete(f"{base}/profile", timeout=10).status_code)

    with (DEMO / "demo_cv.pdf").open("rb") as f:
        r = s.post(
            f"{base}/profile/cv",
            files={"file": ("demo_cv.pdf", f, "application/pdf")},
            data={"target_role": TARGET_ROLE, "mode": "student", **{k: str(v) for k, v in KARACHI.items()}},
            timeout=args.timeout,
        )
    _check(r, "POST /profile/cv")
    profile = r.json()
    print(f"  skills: {[sk['name'] for sk in profile['skills']]}")
    print(f"  projects: {[p['name'] for p in profile['projects']]}")
    if profile.get("gap"):
        print(f"  match vs {profile['target_role']}: {profile['gap']['match_pct']}%  missing {[m['name'] for m in profile['gap']['missing']]}")
        print(f"  jobs nearby: {len(profile['jobs_nearby'])}")
        for g in profile["market_gaps"][:3]:
            print(f"  market gap: {g['jobs_requiring']} of {g['jobs_total']} jobs ask for {g['skill']}")
    else:
        print("  (no gap computed: is data/roles.json present and the role name right?)")

    r = s.get(f"{base}/career/roadmap", timeout=args.timeout)
    _check(r, "GET /career/roadmap")
    for week in r.json()["weeks"]:
        print(f"  week {week['week']}: {week['focus']} ({len(week['tasks'])} tasks)")

    with (DEMO / "linkedin_export.pdf").open("rb") as f:
        r = s.post(
            f"{base}/analyzer/run",
            files={"linkedin_export": ("linkedin_export.pdf", f, "application/pdf")},
            data={"github_username": args.github_username},
            timeout=args.timeout,
        )
    _check(r, "POST /analyzer/run")
    report = r.json()
    print(f"  integrity score: {report.get('integrity_score')}")
    print(f"  anomalies ({len(report['anomalies'])}):")
    for a in report["anomalies"]:
        print(f"    [{a['kind']}] {a['claim']} -> {a.get('suggested_fix', '')}")

    print("\nDone. If the server ran with LLM_CACHE_RECORD=1, demo/cached_responses.json now holds the LLM answers; commit it.")
    return 0


def _check(response: requests.Response, label: str) -> None:
    print(f"{label} -> {response.status_code}")
    if response.status_code >= 400:
        print(f"  {response.text[:500]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
