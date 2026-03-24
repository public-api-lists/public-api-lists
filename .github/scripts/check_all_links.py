#!/usr/bin/env python3
"""
Check all API links in README.md and output broken ones to broken_links.json.
Used by the weekly scheduled link check workflow.
"""

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

TABLE_ENTRY_RE = re.compile(
    r'^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|'
    r'\s*(.+?)\s*\|'
    r'\s*(.+?)\s*\|'
    r'\s*(.+?)\s*\|'
    r'\s*(.+?)\s*\|$'
)

SECTION_RE = re.compile(r'^### (.+)$')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; PublicAPILists-LinkChecker/1.0)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def check_url(entry):
    """Check a single URL. Returns the entry with a status field."""
    url = entry["url"]
    try:
        req = Request(url, headers=HEADERS, method='HEAD')
        response = urlopen(req, timeout=15)
        status = response.getcode()
    except HTTPError as e:
        status = e.code
    except (URLError, OSError, Exception):
        # Try GET as fallback (some servers reject HEAD)
        try:
            req = Request(url, headers=HEADERS)
            response = urlopen(req, timeout=15)
            status = response.getcode()
        except HTTPError as e:
            status = e.code
        except Exception:
            status = 0

    entry["status"] = status
    return entry


def main():
    readme_path = os.path.join(os.environ.get("GITHUB_WORKSPACE", "."), "README.md")

    with open(readme_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Parse all entries
    entries = []
    current_section = None

    for line in lines:
        line = line.rstrip()
        section_match = SECTION_RE.match(line)
        if section_match:
            current_section = section_match.group(1).strip()
            continue

        match = TABLE_ENTRY_RE.match(line)
        if match and current_section:
            entries.append({
                "section": current_section,
                "name": match.group(1).strip(),
                "url": match.group(2).strip(),
            })

    print(f"Found {len(entries)} API links to check...")

    # Check links in parallel (max 10 concurrent)
    broken = []
    checked = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_url, entry): entry for entry in entries}
        for future in as_completed(futures):
            result = future.result()
            checked += 1
            status = result["status"]

            if status == 0 or status >= 400:
                status_str = str(status) if status > 0 else "Connection Failed"
                broken.append({
                    "section": result["section"],
                    "name": result["name"],
                    "url": result["url"],
                    "status": status_str,
                })
                print(f"  FAIL [{status_str}] {result['name']} — {result['url']}")
            else:
                if checked % 50 == 0:
                    print(f"  Checked {checked}/{len(entries)}...")

    # Sort broken links by section
    broken.sort(key=lambda x: (x["section"], x["name"]))

    result = {
        "total": len(entries),
        "broken": broken,
    }

    with open("broken_links.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nDone. {len(broken)} broken link(s) out of {len(entries)} total.")

    if broken:
        print("\nBroken links:")
        for b in broken:
            print(f"  [{b['status']}] {b['section']} > {b['name']} — {b['url']}")


if __name__ == "__main__":
    main()
