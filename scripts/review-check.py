#!/usr/bin/env python3
"""Agent Review Gate — validates review artifacts, change manifests, and ownership.

Run locally::

    python scripts/review-check.py

Run in CI (PR mode)::

    python scripts/review-check.py --pr-mode
    python scripts/review-check.py --ownership-check

Exit codes::

    0  All checks passed
    1  One or more checks failed
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

WORK_DIR = Path("agent_protocol/work")
REQUIRED_REV_SECTIONS = [
    "## Scope Reviewed",
    "## Findings",
    "## Required Fixes",
    "## Verification Reviewed",
    "## Approval Criteria",
    "## Final Decision",
]
REQUIRED_TASK_SECTIONS = [
    "## Shared Understanding",
    "## Intended Changes",
    "## Plan",
    "## Current Status",
]

errors: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)
    print(f"  FAIL: {msg}")


def warn(msg: str) -> None:
    warnings.append(msg)
    print(f"  WARN: {msg}")


def ok(msg: str) -> None:
    print(f"  OK:   {msg}")


def _read_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    try:
        _, front, _ = text.split("---", 2)
    except ValueError:
        return {}
    result: dict[str, Any] = {}
    for line in front.strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            result[key.strip()] = val.strip()
    return result


def check_rev_artifacts() -> int:
    """Validate all REV-* artifacts have required sections."""
    rev_dir = WORK_DIR / "reviews"
    if not rev_dir.exists():
        warn("No reviews/ directory found")
        return 0

    files = list(rev_dir.glob("REV-*.md"))
    if not files:
        warn("No REV-* artifacts found")
        return 0

    checked = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        missing = [sec for sec in REQUIRED_REV_SECTIONS if sec not in text]
        if missing:
            fail(f"{path.name} missing sections: {', '.join(missing)}")
        else:
            ok(f"{path.name} has all required sections")
            checked += 1

        fm = _read_frontmatter(path)
        status = fm.get("status", "")
        if status not in ("requested", "changes_requested", "approved", "closed"):
            fail(f"{path.name} has invalid status: {status!r}")
        else:
            ok(f"{path.name} status={status}")

    return checked


def check_chg_artifacts() -> int:
    """Validate all CHG-* artifacts list changed files."""
    chg_dir = WORK_DIR / "changes"
    if not chg_dir.exists():
        warn("No changes/ directory found")
        return 0

    files = list(chg_dir.glob("CHG-*.md"))
    if not files:
        warn("No CHG-* artifacts found")
        return 0

    checked = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "## Changed Files" not in text and "## Files Changed" not in text:
            fail(f"{path.name} missing '## Changed Files' section")
        else:
            ok(f"{path.name} has Changed Files section")
            checked += 1

        fm = _read_frontmatter(path)
        if not fm.get("related_task"):
            warn(f"{path.name} missing related_task frontmatter")

    return checked


def check_task_artifacts() -> int:
    """Validate all TASK-* artifacts have required sections and valid status."""
    task_dir = WORK_DIR / "tasks"
    if not task_dir.exists():
        warn("No tasks/ directory found")
        return 0

    files = [p for p in task_dir.glob("TASK-*.md") if "TEMPLATE" not in p.name]
    if not files:
        warn("No TASK-* artifacts found")
        return 0

    checked = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        missing = [sec for sec in REQUIRED_TASK_SECTIONS if sec not in text]
        if missing:
            fail(f"{path.name} missing sections: {', '.join(missing)}")
        else:
            ok(f"{path.name} has all required sections")
            checked += 1

        fm = _read_frontmatter(path)
        status = fm.get("status", "")
        valid = ("todo", "in_progress", "blocked", "review", "done")
        if status not in valid:
            fail(f"{path.name} has invalid status: {status!r}")
        else:
            ok(f"{path.name} status={status}")

    return checked


def check_ownership() -> int:
    """Validate ownership.md exists and is parseable."""
    ownership_path = WORK_DIR.parent / "ownership.md"
    if not ownership_path.exists():
        fail("ownership.md not found")
        return 0

    text = ownership_path.read_text(encoding="utf-8")
    if "## Active Ownership" not in text and "## Active File Ownership" not in text:
        warn("ownership.md missing '## Active Ownership' section")
    else:
        ok("ownership.md has Active Ownership section")

    # Rough check for file-owner mappings
    rows = [line for line in text.splitlines() if "|" in line and "TASK-" in line]
    if not rows:
        warn("ownership.md has no TASK-* entries")
    else:
        ok(f"ownership.md has {len(rows)} ownership row(s)")

    return 1


def check_git_changed_files() -> list[str]:
    """Return list of changed files against main."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [line for line in result.stdout.strip().split("\n") if line]
    except subprocess.CalledProcessError:
        # Fallback: check against HEAD~1
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
                check=True,
            )
            return [line for line in result.stdout.strip().split("\n") if line]
        except subprocess.CalledProcessError:
            return []


def check_pr_review_coverage() -> None:
    """In PR mode, ensure changed files have corresponding change/review artifacts."""
    changed = check_git_changed_files()
    if not changed:
        warn("No changed files detected in this PR")
        return

    print(f"\nChanged files ({len(changed)}):")
    for f in changed:
        print(f"  - {f}")

    chg_dir = WORK_DIR / "changes"
    rev_dir = WORK_DIR / "reviews"

    chg_files = list(chg_dir.glob("CHG-*.md")) if chg_dir.exists() else []
    rev_files = list(rev_dir.glob("REV-*.md")) if rev_dir.exists() else []

    chg_text = "\n".join(p.read_text() for p in chg_files)

    uncovered = []
    for f in changed:
        if f.startswith("agent_protocol/"):
            continue  # Skip meta-files
        if f not in chg_text:
            uncovered.append(f)

    if uncovered:
        warn(
            f"{len(uncovered)} changed file(s) not listed in any CHG-* artifact: "
            f"{', '.join(uncovered[:3])}{'...' if len(uncovered) > 3 else ''}"
        )
    else:
        ok("All changed files are covered by a CHG-* artifact")

    if not rev_files:
        warn("No REV-* artifact found for this PR")
    else:
        ok(f"Found {len(rev_files)} REV-* artifact(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Review Gate")
    parser.add_argument("--pr-mode", action="store_true", help="Enable PR-specific checks")
    parser.add_argument("--ownership-check", action="store_true", help="Run ownership validation only")
    args = parser.parse_args()

    print("=" * 60)
    print("Agent Review Gate")
    print("=" * 60)

    if args.ownership_check:
        print("\n--- Ownership Check ---")
        check_ownership()
    else:
        print("\n--- Review Artifacts ---")
        check_rev_artifacts()

        print("\n--- Change Artifacts ---")
        check_chg_artifacts()

        print("\n--- Task Artifacts ---")
        check_task_artifacts()

        print("\n--- Ownership ---")
        check_ownership()

        if args.pr_mode:
            print("\n--- PR Coverage ---")
            check_pr_review_coverage()

    print("\n" + "=" * 60)
    if errors:
        print(f"RESULT: FAILED ({len(errors)} error(s), {len(warnings)} warning(s))")
        return 1
    elif warnings:
        print(f"RESULT: PASSED with warnings ({len(warnings)} warning(s))")
        return 0
    else:
        print("RESULT: PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
