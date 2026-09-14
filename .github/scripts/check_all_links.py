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

# A checker that announces itself as a bot gets served a challenge page or a 403
# by most WAFs, which then looks identical to a dead link in the report.
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# HEAD is not universally implemented. These replies tell us the server disliked
# the request, not that the page is missing, so they are worth a GET retry.
RETRY_WITH_GET = frozenset({400, 401, 403, 405, 406, 409, 429, 500, 501, 502, 503})

# Replies about the client rather than the link. A person with a browser reaches
# these pages fine, so counting them as broken is what fills the report with noise.
INCONCLUSIVE = frozenset({401, 403, 429})


def _fetch(url, method):
    req = Request(url, headers=HEADERS, method=method)
    with urlopen(req, timeout=20) as response:
        return response.getcode()


def check_url(entry):
    """Check a single URL. Returns the entry with status and inconclusive fields."""
    url = entry["url"]

    try:
        status = _fetch(url, 'HEAD')
    except HTTPError as e:
        status = e.code
    except (URLError, OSError):
        status = 0

    # The GET fallback below used to be unreachable: HTTPError subclasses URLError,
    # so it was caught by the first handler and a 405 from HEAD was reported as a
    # broken link. Retry explicitly on the statuses that mean "not like that".
    if status == 0 or status in RETRY_WITH_GET:
        try:
            status = _fetch(url, 'GET')
        except HTTPError as e:
            status = e.code
        except (URLError, OSError):
            # GET told us nothing new, so keep whatever HEAD reported.
            pass

    entry["status"] = status
    entry["inconclusive"] = status in INCONCLUSIVE
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
    blocked = []
    checked = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_url, entry): entry for entry in entries}
        for future in as_completed(futures):
            result = future.result()
            checked += 1
            status = result["status"]
            record = {
                "section": result["section"],
                "name": result["name"],
                "url": result["url"],
                "status": str(status) if status > 0 else "Connection Failed",
            }

            if result["inconclusive"]:
                blocked.append(record)
                print(f"  SKIP [{status}] blocked the checker, not verified: {result['url']}")
            elif status == 0 or status >= 400:
                broken.append(record)
                print(f"  FAIL [{record['status']}] {result['name']}: {result['url']}")
            elif checked % 50 == 0:
                print(f"  Checked {checked}/{len(entries)}...")

    # Sort broken links by section
    broken.sort(key=lambda x: (x["section"], x["name"]))
    blocked.sort(key=lambda x: (x["section"], x["name"]))

    result = {
        "total": len(entries),
        "broken": broken,
        "blocked": blocked,
    }

    with open("broken_links.json", "w") as f:
        json.dump(result, f, indent=2)

    print(
        f"\nDone. {len(broken)} broken link(s) out of {len(entries)} total, "
        f"{len(blocked)} not verified because the host blocked the checker."
    )

    if broken:
        print("\nBroken links:")
        for b in broken:
            print(f"  [{b['status']}] {b['section']} > {b['name']}: {b['url']}")

    if blocked:
        print("\nNot verified (host blocked the checker, these are not reported):")
        for b in blocked:
            print(f"  [{b['status']}] {b['section']} > {b['name']}: {b['url']}")


if __name__ == "__main__":
    main()
