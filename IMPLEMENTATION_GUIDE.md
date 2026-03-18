# Implementation Guide
## Evaluating AI-Generated Unit Tests Using Mutation Coverage

**Author:** Reza  
**Last Updated:** March 2026

---

## How to Use This Guide

Read top to bottom. Every section maps to one execution phase.
Do not skip phases. Each phase depends on the previous one completing cleanly.
Run `smoke_test.py` once at the very start — before cloning anything.

---

## Mac Terminal Setup — Do This First

Before anything else, open Terminal on your Mac and run these commands in order.
This sets up your shell environment correctly for the entire project.

### 1. Verify Python version
```bash
python3 --version
# Must be 3.9 or higher
# If missing: install from https://www.python.org/downloads/
```

### 2. Verify Git is installed
```bash
git --version
# If missing, macOS will prompt you to install Xcode Command Line Tools — accept it
```

### 3. Verify pip is available
```bash
pip3 --version
```

### 4. Navigate to your repo
```bash
cd ~/path/to/mutation-testing-ai-vs-human-tests
# Example: cd ~/Documents/mutation-testing-ai-vs-human-tests
pwd
# Output must end with: mutation-testing-ai-vs-human-tests
# STAY IN THIS DIRECTORY for the entire session unless a command explicitly says cd
```

### 5. Create and activate virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

You will see `(.venv)` appear at the start of your terminal prompt:
```
(.venv) reza@MacBook mutation-testing-ai-vs-human-tests %
```

> **Every time you open a new terminal tab or window, you must run `source .venv/bin/activate` again before running any script. Without this, Python will use the wrong interpreter and packages.**

### 6. Install pipeline dependencies
```bash
pip install -r requirements.txt
```

Verify mutmut installed correctly:
```bash
mutmut --version
# Expected: mutmut version 2.4.4
# If you see a different version: pip install mutmut==2.4.4 --force-reinstall
```

### 7. Set your Groq API key
```bash
export GROQ_API_KEY="paste_your_key_here"
echo $GROQ_API_KEY
# Must print your key — not blank
```

> **This export only lasts for the current terminal session.** If you close Terminal and reopen it, you must run this line again. To avoid repeating this, add it to your shell profile:
```bash
echo 'export GROQ_API_KEY="paste_your_key_here"' >> ~/.zshrc
source ~/.zshrc
```

### 8. Prevent Mac from sleeping during long mutmut runs
```bash
# Install caffeinate alias — built into macOS, no install needed
# Run this before every mutmut run to prevent sleep:
caffeinate -i &
# This keeps the Mac awake. Kill it after mutmut finishes:
kill %1
```

### 9. Useful terminal commands to keep open during execution
```bash
# Check disk space — mutmut caches can be 50-200MB each
df -h .

# Monitor CPU during mutmut runs
top -o cpu

# Check a background job is still running
jobs -l

# Kill a stuck background job
kill %1    # kills job number 1
# or
killall mutmut
```

### 10. Run smoke tests — stop if anything fails
```bash
python3 scripts/smoke_test.py
# All checks must show ✅ PASS
# Fix any ❌ FAIL before proceeding
```

---

## Runtime Warning — Read Before Starting

Mutmut is slow. On a MacBook A1708 (dual-core i5, 8GB RAM) expect:

| Project | Human run | AI run | Total |
|---|---|---|---|
| schedule | 20–40 min | 20–40 min | ~1 hr |
| boltons | 30–60 min | 30–60 min | ~1.5 hr |
| jmespath | 25–50 min | 25–50 min | ~1.5 hr |
| **Grand total** | | | **~4 hrs** |

**Recommended strategy:**
- Morning: run schedule dry run end-to-end (~1 hr). Confirms pipeline works.
- Afternoon: start boltons human run, let it run while you write the paper
- Evening: extract boltons scores, start jmespath human run overnight
- Next morning: extract jmespath, run all three AI test runs back to back

**Run mutmut in background so terminal closing does not kill it:**
```bash
nohup mutmut run --parallel > mutmut_run.log 2>&1 &
```

**Watch progress in a second terminal tab:**
```bash
tail -f projects/schedule/mutmut_run.log
```

**Check kill/survive counts without interrupting:**
```bash
# Must be inside the project directory
cd projects/schedule
mutmut results
cd ../..
```

