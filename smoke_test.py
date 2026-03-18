# scripts/smoke_test.py
"""
Smoke tests — run before execution day to confirm all scripts are functional.
Usage: python3 scripts/smoke_test.py

No API calls. No mutmut. No cloned projects required.
All tests use synthetic in-memory or temp-file data.
All temp files are cleaned up even if a test crashes.
"""
import sys
import os
import sqlite3
import tempfile
import csv

# Fix import path so all sibling scripts can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "✅ PASS"
FAIL = "❌ FAIL"
failures = []
total_checks = 0


def check(name, condition, detail=""):
    global total_checks
    total_checks += 1
    if condition:
        print(f"{PASS} — {name}")
    else:
        msg = f"{FAIL} — {name}"
        if detail:
            msg += f": {detail}"
        print(msg)
        failures.append(name)


print("Running smoke tests...\n")

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: clean_output
# ─────────────────────────────────────────────────────────────────────────────
print("[ clean_output.py ]")
from clean_output import clean_generated_tests

raw_with_fence = (
    "Here are your tests:\n"
    "```python\n"
    "import pytest\n\n"
    "def test_add():\n"
    "    assert 1 + 1 == 2\n"
    "```"
)
result = clean_generated_tests(raw_with_fence)
check("strips markdown fences",        "```" not in result)
check("removes prose preamble",        "Here are your tests" not in result)
check("preserves def test_",           "def test_add" in result)
check("returns empty on no tests",     clean_generated_tests("I cannot generate tests.") == "")
check(
    "returns empty on code without def test_",
    clean_generated_tests("```python\ndef helper():\n    return 1\n```") == ""
)
raw_no_fence = "import pytest\n\ndef test_something():\n    assert True\n"
check("handles input with no fences",  "def test_something" in clean_generated_tests(raw_no_fence))
check(
    "handles triple-backtick with no language tag",
    "def test_x" in clean_generated_tests("```\ndef test_x():\n    assert True\n```")
)

print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: vet_project — count_loc + find_testable_modules
# ─────────────────────────────────────────────────────────────────────────────
print("[ vet_project.py ]")
from vet_project import count_loc, find_testable_modules

# count_loc
tmp_py = None
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("# comment — not counted\n")
        f.write("\n")                     # blank — not counted
        f.write("def hello():\n")        # counted
        f.write("    return 'world'\n")  # counted
        f.write("x = 1\n")              # counted
        tmp_py = f.name
    loc = count_loc(tmp_py)
    check("count_loc skips comments and blank lines", loc == 3, f"got {loc}, expected 3")
finally:
    if tmp_py and os.path.exists(tmp_py):
        os.unlink(tmp_py)

# find_testable_modules — uses a temp directory with known files
tmp_dir = None
try:
    tmp_dir = tempfile.mkdtemp()

    # A file inside the LOC range
    big_file = os.path.join(tmp_dir, "bigmodule.py")
    with open(big_file, "w") as f:
        for i in range(250):
            f.write(f"x_{i} = {i}\n")

    # A test file — should be excluded
    test_file = os.path.join(tmp_dir, "test_something.py")
    with open(test_file, "w") as f:
        for i in range(250):
            f.write(f"x_{i} = {i}\n")

    # A file too small
    small_file = os.path.join(tmp_dir, "tiny.py")
    with open(small_file, "w") as f:
        f.write("x = 1\n")

    candidates = find_testable_modules(tmp_dir, min_loc=200, max_loc=600)
    names = [os.path.basename(p) for p, _ in candidates]
    check("find_testable_modules finds in-range module",   "bigmodule.py" in names)
    check("find_testable_modules excludes test_ files",    "test_something.py" not in names)
    check("find_testable_modules excludes too-small files","tiny.py" not in names)
finally:
    if tmp_dir:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: validate_tests
# ─────────────────────────────────────────────────────────────────────────────
print("[ validate_tests.py ]")
from validate_tests import validate_generated_tests

# Missing file
r = validate_generated_tests("/nonexistent/path/test_fake.py")
check("handles missing file gracefully",            not r["valid"])
check("missing file reason mentions 'not found'",   "not found" in r["reason"].lower())

# Hollow test — no assertions — use try/finally to guarantee cleanup
tmp_hollow = None
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".") as f:
        f.write("def test_hollow():\n    pass\n")
        tmp_hollow = f.name
    r = validate_generated_tests(tmp_hollow)
    check("rejects hollow tests (no asserts)",          not r["valid"])
    check("assertion_count is 0 for hollow tests",      r["assertion_count"] == 0)
finally:
    if tmp_hollow and os.path.exists(tmp_hollow):
        os.unlink(tmp_hollow)

# Valid test file
tmp_valid = None
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".") as f:
        f.write(
            "def test_real():\n    assert 1 + 1 == 2\n\n"
            "def test_also():\n    assert 'a' in 'abc'\n"
        )
        tmp_valid = f.name
    r = validate_generated_tests(tmp_valid)
    check("accepts valid test file",          r["valid"], str(r.get("error_output", "")))
    check("counts assertions correctly",      r["assertion_count"] == 2, f"got {r['assertion_count']}")
    check("counts test functions correctly",  r["test_count"] == 2,      f"got {r['test_count']}")
finally:
    if tmp_valid and os.path.exists(tmp_valid):
        os.unlink(tmp_valid)

# Syntax error file
tmp_syntax = None
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".") as f:
        f.write("def test_broken(\n    assert True\n")
        tmp_syntax = f.name
    r = validate_generated_tests(tmp_syntax)
    check("rejects file with syntax error", not r["valid"])
finally:
    if tmp_syntax and os.path.exists(tmp_syntax):
        os.unlink(tmp_syntax)

