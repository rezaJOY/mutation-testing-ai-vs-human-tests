# scripts/extract_scores.py
"""
Phase 6 & 7 — Extract mutation score from .mutmut-cache and append to results.csv.
Usage: python3 scripts/extract_scores.py <cache_path> <run_type> <project>
  run_type: human | ai
  project:  schedule | boltons | jmespath

Example:
  python3 scripts/extract_scores.py projects/schedule/.mutmut-cache human schedule

IMPORTANT: Run this immediately after each mutmut run.
           Archive and delete .mutmut-cache before the next run (see README).
           Always run from the repo root.
"""
import sqlite3
import json
import csv
import sys
import os

# Anchor all paths to repo root regardless of where script is called from
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(REPO_ROOT, "results")
RESULTS_CSV = os.path.join(RESULTS_DIR, "results.csv")

CSV_FIELDS = [
    "project",
    "module",
    "run_type",
    "mutation_score_pct",
    "killed",
    "survived",
    "timeout",
    "suspicious",
    "total",
]

MODULE_MAP = {
    "schedule": "schedule/__init__.py",
    "boltons": "boltons/strutils.py",
    "jmespath": "jmespath/lexer.py",
}


def extract_mutation_score(cache_path: str) -> dict:
    if not os.path.isfile(cache_path):
        raise FileNotFoundError(f".mutmut-cache not found at: {cache_path}")

    conn = sqlite3.connect(cache_path)
    cursor = conn.cursor()

    # Verify schema — catches wrong mutmut version or corrupt cache
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    if "mutant" not in tables:
        conn.close()
        raise RuntimeError(
            f"Expected table 'mutant' not found in cache. Found: {tables}.\n"
            "Check mutmut version — must be 2.4.4"
        )

    cursor.execute("SELECT status, COUNT(*) FROM mutant GROUP BY status")
    results = dict(cursor.fetchall())
    conn.close()

    killed     = results.get("Killed", 0)
    survived   = results.get("Survived", 0)
    timeout    = results.get("Timeout", 0)
    suspicious = results.get("Suspicious", 0)
    total      = killed + survived + timeout + suspicious
    score      = round((killed / total * 100), 2) if total > 0 else 0.0

    return {
        "killed": killed,
        "survived": survived,
        "timeout": timeout,
        "suspicious": suspicious,
        "total": total,
        "mutation_score_pct": score,
    }


def check_duplicate(project: str, run_type: str) -> bool:
    """Return True if this project+run_type combo already exists in results.csv."""
    if not os.path.isfile(RESULTS_CSV):
        return False
    with open(RESULTS_CSV, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("project") == project and row.get("run_type") == run_type:
                return True
    return False


def append_to_csv(project: str, run_type: str, scores: dict):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_header = not os.path.isfile(RESULTS_CSV)

    with open(RESULTS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "project":            project,
            "module":             MODULE_MAP.get(project, "unknown"),
            "run_type":           run_type,
            "mutation_score_pct": scores["mutation_score_pct"],
            "killed":             scores["killed"],
            "survived":           scores["survived"],
            "timeout":            scores["timeout"],
            "suspicious":         scores["suspicious"],
            "total":              scores["total"],
        })
    print(f"Appended to {RESULTS_CSV}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 scripts/extract_scores.py <cache_path> <run_type> <project>")
        print("  run_type: human | ai")
        print("  project:  schedule | boltons | jmespath")
        sys.exit(1)

    cache_path = sys.argv[1]
    run_type   = sys.argv[2]
    project    = sys.argv[3]

    if run_type not in ("human", "ai"):
        print(f"ERROR: run_type must be 'human' or 'ai', got: '{run_type}'")
        sys.exit(1)

    if project not in MODULE_MAP:
        print(f"ERROR: unknown project '{project}'. Known: {list(MODULE_MAP.keys())}")
        sys.exit(1)

    # Duplicate guard — prevents silent double-writes on re-runs
    if check_duplicate(project, run_type):
        print(f"WARNING: {project}/{run_type} already exists in results.csv.")
        print("If you want to overwrite, delete that row manually first.")
        print("Aborting to prevent duplicate data.")
        sys.exit(1)

    try:
        scores = extract_mutation_score(cache_path)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"\nProject:  {project}")
    print(f"Module:   {MODULE_MAP[project]}")
    print(f"Run type: {run_type}")
    print(f"Score:    {scores['mutation_score_pct']}%")
    print(f"Killed:   {scores['killed']} / {scores['total']}")
    print(json.dumps(scores, indent=2))

    append_to_csv(project, run_type, scores)

    print(f"\nREMINDER: Archive and delete {cache_path} before the next mutmut run.")
