#!/usr/bin/env python3
"""
PR Validation Script for public-api-lists.

Validates that PRs follow contribution guidelines:
- Correct table format (5 columns: API, Description, Auth, HTTPS, CORS)
- Valid Auth values (No, OAuth, apiKey, X-Mashape-Key)
- Valid HTTPS values (Yes, No)
- Valid CORS values (Yes, No, Unknown)
- Alphabetical ordering within sections
- Append-only: no deletions of existing entries (unless labeled as cleanup)
- No duplicate APIs (same name or URL)
- Description doesn't end with punctuation
- Column spacing (one space padding)
- Entries added in correct alphabetical position
"""

import json
import os
import re
import subprocess
import sys

# --- Constants ---

VALID_AUTH = {"No", "OAuth", "`apiKey`", "`OAuth`", "`X-Mashape-Key`", "apiKey", "X-Mashape-Key"}
VALID_HTTPS = {"Yes", "No"}
VALID_CORS = {"Yes", "No", "Unknown"}

# Regex for a valid table entry line
# Matches: | [Name](URL) | Description | Auth | HTTPS | CORS |
TABLE_ENTRY_RE = re.compile(
    r'^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|'  # | [Name](URL) |
    r'\s*(.+?)\s*\|'                         # Description |
    r'\s*(.+?)\s*\|'                         # Auth |
    r'\s*(.+?)\s*\|'                         # HTTPS |
    r'\s*(.+?)\s*\|$'                        # CORS |
)

# Regex for section headers
SECTION_RE = re.compile(r'^### (.+)$')

# Sections to skip (not API categories)
SKIP_SECTIONS = {"Gold Sponsors", "Silver Sponsors", "Bronze Sponsors"}

# Lines to ignore in diff (headers, separators, back-to-index)
SKIP_LINE_RE = re.compile(
    r'^\|.*API.*Description.*Auth.*HTTPS.*CORS.*\|$|'  # table header
    r'^\|[\s:\-]+\|[\s:\-]+\|[\s:\-]+\|[\s:\-]+\|[\s:\-]+\|$|'  # separator
    r'^\*\*\[.*Back to Index.*\]\(#index\)\*\*$|'  # back to index
    r'^$'  # empty lines
)


def get_diff():
    """Get the diff of the PR against the base branch."""
    # Use pre-generated diff file if available (pull_request_target workflow)
    diff_file = os.environ.get("DIFF_FILE", "pr_diff.patch")
    if os.path.exists(diff_file):
        with open(diff_file, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            return content

    base = os.environ.get("GITHUB_BASE_REF", "master")
    head = os.environ.get("GITHUB_HEAD_REF", "HEAD")

    # In GitHub Actions, fetch both refs
    if os.environ.get("GITHUB_ACTIONS"):
        result = subprocess.run(
            ["git", "diff", f"origin/{base}...origin/{head}", "--", "README.md"],
            capture_output=True, text=True
        )
    else:
        result = subprocess.run(
            ["git", "diff", f"{base}...{head}", "--", "README.md"],
            capture_output=True, text=True
        )

    if result.returncode != 0:
        # Fallback: diff against HEAD~1
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "--", "README.md"],
            capture_output=True, text=True
        )

    return result.stdout


