# scripts/record_metadata.py
"""
Phase 2 — Snapshot tool versions and project commit hashes.
Run once after cloning all three projects and before any mutmut run.
Output: results/metadata.json

Usage: python3 scripts/record_metadata.py
"""
import subprocess
import json
import datetime
import sys
import os

# Anchor all paths to repo root regardless of where script is called from
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(REPO_ROOT, "results")

# Project directories relative to repo root
PROJECT_DIRS = {
    "schedule": os.path.join(REPO_ROOT, "projects", "schedule"),
    "boltons":  os.path.join(REPO_ROOT, "projects", "boltons"),
    "jmespath": os.path.join(REPO_ROOT, "projects", "jmespath.py"),
}


def get_version(cmd: list) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.stdout.strip().split("\n")[0]
    except Exception:
        return "unknown"


def get_commit_hash(project_path: str) -> str:
    """Get the HEAD commit hash of a cloned repo for reproducibility."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_remote_url(project_path: str) -> str:
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    projects_meta = {}
    for name, path in PROJECT_DIRS.items():
        if not os.path.isdir(path):
            print(f"WARNING: project directory not found: {path}")
            print(f"  Run 'git clone ...' for '{name}' before recording metadata.")
            projects_meta[name] = {
                "path": path,
                "commit_hash": "NOT_CLONED",
                "remote_url": "NOT_CLONED",
            }
        else:
            projects_meta[name] = {
                "path": path,
                "commit_hash": get_commit_hash(path),
                "remote_url": get_remote_url(path),
            }

    metadata = {
        "date":             datetime.datetime.now().isoformat(),
        "python_version":   sys.version,
        "python_executable": sys.executable,
        # Use sys.executable to ensure we query the active venv's mutmut/pytest
        "mutmut_version":  get_version([sys.executable, "-m", "mutmut", "--version"]),
        "pytest_version":  get_version([sys.executable, "-m", "pytest", "--version"]),
        "llm_provider":    "Groq",
        "llm_model":       "llama-3.3-70b-versatile",  # hard-coded — update if model changes
        "llm_input":       "source_file_only",
        "prompt_version":  "v1_fixed",
        "projects":        projects_meta,
    }

    output_path = os.path.join(RESULTS_DIR, "metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved: {output_path}")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