**Check if mutmut is still running:**
```bash
jobs -l
# or
ps aux | grep mutmut
```

---

## File Map

```
scripts/
├── clean_output.py       # helper — no phase, imported by generate_tests.py
├── vet_project.py        # Phase 1 — validate project eligibility
├── record_metadata.py    # Phase 2 — snapshot tool versions and commit hashes
│                         # (Phase 3 = write setup.cfg manually — no script)
├── generate_tests.py     # Phase 4 — call LLM, save tests
├── validate_tests.py     # Phase 5 — confirm AI tests are runnable
├── extract_scores.py     # Phase 6 (human) & Phase 7 (AI) — read cache, write CSV
└── smoke_test.py         # run before execution day — no API calls needed
```

---

---

# FILE 1 — `scripts/clean_output.py`

## What It Is
A helper module. **Not run directly.** Imported by `generate_tests.py`.

## What It Does
Takes raw LLM response text and strips everything that isn't valid Python test code:
- Markdown code fences (` ```python `, ` ``` `)
- Prose explanations before and after the code
- Stray `python` language tag artifacts

Returns empty string if no `def test_` found — signals generation failure to caller.

## Pseudocode
```
FUNCTION clean_generated_tests(raw_output):
    STRIP ```python fences
    STRIP ``` fences
    STRIP leading "python\n" artifact
    FIND first line that looks like real code:
        starts with: import / from / def test_ / """ / class Test
    SLICE from that line to end
    IF "def test_" not in result:
        RETURN ""    ← caller retries or discards
    RETURN cleaned code
```

## Actual Code
```python
# scripts/clean_output.py
import re

def clean_generated_tests(raw_output: str) -> str:
    raw_output = re.sub(r"```python\n?", "", raw_output)
    raw_output = re.sub(r"```\n?", "", raw_output)
    raw_output = re.sub(r"^python\n", "", raw_output.lstrip())

    lines = raw_output.split("\n")
    start_index = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            stripped.startswith("import ")
            or stripped.startswith("from ")
            or stripped.startswith("def test_")
            or stripped.startswith('"""')
            or stripped.startswith("class Test")
        ):
            start_index = i
            break

    cleaned = "\n".join(lines[start_index:]).strip()

    if "def test_" not in cleaned:
        return ""

    return cleaned
```

## Expected Behaviour
```
Input:  "Sure! Here are your tests:\n```python\nimport pytest\n\ndef test_add():\n    assert 1+1==2\n```"
Output: "import pytest\n\ndef test_add():\n    assert 1+1==2"

Input:  "I cannot generate tests for this module."
Output: ""
```

---

---

# FILE 2 — `scripts/vet_project.py`

## What It Is
Phase 1 script. Run once per cloned project.

## What It Does
- Runs `pytest --collect-only` to confirm pytest compatibility
- Walks all `.py` files
- Counts non-comment, non-blank LOC
- Reports all modules in 200–600 LOC range

## Pseudocode
```
ACCEPT project_dir from args
IF not a directory: EXIT with error

RUN pytest --collect-only in project_dir using sys.executable
PRINT OK or FAILED

WALK all .py files:
    SKIP: hidden dirs, __pycache__, test_ files, conftest.py
    COUNT non-blank non-comment lines
    IF 200 <= LOC <= 600: add to candidates

PRINT candidates sorted by LOC
IF none found: WARN
```

## Actual Code
```python
# scripts/vet_project.py
import subprocess
import os
import sys


def count_loc(filepath):
    with open(filepath, encoding="utf-8", errors="ignore") as f:
        lines = [
            l for l in f.readlines()
            if l.strip() and not l.strip().startswith("#")
        ]
    return len(lines)


def find_testable_modules(src_dir, min_loc=200, max_loc=600):
    candidates = []
    for root, _, files in os.walk(src_dir):
        if any(part.startswith(".") or part in ("__pycache__", "node_modules")
               for part in root.split(os.sep)):
            continue
        for f in files:
            if f.endswith(".py") and not f.startswith("test_") and f != "conftest.py":
                path = os.path.join(root, f)
                try:
                    loc = count_loc(path)
                    if min_loc <= loc <= max_loc:
                        candidates.append((path, loc))
                except Exception:
                    pass
    return sorted(candidates, key=lambda x: x[1])


