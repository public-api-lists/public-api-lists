#!/usr/bin/env python3
"""
Auto-sort all API entries within each section alphabetically.

Usage:
    python3 .github/scripts/sort_entries.py          # dry-run (shows what would change)
    python3 .github/scripts/sort_entries.py --fix     # sorts in-place

This is useful for:
  - Contributors fixing alphabetical order violations
  - Maintainers doing bulk cleanup
  - CI scripts that auto-fix PRs
"""

import re
import sys

SECTION_RE = re.compile(r'^### (.+)$')
TABLE_ENTRY_RE = re.compile(
    r'^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|'
    r'\s*(.+?)\s*\|'
    r'\s*(.+?)\s*\|'
    r'\s*(.+?)\s*\|'
    r'\s*(.+?)\s*\|$'
)
TABLE_HEADER_RE = re.compile(r'^\|.*API.*Description.*\|$')
TABLE_SEP_RE = re.compile(r'^\|[\s:\-]+\|')
SKIP_SECTIONS = {"Gold Sponsors", "Silver Sponsors", "Bronze Sponsors"}


def extract_sort_key(line):
    """Extract the API name for sorting (case-insensitive)."""
    match = TABLE_ENTRY_RE.match(line.strip())
    if match:
        return match.group(1).strip().lower()
    return ""


def sort_readme(readme_path, fix=False):
    with open(readme_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    output = []
    i = 0
    total_fixes = 0
    sections_fixed = []

    while i < len(lines):
        line = lines[i]

        # Check for section header
        section_match = SECTION_RE.match(line.strip())
        if section_match:
            section_name = section_match.group(1).strip()
            clean_name = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\s]+', '', section_name).strip()

            output.append(line)
            i += 1

            if clean_name in SKIP_SECTIONS:
                continue

            # Collect the table: blank line, header, separator, entries
            pre_table = []
            entries = []
            post_table = []

            # Collect lines between header and entries (blank, header, sep)
            while i < len(lines):
                l = lines[i]
                stripped = l.strip()

                if TABLE_ENTRY_RE.match(stripped):
                    break
                pre_table.append(l)
                i += 1

                if TABLE_SEP_RE.match(stripped):
                    break

            # Collect entries
            while i < len(lines):
                stripped = lines[i].strip()
                if TABLE_ENTRY_RE.match(stripped):
                    entries.append(lines[i])
                    i += 1
                else:
                    break

            if entries:
                # Sort entries by API name
                sorted_entries = sorted(entries, key=lambda l: extract_sort_key(l))

                if entries != sorted_entries:
                    total_fixes += 1
                    sections_fixed.append(section_name)

                    # Show diff
                    old_names = [extract_sort_key(e) for e in entries]
                    new_names = [extract_sort_key(e) for e in sorted_entries]
                    if old_names != new_names:
                        moved = []
                        for j, (old, new) in enumerate(zip(old_names, new_names)):
                            if old != new:
                                moved.append(f"    {old} -> {new}")
                        if moved:
                            print(f"\n{section_name} ({len(entries)} entries):")
                            for m in moved[:5]:
                                print(m)
                            if len(moved) > 5:
                                print(f"    ... and {len(moved)-5} more")

                output.extend(pre_table)
                output.extend(sorted_entries if fix else entries)
            else:
                output.extend(pre_table)

            continue

        output.append(line)
        i += 1

    if fix and total_fixes > 0:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.writelines(output)
        print(f"\nFixed {total_fixes} section(s): {', '.join(sections_fixed)}")
    elif total_fixes > 0:
        print(f"\nFound {total_fixes} section(s) with ordering issues: {', '.join(sections_fixed)}")
        print("Run with --fix to sort them.")
    else:
        print("All sections are already in alphabetical order!")

    return total_fixes


if __name__ == "__main__":
    fix = "--fix" in sys.argv
    readme = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "README.md"
    sort_readme(readme, fix=fix)