def get_full_readme():
    """Read the full README.md to check for duplicates and ordering."""
    readme_path = os.path.join(os.environ.get("GITHUB_WORKSPACE", "."), "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        return f.readlines()


def parse_sections_from_readme(lines):
    """Parse all sections and their entries from the full README."""
    sections = {}
    current_section = None

    for line in lines:
        line = line.rstrip()
        section_match = SECTION_RE.match(line)
        if section_match:
            raw_name = section_match.group(1).strip()
            clean_name = re.sub(
                r'^[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\s]+',
                '', raw_name
            ).strip()
            if clean_name in SKIP_SECTIONS:
                current_section = None
                continue
            current_section = raw_name
            sections[current_section] = []
            continue

        if current_section and TABLE_ENTRY_RE.match(line):
            match = TABLE_ENTRY_RE.match(line)
            name = match.group(1).strip()
            url = match.group(2).strip()
            sections[current_section].append({
                "name": name,
                "url": url,
                "line": line,
            })

    return sections


def parse_diff(diff_text):
    """Parse the unified diff to extract added and removed lines with context."""
    added_lines = []
    removed_lines = []
    current_section = None
    in_readme = False

    for line in diff_text.split("\n"):
        # Track if we're in README.md changes
        if line.startswith("diff --git"):
            in_readme = "README.md" in line
            continue

        if not in_readme:
            continue

        # Track which section we're in from context lines
        raw = line[1:] if line and line[0] in ("+", "-", " ") else line
        section_match = SECTION_RE.match(raw)
        if section_match:
            current_section = section_match.group(1).strip()

        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            added_lines.append({
                "content": content,
                "section": current_section,
            })
        elif line.startswith("-") and not line.startswith("---"):
            content = line[1:]
            removed_lines.append({
                "content": content,
                "section": current_section,
            })

    return added_lines, removed_lines


def extract_api_name(line):
    """Extract the API name from a table entry line for sorting."""
    match = TABLE_ENTRY_RE.match(line)
    if match:
        return match.group(1).strip().lower()
    return None


def extract_api_url(line):
    """Extract the URL from a table entry line."""
    match = TABLE_ENTRY_RE.match(line)
    if match:
        return match.group(2).strip()
    return None


def validate_entry(content, section):
    """Validate a single table entry line. Returns list of error strings."""
    errors = []

    # Skip non-table lines
    if SKIP_LINE_RE.match(content.strip()):
        return errors

    # Skip section headers, back-to-index, and other non-entry lines
    if not content.strip().startswith("|"):
        return errors

    # Must be a table line but might be header/separator
    if "---" in content and "|" in content:
        return errors

    match = TABLE_ENTRY_RE.match(content.strip())
    if not match:
        # It's a table line but doesn't match the entry format
        if content.strip().startswith("|") and content.strip().endswith("|"):
            # Could be a header row or malformed entry
            if "API" in content and "Description" in content:
                return errors  # It's a header row
            errors.append(f"Malformed table entry: `{content.strip()}`")
        return errors

    name = match.group(1).strip()
    url = match.group(2).strip()
    description = match.group(3).strip()
    auth = match.group(4).strip()
    https_val = match.group(5).strip()
    cors = match.group(6).strip()

    # Check Auth value
    if auth not in VALID_AUTH:
        errors.append(
            f"**{name}**: Invalid Auth value `{auth}`. "
            f"Must be one of: No, `apiKey`, `OAuth`, `X-Mashape-Key`"
        )

    # Check HTTPS value
    if https_val not in VALID_HTTPS:
        errors.append(
            f"**{name}**: Invalid HTTPS value `{https_val}`. Must be Yes or No"
        )

    # Check CORS value
    if cors not in VALID_CORS:
        errors.append(
            f"**{name}**: Invalid CORS value `{cors}`. Must be Yes, No, or Unknown"
        )

    # Check description doesn't end with punctuation
    if description and description[-1] in ".!?,;:":
        errors.append(
            f"**{name}**: Description should not end with punctuation (`{description[-1]}`)"
        )

    # Check URL format
    if not url.startswith("http://") and not url.startswith("https://"):
        errors.append(f"**{name}**: URL must start with http:// or https://")

    # Check name is not empty
    if not name:
        errors.append("Entry has an empty API name")

    # Check description is not empty
    if not description:
        errors.append(f"**{name}**: Description is empty")

    return errors


def check_alphabetical_order(sections):
    """Check that entries within each section are alphabetically ordered."""
    errors = []
    for section_name, entries in sections.items():
        names = [e["name"].lower() for e in entries]
        for i in range(len(names) - 1):
            if names[i] > names[i + 1]:
                errors.append(
                    f"**{section_name}**: `{entries[i]['name']}` should come after "
                    f"`{entries[i+1]['name']}` (alphabetical order)"
                )
    return errors


def check_duplicates(sections, added_entries):
    """Check if newly added entries duplicate existing ones.

    Only flags duplicates that involve a newly added entry.
    Pre-existing duplicates (both entries already in the list) are ignored.
    """
    errors = []

    # Build set of newly added names and URLs for filtering
    new_names = set()
    new_urls = set()
    for item in added_entries:
        match = TABLE_ENTRY_RE.match(item["content"].strip())
        if match:
            new_names.add(match.group(1).strip().lower())
            new_urls.add(match.group(2).strip().lower().rstrip("/"))

    # Collect all names and URLs from the full README
    all_names = {}
    all_urls = {}
    for section_name, entries in sections.items():
        for entry in entries:
            lower_name = entry["name"].lower()
            lower_url = entry["url"].lower().rstrip("/")
            if lower_name not in all_names:
                all_names[lower_name] = []
            all_names[lower_name].append(section_name)
            if lower_url not in all_urls:
                all_urls[lower_url] = []
            all_urls[lower_url].append((entry["name"], section_name))

    # Only flag duplicates involving a newly added entry
    for name, secs in all_names.items():
        if len(secs) > 1 and name in new_names:
            errors.append(
                f"Duplicate API name `{name}` found in sections: {', '.join(secs)}"
            )

    for url, entries in all_urls.items():
        if len(entries) > 1 and url in new_urls:
            names_sections = [f"`{n}` in {s}" for n, s in entries]
            errors.append(
                f"Duplicate URL `{url}` found: {', '.join(names_sections)}"
            )

    return errors


def check_deletions(removed_lines):
    """Check if existing entries were removed (append-only enforcement)."""
    errors = []
    deleted_entries = []

    for item in removed_lines:
        content = item["content"].strip()
        match = TABLE_ENTRY_RE.match(content)
        if match:
            name = match.group(1).strip()
            section = item["section"] or "unknown section"
            deleted_entries.append(f"`{name}` from **{section}**")

    if deleted_entries:
        errors.append(
            "This PR removes existing API entries. If this is intentional "
            "(e.g., broken link cleanup), please add the `cleanup` label.\n"
            "Removed entries:\n" + "\n".join(f"  - {e}" for e in deleted_entries)
        )

    return errors


def get_modified_sections(added_lines):
    """Get the set of sections that were modified."""
    sections = set()
    for item in added_lines:
        if item["section"]:
            sections.add(item["section"])
    return sections


# --- PR Size Limits ---

MAX_ADDED_ENTRIES = 5
MAX_MODIFIED_SECTIONS = 3


def check_pr_size(added_entries, removed_entries, modified_sections):
    """Check if the PR is suspiciously large (likely spam or bulk edit)."""
    errors = []

    if len(added_entries) > MAX_ADDED_ENTRIES:
        errors.append(
            f"This PR adds **{len(added_entries)} entries** (max {MAX_ADDED_ENTRIES}). "
            f"Please split into smaller PRs or add the `bulk` label if this is intentional."
        )

    if len(modified_sections) > MAX_MODIFIED_SECTIONS:
        errors.append(
            f"This PR modifies **{len(modified_sections)} sections** (max {MAX_MODIFIED_SECTIONS}). "
            f"Please keep changes to related sections or add the `bulk` label if this is intentional."
        )

    return errors


def main():
    errors = []
    warnings = []

    # Get diff
    diff_text = get_diff()
    if not diff_text:
        print("No changes to README.md detected.")
        output_result([], [], set(), 0, 0)
        return 0

    # Parse diff
    added_lines, removed_lines = parse_diff(diff_text)

    # If no table entries were added or removed, nothing to validate
    added_entries = [
        a for a in added_lines if TABLE_ENTRY_RE.match(a["content"].strip())
    ]
    removed_entries = [
        r for r in removed_lines if TABLE_ENTRY_RE.match(r["content"].strip())
    ]

    if not added_entries and not removed_entries:
        print("No API entry changes detected (might be docs/formatting only).")
        output_result([], [], set(), 0, 0)
        return 0

    modified_sections = get_modified_sections(added_lines)

    # 1. Validate each added entry format
    for item in added_entries:
        entry_errors = validate_entry(item["content"], item["section"])
        errors.extend(entry_errors)

    # 2. Check for deletions (append-only)
    is_cleanup = os.environ.get("PR_LABELS", "").lower().find("cleanup") != -1
    if not is_cleanup:
        deletion_errors = check_deletions(removed_lines)
        warnings.extend(deletion_errors)

    # 3. PR size limits (skip if labeled as bulk)
    is_bulk = os.environ.get("PR_LABELS", "").lower().find("bulk") != -1
    if not is_bulk:
        size_errors = check_pr_size(added_entries, removed_entries, modified_sections)
        errors.extend(size_errors)

    # 4. Read full README and check alphabetical order + duplicates
    try:
        readme_lines = get_full_readme()
        sections = parse_sections_from_readme(readme_lines)

        # Check alphabetical ordering in modified sections only
        for section_name in modified_sections:
            if section_name in sections:
                entries = sections[section_name]
                names = [e["name"].lower() for e in entries]
                for i in range(len(names) - 1):
                    if names[i] > names[i + 1]:
                        errors.append(
                            f"**{section_name}**: `{entries[i]['name']}` should come "
                            f"after `{entries[i+1]['name']}` (not in alphabetical order)"
                        )

        # Check for duplicates
        dup_errors = check_duplicates(sections, added_entries)
        errors.extend(dup_errors)

    except FileNotFoundError:
        warnings.append("Could not read README.md to check ordering/duplicates")

    # Output results
    output_result(errors, warnings, modified_sections,
                  len(added_entries), len(removed_entries))

    return 1 if errors else 0


def output_result(errors, warnings, modified_sections,
                   added_count=0, removed_count=0):
    """Write results to files for the GitHub Action to pick up."""
    result = {
        "errors": errors,
        "warnings": warnings,
        "modified_sections": list(modified_sections),
        "passed": len(errors) == 0,
        "added_count": added_count,
        "removed_count": removed_count,
        "is_single_entry": added_count == 1 and removed_count == 0,
    }

    # Write JSON result
    output_path = os.environ.get("VALIDATION_OUTPUT", "validation_result.json")
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    # Also print human-readable output
    if errors:
        print(f"\n{'='*60}")
        print(f"VALIDATION FAILED - {len(errors)} error(s) found:")
        print(f"{'='*60}")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\nAll validation checks passed!")

    if warnings:
        print(f"\n{'='*60}")
        print(f"WARNINGS - {len(warnings)} warning(s):")
        print(f"{'='*60}")
        for w in warnings:
            print(f"  - {w}")

    if modified_sections:
        print(f"\nModified sections: {', '.join(sorted(modified_sections))}")


if __name__ == "__main__":
    sys.exit(main())