if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    abs_dir = os.path.abspath(project_dir)

    if not os.path.isdir(abs_dir):
        print(f"ERROR: Directory not found: {abs_dir}")
        sys.exit(1)

    print(f"Vetting: {abs_dir}\n")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True, text=True, cwd=abs_dir,
    )
    pytest_ok = result.returncode == 0
    print(f"Pytest collection: {'OK' if pytest_ok else 'FAILED'}")
    if not pytest_ok:
        print(result.stdout[-800:])
        print(result.stderr[-400:])

    candidates = find_testable_modules(abs_dir)
    print(f"\nCandidate modules in 200-600 LOC range ({len(candidates)} found):")
    for path, loc in candidates:
        rel = os.path.relpath(path, abs_dir)
        print(f"  {rel}: {loc} LOC")

    if len(candidates) == 0:
        print("\nWARNING: No viable modules found.")
    elif len(candidates) < 2:
        print("\nWARNING: Fewer than 2 viable modules found.")
```

## Expected Output
```
Vetting: /path/to/projects/schedule

Pytest collection: OK

Candidate modules in 200-600 LOC range (1 found):
  schedule/__init__.py: 312 LOC
```

### If pytest FAILED:
```
Pytest collection: FAILED
ModuleNotFoundError: No module named 'schedule'
```
**Fix:** `pip install -e projects/schedule` — editable install missing.

---

---

# FILE 3 — `scripts/record_metadata.py`

## What It Is
Phase 2 script. Run once after cloning all three projects, before any mutmut run.

## What It Does
- Records exact git commit hash of each cloned repo
- Records Python, mutmut, pytest versions from the active venv
- Records LLM model name and input strategy
- Writes `results/metadata.json`

## Pseudocode
```
FOR each project in [schedule, boltons, jmespath]:
    IF directory exists:
        RUN git rev-parse HEAD → commit hash
        RUN git remote get-url origin → remote URL
    ELSE:
        RECORD "NOT_CLONED" — print warning

RUN sys.executable -m mutmut --version
RUN sys.executable -m pytest --version
BUILD metadata dict
WRITE to results/metadata.json
```

## Actual Code
```python
# scripts/record_metadata.py
import subprocess, json, datetime, sys, os

REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(REPO_ROOT, "results")

PROJECT_DIRS = {
    "schedule": os.path.join(REPO_ROOT, "projects", "schedule"),
    "boltons":  os.path.join(REPO_ROOT, "projects", "boltons"),
    "jmespath": os.path.join(REPO_ROOT, "projects", "jmespath.py"),
}