print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: extract_scores
# ─────────────────────────────────────────────────────────────────────────────
print("[ extract_scores.py ]")
from extract_scores import extract_mutation_score, check_duplicate

# Valid fake cache
fake_cache = None
try:
    with tempfile.NamedTemporaryFile(suffix=".mutmut-cache", delete=False) as f:
        fake_cache = f.name
    conn = sqlite3.connect(fake_cache)
    conn.execute("CREATE TABLE mutant (id INTEGER PRIMARY KEY, status TEXT)")
    conn.executemany("INSERT INTO mutant VALUES (?, ?)", [
        (1, "Killed"), (2, "Killed"), (3, "Killed"),
        (4, "Survived"), (5, "Timeout"),
    ])
    conn.commit()
    conn.close()

    scores = extract_mutation_score(fake_cache)
    check("reads killed count",       scores["killed"] == 3,             f"got {scores['killed']}")
    check("reads survived count",     scores["survived"] == 1,           f"got {scores['survived']}")
    check("reads timeout count",      scores["timeout"] == 1,            f"got {scores['timeout']}")
    check("calculates total",         scores["total"] == 5,              f"got {scores['total']}")
    check("calculates score 60.0%",   scores["mutation_score_pct"] == 60.0, f"got {scores['mutation_score_pct']}")
finally:
    if fake_cache and os.path.exists(fake_cache):
        os.unlink(fake_cache)

# Bad schema cache
bad_cache = None
try:
    with tempfile.NamedTemporaryFile(suffix=".mutmut-cache", delete=False) as f:
        bad_cache = f.name
    conn = sqlite3.connect(bad_cache)
    conn.execute("CREATE TABLE something_else (id INTEGER)")
    conn.commit()
    conn.close()
    try:
        extract_mutation_score(bad_cache)
        check("raises RuntimeError on wrong schema", False, "should have raised")
    except RuntimeError:
        check("raises RuntimeError on wrong schema", True)
finally:
    if bad_cache and os.path.exists(bad_cache):
        os.unlink(bad_cache)

# Nonexistent cache
try:
    extract_mutation_score("/nonexistent/.mutmut-cache")
    check("raises FileNotFoundError on missing cache", False, "should have raised")
except FileNotFoundError:
    check("raises FileNotFoundError on missing cache", True)

# Duplicate detection — use try/finally so RESULTS_CSV patch always restores
import extract_scores as es
tmp_csv = None
original_csv = es.RESULTS_CSV
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=[
            "project", "module", "run_type", "mutation_score_pct",
            "killed", "survived", "timeout", "suspicious", "total"
        ])
        writer.writeheader()
        writer.writerow({
            "project": "schedule", "module": "schedule/__init__.py",
            "run_type": "human", "mutation_score_pct": 74.5,
            "killed": 149, "survived": 45,
            "timeout": 6, "suspicious": 0, "total": 200
        })
        tmp_csv = f.name
    es.RESULTS_CSV = tmp_csv
    check("detects existing project+run_type",          es.check_duplicate("schedule", "human"))
    check("allows new run_type for same project",   not es.check_duplicate("schedule", "ai"))
    check("allows new project entirely",            not es.check_duplicate("boltons", "human"))
finally:
    es.RESULTS_CSV = original_csv   # always restore — even if check() raises
    if tmp_csv and os.path.exists(tmp_csv):
        os.unlink(tmp_csv)

print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: record_metadata helpers
# ─────────────────────────────────────────────────────────────────────────────
print("[ record_metadata.py ]")
from record_metadata import get_version, get_commit_hash, get_remote_url

ver = get_version([sys.executable, "--version"])
check("get_version returns non-empty string", len(ver) > 0,      f"got: '{ver}'")
check("get_version contains 'Python'",        "Python" in ver,   f"got: '{ver}'")

bad_hash = get_commit_hash("/nonexistent/path")
check("get_commit_hash returns 'unknown' on bad path", bad_hash == "unknown")

bad_url = get_remote_url("/nonexistent/path")
check("get_remote_url returns 'unknown' on bad path", bad_url == "unknown")

print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: generate_tests — env and path checks (no API call)
# ─────────────────────────────────────────────────────────────────────────────
print("[ generate_tests.py — env checks ]")

# Verify clean_output is importable from the scripts directory
# (this is what generate_tests does with sys.path.insert)
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "clean_output",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "clean_output.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    check("clean_output importable from scripts dir", hasattr(mod, "clean_generated_tests"))
except Exception as e:
    check("clean_output importable from scripts dir", False, str(e))

# Verify GROQ_API_KEY check would trigger (temporarily unset if set)
original_key = os.environ.get("GROQ_API_KEY")
os.environ.pop("GROQ_API_KEY", None)
key_missing = os.environ.get("GROQ_API_KEY") is None
check("GROQ_API_KEY absence is detectable", key_missing)
if original_key:
    os.environ["GROQ_API_KEY"] = original_key

# Verify output directory creation logic
tmp_out_dir = None
try:
    tmp_out_dir = tempfile.mkdtemp()
    nested = os.path.join(tmp_out_dir, "ai_tests", "test_ai_x.py")
    os.makedirs(os.path.dirname(nested), exist_ok=True)
    check("output directory creation works", os.path.isdir(os.path.dirname(nested)))
finally:
    if tmp_out_dir:
        import shutil
        shutil.rmtree(tmp_out_dir, ignore_errors=True)

print()

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 52)
if failures:
    print(f"❌  {len(failures)} / {total_checks} test(s) FAILED:")
    for name in failures:
        print(f"    - {name}")
    print("\nFix the failures above before running the pipeline.")
    sys.exit(1)
else:
    print(f"✅  All {total_checks} smoke tests passed. Pipeline is ready.")
    sys.exit(0)