def get_version(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.stdout.strip().split("\n")[0]
    except Exception:
        return "unknown"


def get_commit_hash(project_path):
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"],
            cwd=project_path, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_remote_url(project_path):
    try:
        r = subprocess.run(["git", "remote", "get-url", "origin"],
            cwd=project_path, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    projects_meta = {}
    for name, path in PROJECT_DIRS.items():
        if not os.path.isdir(path):
            print(f"WARNING: {name} not cloned yet: {path}")
            projects_meta[name] = {"path": path,
                "commit_hash": "NOT_CLONED", "remote_url": "NOT_CLONED"}
        else:
            projects_meta[name] = {"path": path,
                "commit_hash": get_commit_hash(path),
                "remote_url":  get_remote_url(path)}

    metadata = {
        "date":              datetime.datetime.now().isoformat(),
        "python_version":    sys.version,
        "python_executable": sys.executable,
        "mutmut_version":    get_version([sys.executable, "-m", "mutmut", "--version"]),
        "pytest_version":    get_version([sys.executable, "-m", "pytest", "--version"]),
        "llm_provider":      "Groq",
        "llm_model":         "llama-3.3-70b-versatile",
        "llm_input":         "source_file_only",
        "prompt_version":    "v1_fixed",
        "projects":          projects_meta,
    }

    out = os.path.join(RESULTS_DIR, "metadata.json")
    with open(out, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved: {out}")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
```

## Expected Output
```json
{
  "date": "2026-03-20T09:00:00",
  "mutmut_version": "mutmut version 2.4.4",
  "llm_model": "llama-3.3-70b-versatile",
  "projects": {
    "schedule": { "commit_hash": "82a43db...", ... },
    "boltons":  { "commit_hash": "207651e...", ... },
    "jmespath": { "commit_hash": "cdb9327...", ... }
  }
}
```

### Red flags:
- `commit_hash: "NOT_CLONED"` → run clones first
- `mutmut_version: "unknown"` → venv not active or mutmut not installed

---

---

# FILE 4 — `scripts/generate_tests.py`

## What It Is
Phase 4 script. Run once per module.

## What It Does
- Reads source file
- Sends to Groq LLM with fixed prompt
- Saves raw response to `results/raw_ai_outputs/`
- Cleans with `clean_output.py`
- Writes tests to `ai_tests/`
- Retries once on failure, discards if both fail

## Pseudocode
```
ACCEPT source_path, output_path from args
CHECK GROQ_API_KEY set — exit if missing
READ source file

FOR attempt in [0, 1]:
    CALL Groq API with source_code injected into prompt
    SAVE raw response to results/raw_ai_outputs/
    CLEAN with clean_generated_tests()
    IF cleaned has def test_:
        WRITE to output_path
        RETURN success
    IF attempt 0: wait 1s, retry
    IF attempt 1: discard

REPORT discarded — exit code 1
```

## Actual Code
```python
# scripts/generate_tests.py
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clean_output import clean_generated_tests

from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

MODEL = "llama-3.3-70b-versatile"

PROMPT_TEMPLATE = """You are a Python test engineer writing pytest unit tests.

Module to test:
{source_code}

Requirements:
- Use pytest style (def test_...)
- Each test must have a clear assert statement
- Cover: normal inputs, edge cases, invalid inputs
- Do not use mocks unless absolutely necessary
- Import only from the standard library and pytest
- Return only valid Python code, no explanations."""


def generate_tests_for_module(source_path, output_path, max_retries=1):
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY is not set.")
        sys.exit(1)

    with open(source_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(REPO_ROOT, "results", "raw_ai_outputs")
    os.makedirs(raw_dir, exist_ok=True)

    for attempt in range(max_retries + 1):
        print(f"  Attempt {attempt + 1} for {source_path} ...")
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": "You are an expert Python test engineer."},
                    {"role": "user",   "content": PROMPT_TEMPLATE.format(source_code=source_code)},
                ],
            )
        except Exception as e:
            print(f"  API error: {e}")
            time.sleep(2)
            continue

        raw = response.choices[0].message.content
        raw_name = os.path.basename(source_path).replace(".py", f"_raw_attempt{attempt}.txt")
        with open(os.path.join(raw_dir, raw_name), "w", encoding="utf-8") as f:
            f.write(raw)

        cleaned = clean_generated_tests(raw)
        if cleaned:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(cleaned)
            print(f"  Saved: {output_path}")
            return {"status": "saved", "path": output_path}

        print(f"  No valid tests on attempt {attempt + 1}.", end=" ")
        if attempt < max_retries:
            print("Retrying...")
            time.sleep(1)
        else:
            print("Discarding.")

    print(f"  DISCARDED: {source_path}")
    return {"status": "discarded", "path": None}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/generate_tests.py <source_path> <output_path>")
        sys.exit(1)
    source, output = sys.argv[1], sys.argv[2]
    if not os.path.isfile(source):
        print(f"ERROR: Source file not found: {source}")
        sys.exit(1)
    result = generate_tests_for_module(source, output)
    sys.exit(0 if result["status"] == "saved" else 1)
```

## Expected Output
```
  Attempt 1 for projects/schedule/schedule/__init__.py ...
  Saved: projects/schedule/ai_tests/test_ai_schedule.py
```

### If DISCARDED:
Open `results/raw_ai_outputs/__init___raw_attempt0.txt` and read what the LLM returned.
- If it's a refusal message → check API key
- If it's code without `def test_` → rare prompt failure, re-run once manually

---

---

# FILE 5 — `scripts/validate_tests.py`

## What It Is
Phase 5 script. Run immediately after `generate_tests.py` for each module.

## What It Does
1. Counts `assert` statements — rejects if zero
2. Runs `pytest --collect-only` — rejects on any error
3. Confirms at least one test collected

## Pseudocode
```
ACCEPT test_file_path from args
IF file missing: RETURN invalid

READ file, COUNT "assert" occurrences
IF count == 0: RETURN invalid (hollow)

RUN pytest --collect-only using sys.executable
IF errors OR zero tests: RETURN invalid

RETURN valid with counts
```

## Actual Code
```python
# scripts/validate_tests.py
import subprocess, sys, os, re


def validate_generated_tests(test_file_path):
    if not os.path.isfile(test_file_path):
        return {"valid": False, "test_count": 0, "assertion_count": 0,
                "reason": f"File not found: {test_file_path}", "error_output": None}

    with open(test_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    assertion_count = len(re.findall(r"\bassert\b", content))
    if assertion_count == 0:
        return {"valid": False, "test_count": 0, "assertion_count": 0,
                "reason": "No assert statements found — tests are hollow",
                "error_output": None}

    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file_path,
         "--collect-only", "-q", "--tb=short"],
        capture_output=True, text=True,
    )
    output = result.stdout + result.stderr

    has_error = (
        result.returncode != 0
        or "ERROR" in output
        or "ImportError" in output
        or "SyntaxError" in output
        or "ModuleNotFoundError" in output
    )

    match = re.search(r"(\d+) test[s]? collected", output)
    test_count = int(match.group(1)) if match else 0

    if has_error or test_count == 0:
        return {"valid": False, "test_count": test_count,
                "assertion_count": assertion_count,
                "reason": "pytest collection failed or no tests collected",
                "error_output": output[:600]}

    return {"valid": True, "test_count": test_count,
            "assertion_count": assertion_count,
            "reason": None, "error_output": None}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/validate_tests.py <test_file_path>")
        sys.exit(1)
    r = validate_generated_tests(sys.argv[1])
    status = "VALID" if r["valid"] else "INVALID"
    print(f"{status} | Tests: {r['test_count']} | Assertions: {r['assertion_count']}")
    if not r["valid"]:
        print(f"Reason: {r['reason']}")
        if r["error_output"]:
            print(r["error_output"])
        sys.exit(1)
    sys.exit(0)
```

## Expected Output
```
VALID | Tests: 18 | Assertions: 24
```

### INVALID — ModuleNotFoundError:
```
INVALID | Tests: 0 | Assertions: 12
Reason: pytest collection failed
ModuleNotFoundError: No module named 'schedule'
```
**Fix:** `pip install -e projects/schedule`

### INVALID — hollow tests:
```
INVALID | Tests: 0 | Assertions: 0
Reason: No assert statements found — tests are hollow
```
**Fix:** Re-run `generate_tests.py` — the LLM produced tests with no assertions.

---

---

# FILE 6 — `scripts/extract_scores.py`

## What It Is
Phase 6 (human run) and Phase 7 (AI run) script.
Run immediately after every single mutmut run — before doing anything else.

## What It Does
- Opens `.mutmut-cache` SQLite file
- Queries kill/survive/timeout/suspicious counts
- Calculates mutation score %
- Checks for duplicate row before writing
- Appends one row to `results/results.csv`
- Prints reminder to archive and delete cache

## Pseudocode
```
ACCEPT cache_path, run_type ("human"|"ai"), project from args
VALIDATE inputs — exit on bad values
CHECK results.csv for existing project+run_type — abort if duplicate

OPEN .mutmut-cache as SQLite
VERIFY "mutant" table exists — exit if missing
QUERY status counts
CALCULATE score = killed / total * 100

APPEND to results/results.csv
PRINT score summary
PRINT archive/delete reminder
```

## Actual Code
```python
# scripts/extract_scores.py
import sqlite3, json, csv, sys, os

REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(REPO_ROOT, "results")
RESULTS_CSV = os.path.join(RESULTS_DIR, "results.csv")

CSV_FIELDS = ["project","module","run_type","mutation_score_pct",
              "killed","survived","timeout","suspicious","total"]

MODULE_MAP = {
    "schedule": "schedule/__init__.py",
    "boltons":  "boltons/strutils.py",
    "jmespath": "jmespath/lexer.py",
}


def extract_mutation_score(cache_path):
    if not os.path.isfile(cache_path):
        raise FileNotFoundError(f".mutmut-cache not found: {cache_path}")
    conn = sqlite3.connect(cache_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    if "mutant" not in tables:
        conn.close()
        raise RuntimeError(f"Table 'mutant' not found. Found: {tables}. Check mutmut==2.4.4")
    cursor.execute("SELECT status, COUNT(*) FROM mutant GROUP BY status")
    results = dict(cursor.fetchall())
    conn.close()
    killed     = results.get("Killed", 0)
    survived   = results.get("Survived", 0)
    timeout    = results.get("Timeout", 0)
    suspicious = results.get("Suspicious", 0)
    total      = killed + survived + timeout + suspicious
    score      = round((killed / total * 100), 2) if total > 0 else 0.0
    return {"killed": killed, "survived": survived, "timeout": timeout,
            "suspicious": suspicious, "total": total, "mutation_score_pct": score}


def check_duplicate(project, run_type):
    if not os.path.isfile(RESULTS_CSV):
        return False
    with open(RESULTS_CSV, "r", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("project") == project and row.get("run_type") == run_type:
                return True
    return False


def append_to_csv(project, run_type, scores):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_header = not os.path.isfile(RESULTS_CSV)
    with open(RESULTS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "project": project, "module": MODULE_MAP.get(project, "unknown"),
            "run_type": run_type, "mutation_score_pct": scores["mutation_score_pct"],
            "killed": scores["killed"], "survived": scores["survived"],
            "timeout": scores["timeout"], "suspicious": scores["suspicious"],
            "total": scores["total"],
        })
    print(f"Appended to {RESULTS_CSV}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 scripts/extract_scores.py <cache_path> <run_type> <project>")
        print("  run_type: human | ai")
        print("  project:  schedule | boltons | jmespath")
        sys.exit(1)

    cache_path, run_type, project = sys.argv[1], sys.argv[2], sys.argv[3]

    if run_type not in ("human", "ai"):
        print(f"ERROR: run_type must be 'human' or 'ai', got: '{run_type}'")
        sys.exit(1)

    if project not in MODULE_MAP:
        print(f"ERROR: unknown project '{project}'. Known: {list(MODULE_MAP.keys())}")
        sys.exit(1)

    if check_duplicate(project, run_type):
        print(f"WARNING: {project}/{run_type} already in results.csv.")
        print("Delete that row manually before re-running. Aborting.")
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
```

## Expected Output
```
Project:  schedule
Module:   schedule/__init__.py
Run type: human
Score:    74.5%
Killed:   149 / 200
Appended to /path/to/results/results.csv

REMINDER: Archive and delete projects/schedule/.mutmut-cache before the next mutmut run.
```

### Score is 0% or near-zero:
Two possible causes:
1. **Editable install missing** — mutations ran but tests imported from pip. Redo with `pip install -e`.
2. **Test suite errored out on every mutant** — check if the human tests actually pass first with `pytest tests/` inside the project dir.

---

---

# Execution Day — Full Command Sequence

## Step 0 — Every time you open Terminal
```bash
cd ~/path/to/mutation-testing-ai-vs-human-tests
source .venv/bin/activate
export GROQ_API_KEY="your_key_here"
echo $GROQ_API_KEY   # must not be blank
python3 scripts/smoke_test.py  # all must pass
```

## Step 1 — Clone target projects
```bash
git clone https://github.com/dbader/schedule projects/schedule
git clone https://github.com/mahmoud/boltons projects/boltons
git clone --branch develop https://github.com/jmespath/jmespath.py projects/jmespath.py
```

## Step 2 — Install target projects in editable mode

> **Critical — do not skip.** Without editable install, Python imports from
> pip's site-packages, not the cloned source. Mutmut mutates the clone but
> the tests never see the mutations. All scores will be wrong.

```bash
pip install -e projects/schedule
pip install -e projects/boltons
pip install -e projects/jmespath.py
```

Also install dev dependencies so human test suites run cleanly:
```bash
pip install -r projects/schedule/requirements-dev.txt   2>/dev/null || true
pip install -r projects/boltons/requirements-test.txt   2>/dev/null || true
pip install pytest-cov 2>/dev/null || true
```

## Step 3 — Record metadata (run before any mutmut)
```bash
python3 scripts/record_metadata.py
# Open results/metadata.json and verify:
# - commit_hash values are real hashes (not "NOT_CLONED" or "unknown")
# - mutmut_version is "mutmut version 2.4.4"
```

## Step 4 — Vet all three projects
```bash
python3 scripts/vet_project.py projects/schedule
python3 scripts/vet_project.py projects/boltons
python3 scripts/vet_project.py projects/jmespath.py
# All three must show: Pytest collection: OK
# Confirm target modules appear in 200-600 LOC output
```

## Step 5 — Write setup.cfg per project

> **Use append (`>>`) not overwrite (`>`).** boltons and jmespath ship with
> their own setup.cfg — overwriting destroys their config.

```bash
# Backup originals first
cp projects/boltons/setup.cfg   projects/boltons/setup.cfg.bak
cp projects/jmespath.py/setup.cfg projects/jmespath.py/setup.cfg.bak

# schedule — no existing setup.cfg, safe to create
cat > projects/schedule/setup.cfg << 'EOF'
[mutmut]
paths_to_mutate = schedule/
runner = python3 -m pytest test_schedule.py
tests_dir = .
dict_synonyms =
EOF

# boltons — append to existing file
cat >> projects/boltons/setup.cfg << 'EOF'

[mutmut]
paths_to_mutate = boltons/strutils.py
runner = python3 -m pytest tests/
tests_dir = tests/
dict_synonyms =
EOF

# jmespath — append to existing file
cat >> projects/jmespath.py/setup.cfg << 'EOF'

[mutmut]
paths_to_mutate = jmespath/lexer.py
runner = python3 -m pytest tests/
tests_dir = tests/
dict_synonyms =
EOF

# Verify all three have [mutmut] section
grep -l "\[mutmut\]" projects/schedule/setup.cfg \
                     projects/boltons/setup.cfg \
                     projects/jmespath.py/setup.cfg
# Should print all three paths
```

## Step 6 — DRY RUN — Schedule only

Run this complete block before touching boltons or jmespath.
If this doesn't produce two rows in results.csv — stop and debug.

```bash
# Generate AI tests
python3 scripts/generate_tests.py \
  projects/schedule/schedule/__init__.py \
  projects/schedule/ai_tests/test_ai_schedule.py

# Validate
python3 scripts/validate_tests.py \
  projects/schedule/ai_tests/test_ai_schedule.py
# Must print VALID — if INVALID, stop and read the error

# Keep Mac awake during mutmut runs
caffeinate -i &
CAFFEINATE_PID=$!

# Human mutmut run — background with log
cd projects/schedule
nohup mutmut run --parallel > mutmut_human.log 2>&1 &
MUTMUT_PID=$!
echo "mutmut PID: $MUTMUT_PID"
tail -f mutmut_human.log
# When log shows completion, press Ctrl+C to stop tail

# Confirm mutmut actually finished before extracting
wait $MUTMUT_PID
echo "mutmut finished"
cd ../..

# Extract, archive, delete cache
python3 scripts/extract_scores.py \
  projects/schedule/.mutmut-cache human schedule
cp projects/schedule/.mutmut-cache results/schedule_human.mutmut-cache
rm projects/schedule/.mutmut-cache

# AI mutmut run
cd projects/schedule
nohup mutmut run \
  --paths-to-mutate schedule/ \
  --runner "python3 -m pytest ai_tests/" \
  --parallel > mutmut_ai.log 2>&1 &
MUTMUT_PID=$!
tail -f mutmut_ai.log
wait $MUTMUT_PID
echo "mutmut finished"
cd ../..

python3 scripts/extract_scores.py \
  projects/schedule/.mutmut-cache ai schedule
cp projects/schedule/.mutmut-cache results/schedule_ai.mutmut-cache
rm projects/schedule/.mutmut-cache

# Stop caffeinate
kill $CAFFEINATE_PID
```

**Verify dry run succeeded:**
```bash
cat results/results.csv
# Must show exactly 2 rows: schedule/human and schedule/ai
# Both must have non-zero total mutants and a real score percentage
```

## Step 7 — Boltons

```bash
python3 scripts/generate_tests.py \
  projects/boltons/boltons/strutils.py \
  projects/boltons/ai_tests/test_ai_strutils.py

python3 scripts/validate_tests.py \
  projects/boltons/ai_tests/test_ai_strutils.py
# Must print VALID

caffeinate -i &
CAFFEINATE_PID=$!

cd projects/boltons
nohup mutmut run --parallel > mutmut_human.log 2>&1 &
MUTMUT_PID=$!
tail -f mutmut_human.log
wait $MUTMUT_PID
cd ../..

python3 scripts/extract_scores.py \
  projects/boltons/.mutmut-cache human boltons
cp projects/boltons/.mutmut-cache results/boltons_human.mutmut-cache
rm projects/boltons/.mutmut-cache

cd projects/boltons
nohup mutmut run \
  --paths-to-mutate boltons/strutils.py \
  --runner "python3 -m pytest ai_tests/" \
  --parallel > mutmut_ai.log 2>&1 &
MUTMUT_PID=$!
tail -f mutmut_ai.log
wait $MUTMUT_PID
cd ../..

python3 scripts/extract_scores.py \
  projects/boltons/.mutmut-cache ai boltons
cp projects/boltons/.mutmut-cache results/boltons_ai.mutmut-cache
rm projects/boltons/.mutmut-cache

kill $CAFFEINATE_PID
```

## Step 8 — Jmespath

```bash
python3 scripts/generate_tests.py \
  projects/jmespath.py/jmespath/lexer.py \
  projects/jmespath.py/ai_tests/test_ai_lexer.py

python3 scripts/validate_tests.py \
  projects/jmespath.py/ai_tests/test_ai_lexer.py
# Must print VALID

caffeinate -i &
CAFFEINATE_PID=$!

cd projects/jmespath.py
nohup mutmut run --parallel > mutmut_human.log 2>&1 &
MUTMUT_PID=$!
tail -f mutmut_human.log
wait $MUTMUT_PID
cd ../..

python3 scripts/extract_scores.py \
  projects/jmespath.py/.mutmut-cache human jmespath
cp projects/jmespath.py/.mutmut-cache results/jmespath_human.mutmut-cache
rm projects/jmespath.py/.mutmut-cache

cd projects/jmespath.py
nohup mutmut run \
  --paths-to-mutate jmespath/lexer.py \
  --runner "python3 -m pytest ai_tests/" \
  --parallel > mutmut_ai.log 2>&1 &
MUTMUT_PID=$!
tail -f mutmut_ai.log
wait $MUTMUT_PID
cd ../..

python3 scripts/extract_scores.py \
  projects/jmespath.py/.mutmut-cache ai jmespath
cp projects/jmespath.py/.mutmut-cache results/jmespath_ai.mutmut-cache
rm projects/jmespath.py/.mutmut-cache

kill $CAFFEINATE_PID
```

## Step 9 — Verify final results
```bash
cat results/results.csv
# Must show 6 rows total:
# schedule/human, schedule/ai
# boltons/human,  boltons/ai
# jmespath/human, jmespath/ai
# All rows must have non-zero total and a real score
```

## Step 10 — Commit everything
```bash
git add results/results.csv
git add results/metadata.json
git add results/*.mutmut-cache
git add projects/schedule/ai_tests/
git add projects/boltons/ai_tests/
git add projects/jmespath.py/ai_tests/
git add results/raw_ai_outputs/
git commit -m "add all results, AI tests, metadata"
git push
```

---

# Runtime Troubleshooting

**mutmut produces 0 mutants:**
`paths_to_mutate` path is wrong in setup.cfg. Verify it relative to project root:
```bash
ls projects/schedule/schedule/   # must exist
```

**Score is 0.0% (all survived):**
Two causes — check both:
```bash
# 1. Confirm editable install is active
python3 -c "import schedule; print(schedule.__file__)"
# Must print path inside projects/schedule/, NOT inside .venv/lib/

# 2. Confirm human tests actually pass before mutation
cd projects/schedule
python3 -m pytest test_schedule.py -v
cd ../..
```

**mutmut interrupted mid-run:**
Do not delete the cache. Resume from same directory:
```bash
cd projects/schedule
mutmut run --parallel   # resumes from checkpoint
```

**Two mutmut processes running at once in same directory:**
This corrupts the cache. Kill one immediately:
```bash
jobs -l           # find job numbers
kill %2           # kill the second one
```
> Note: Running mutmut in two **different** project directories simultaneously is fine — they have separate caches.

**Mac goes to sleep and kills background job:**
Use `caffeinate -i &` before every run. Check it's running:
```bash
jobs -l
```

**Terminal closed and lost background job:**
Check if it's still running:
```bash
ps aux | grep mutmut
```
If still running, the cache is still being written. Wait for it to finish before extracting.
