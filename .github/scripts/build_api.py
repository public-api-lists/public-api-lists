#!/usr/bin/env python3
"""
Build script: parses README.md into structured JSON API files.

Outputs:
  api/
    all.json          — all entries in one file
    categories.json   — list of categories with counts
    {category}.json   — entries for each category
    stats.json        — total counts and metadata
    random.json       — 10 random entries (regenerated each build)

These are served as a free static JSON API via GitHub Pages.
"""

import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timezone

TABLE_ENTRY_RE = re.compile(
    r'^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|'
    r'\s*(.+?)\s*\|'
    r'\s*(.+?)\s*\|'
    r'\s*(.+?)\s*\|'
    r'\s*(.+?)\s*\|$'
)

SECTION_RE = re.compile(r'^### (.+)$')

# Sections to skip (not API categories)
SKIP_SECTIONS = {"Gold Sponsors", "Silver Sponsors", "Bronze Sponsors"}


def slugify(text):
    """Convert a section name to a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


def parse_readme(readme_path):
    """Parse README.md into structured data."""
    with open(readme_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    categories = {}
    current_section = None

    for line in lines:
        line = line.rstrip()

        section_match = SECTION_RE.match(line)
        if section_match:
            raw_name = section_match.group(1).strip()
            # Strip emoji prefixes for comparison
            clean_name = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\s]+', '', raw_name).strip()
            if clean_name in SKIP_SECTIONS:
                current_section = None
                continue
            current_section = raw_name
            if current_section not in categories:
                categories[current_section] = []
            continue

        if current_section:
            match = TABLE_ENTRY_RE.match(line)
            if match:
                auth_raw = match.group(4).strip().strip('`')
                entry = {
                    "name": match.group(1).strip(),
                    "url": match.group(2).strip(),
                    "description": match.group(3).strip(),
                    "auth": auth_raw,
                    "https": match.group(5).strip() == "Yes",
                    "cors": match.group(6).strip(),
                    "category": current_section,
                }
                categories[current_section].append(entry)

    return categories


def build_api(categories, output_dir):
    """Generate all JSON API files."""
    os.makedirs(output_dir, exist_ok=True)

    # All entries flat list
    all_entries = []
    for cat_name, entries in sorted(categories.items()):
        all_entries.extend(entries)

    # all.json
    with open(os.path.join(output_dir, "all.json"), "w") as f:
        json.dump({
            "count": len(all_entries),
            "entries": all_entries,
        }, f, indent=2)

    # categories.json
    cat_list = []
    for cat_name in sorted(categories.keys()):
        cat_list.append({
            "name": cat_name,
            "slug": slugify(cat_name),
            "count": len(categories[cat_name]),
        })

    with open(os.path.join(output_dir, "categories.json"), "w") as f:
        json.dump({
            "count": len(cat_list),
            "categories": cat_list,
        }, f, indent=2)

    # Per-category JSON files
    for cat_name, entries in sorted(categories.items()):
        slug = slugify(cat_name)
        with open(os.path.join(output_dir, f"{slug}.json"), "w") as f:
            json.dump({
                "category": cat_name,
                "count": len(entries),
                "entries": entries,
            }, f, indent=2)

    # random.json — 10 random entries
    sample_size = min(10, len(all_entries))
    random_entries = random.sample(all_entries, sample_size)
    with open(os.path.join(output_dir, "random.json"), "w") as f:
        json.dump({
            "count": sample_size,
            "entries": random_entries,
            "note": "Random selection changes on each build",
        }, f, indent=2)

    # stats.json
    auth_counts = {}
    https_count = 0
    cors_counts = {"Yes": 0, "No": 0, "Unknown": 0}

    for entry in all_entries:
        auth_counts[entry["auth"]] = auth_counts.get(entry["auth"], 0) + 1
        if entry["https"]:
            https_count += 1
        cors_val = entry["cors"]
        if cors_val in cors_counts:
            cors_counts[cors_val] += 1

    with open(os.path.join(output_dir, "stats.json"), "w") as f:
        json.dump({
            "total_apis": len(all_entries),
            "total_categories": len(categories),
            "auth_breakdown": auth_counts,
            "https_percentage": round(https_count / len(all_entries) * 100, 1) if all_entries else 0,
            "cors_breakdown": cors_counts,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)

    return len(all_entries), len(categories)


def build_landing_page(categories, output_dir, api_count, cat_count):
    """Generate a simple landing page for GitHub Pages."""
    all_entries = []
    for entries in categories.values():
        all_entries.extend(entries)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Public API Lists</title>
    <meta name="description" content="A curated list of {api_count}+ free public APIs across {cat_count} categories. Browse, search, and use our free JSON API.">
    <style>
        :root {{
            --bg: #0d1117;
            --surface: #161b22;
            --border: #30363d;
            --text: #e6edf3;
            --text-muted: #8b949e;
            --accent: #58a6ff;
            --accent-hover: #79c0ff;
            --green: #3fb950;
            --tag-bg: #1f2937;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 0 24px; }}

        /* Header */
        header {{
            padding: 80px 0 48px;
            text-align: center;
        }}
        h1 {{
            font-size: 48px;
            font-weight: 800;
            margin-bottom: 16px;
            background: linear-gradient(135deg, var(--accent), var(--green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .subtitle {{
            font-size: 20px;
            color: var(--text-muted);
            max-width: 600px;
            margin: 0 auto 32px;
        }}
        .stats {{
            display: flex;
            gap: 32px;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 32px;
        }}
        .stat {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: 700;
            color: var(--accent);
        }}
        .stat-label {{
            font-size: 14px;
            color: var(--text-muted);
        }}

        /* Search */
        .search-container {{
            max-width: 600px;
            margin: 0 auto 48px;
        }}
        #search {{
            width: 100%;
            padding: 14px 20px;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: var(--surface);
            color: var(--text);
            font-size: 16px;
            outline: none;
            transition: border-color 0.2s;
        }}
        #search:focus {{
            border-color: var(--accent);
        }}
        #search::placeholder {{
            color: var(--text-muted);
        }}

        /* API Section */
        .api-section {{ margin-bottom: 24px; }}
        .api-endpoint {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 12px;
        }}
        .api-endpoint h3 {{
            font-size: 14px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        .api-endpoint code {{
            font-size: 15px;
            color: var(--green);
            background: rgba(63, 185, 80, 0.1);
            padding: 2px 8px;
            border-radius: 4px;
            font-family: 'SF Mono', 'Fira Code', monospace;
            word-break: break-all;
        }}
        .api-endpoint p {{
            color: var(--text-muted);
            font-size: 14px;
            margin-top: 4px;
        }}

        /* Categories Grid */
        .categories {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
            margin-bottom: 64px;
        }}
        .category-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px 20px;
            cursor: pointer;
            transition: border-color 0.2s, transform 0.1s;
            text-decoration: none;
            color: var(--text);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .category-card:hover {{
            border-color: var(--accent);
            transform: translateY(-1px);
        }}
        .category-card .name {{
            font-weight: 600;
        }}
        .category-card .count {{
            color: var(--text-muted);
            font-size: 14px;
        }}

        /* Entries Table */
        .entries {{ margin-bottom: 64px; }}
        .entry {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 8px;
            display: none;
        }}
        .entry.visible {{ display: block; }}
        .entry-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .entry-name {{
            font-weight: 600;
            font-size: 16px;
        }}
        .entry-name a {{
            color: var(--accent);
            text-decoration: none;
        }}
        .entry-name a:hover {{
            color: var(--accent-hover);
            text-decoration: underline;
        }}
        .entry-tags {{
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .tag {{
            font-size: 12px;
            padding: 2px 8px;
            border-radius: 6px;
            background: var(--tag-bg);
            color: var(--text-muted);
        }}
        .tag.auth {{ color: #d2a8ff; background: rgba(210, 168, 255, 0.1); }}
        .tag.https {{ color: var(--green); background: rgba(63, 185, 80, 0.1); }}
        .tag.cors {{ color: var(--accent); background: rgba(88, 166, 255, 0.1); }}
        .entry-desc {{
            color: var(--text-muted);
            font-size: 14px;
            margin-top: 6px;
        }}
        .entry-category {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        /* Footer */
        footer {{
            text-align: center;
            padding: 48px 0;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
        }}
        footer a {{
            color: var(--accent);
            text-decoration: none;
        }}

        .hidden {{ display: none; }}
        #result-count {{
            color: var(--text-muted);
            text-align: center;
            margin-bottom: 24px;
            font-size: 14px;
        }}
        .links {{
            display: flex;
            gap: 16px;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 48px;
        }}
        .links a {{
            color: var(--accent);
            text-decoration: none;
            padding: 10px 20px;
            border: 1px solid var(--border);
            border-radius: 8px;
            transition: border-color 0.2s;
        }}
        .links a:hover {{
            border-color: var(--accent);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Public API Lists</h1>
            <p class="subtitle">A curated list of free, open, and developer-friendly APIs. Browse, search, or use our JSON API.</p>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{api_count}</div>
                    <div class="stat-label">APIs</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{cat_count}</div>
                    <div class="stat-label">Categories</div>
                </div>
            </div>
            <div class="links">
                <a href="https://github.com/public-api-lists/public-api-lists">GitHub Repo</a>
                <a href="https://github.com/public-api-lists/public-api-lists/blob/master/.github/CONTRIBUTING.md">Contribute</a>
                <a href="https://github.com/public-api-lists/public-api-lists/blob/master/.github/SPONSORS.md">Sponsor</a>
            </div>
        </header>

        <h2 style="text-align:center; margin-bottom:24px; color:var(--text-muted); font-size:18px;">Free JSON API</h2>

        <div class="api-section">
            <div class="api-endpoint">
                <h3>All APIs</h3>
                <code>GET /api/all.json</code>
                <p>Returns all {api_count} API entries</p>
            </div>
            <div class="api-endpoint">
                <h3>Categories</h3>
                <code>GET /api/categories.json</code>
                <p>Returns all {cat_count} categories with entry counts</p>
            </div>
            <div class="api-endpoint">
                <h3>By Category</h3>
                <code>GET /api/{{slug}}.json</code>
                <p>Returns entries for a specific category (e.g., /api/animals.json)</p>
            </div>
            <div class="api-endpoint">
                <h3>Random</h3>
                <code>GET /api/random.json</code>
                <p>Returns 10 random API entries</p>
            </div>
            <div class="api-endpoint">
                <h3>Stats</h3>
                <code>GET /api/stats.json</code>
                <p>Returns aggregate statistics</p>
            </div>
        </div>

        <div class="search-container">
            <input type="text" id="search" placeholder="Search {api_count} APIs..." autocomplete="off">
        </div>
        <div id="result-count" class="hidden"></div>

        <div id="categories-grid" class="categories">
"""

    # Category cards
    for cat_name in sorted(categories.keys()):
        count = len(categories[cat_name])
        slug = slugify(cat_name)
        html += f'            <div class="category-card" data-category="{slug}" onclick="filterCategory(\'{slug}\')">\n'
        html += f'                <span class="name">{cat_name}</span>\n'
        html += f'                <span class="count">{count}</span>\n'
        html += f'            </div>\n'

    html += """        </div>

        <div id="entries" class="entries">
"""

    # All entries
    for entry in all_entries:
        slug = slugify(entry["category"])
        tags_html = ""
        if entry["auth"] != "No":
            tags_html += f'<span class="tag auth">{entry["auth"]}</span>'
        if entry["https"]:
            tags_html += '<span class="tag https">HTTPS</span>'
        if entry["cors"] == "Yes":
            tags_html += '<span class="tag cors">CORS</span>'

        safe_name = entry["name"].replace('"', '&quot;')
        safe_desc = entry["description"].replace('"', '&quot;')
        html += f"""            <div class="entry" data-category="{slug}" data-name="{safe_name.lower()}" data-desc="{safe_desc.lower()}">
                <div class="entry-header">
                    <span class="entry-name"><a href="{entry["url"]}" target="_blank" rel="noopener">{entry["name"]}</a></span>
                    <div class="entry-tags">{tags_html}</div>
                </div>
                <div class="entry-desc">{entry["description"]}</div>
                <div class="entry-category">{entry["category"]}</div>
            </div>
"""

    html += f"""        </div>

        <footer>
            <p>
                Made with care by the <a href="https://github.com/public-api-lists/public-api-lists">public-api-lists</a> community.
                <br>Last built: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
            </p>
        </footer>
    </div>

    <script>
        const search = document.getElementById('search');
        const entries = document.querySelectorAll('.entry');
        const categoriesGrid = document.getElementById('categories-grid');
        const resultCount = document.getElementById('result-count');

        function showAll() {{
            entries.forEach(e => e.classList.remove('visible'));
            categoriesGrid.classList.remove('hidden');
            resultCount.classList.add('hidden');
        }}

        function filterCategory(slug) {{
            categoriesGrid.classList.add('hidden');
            let count = 0;
            entries.forEach(e => {{
                if (e.dataset.category === slug) {{
                    e.classList.add('visible');
                    count++;
                }} else {{
                    e.classList.remove('visible');
                }}
            }});
            resultCount.textContent = count + ' APIs in this category';
            resultCount.classList.remove('hidden');
            search.value = '';
            window.scrollTo({{ top: search.offsetTop - 20, behavior: 'smooth' }});
        }}

        search.addEventListener('input', function() {{
            const q = this.value.toLowerCase().trim();
            if (!q) {{
                showAll();
                return;
            }}

            categoriesGrid.classList.add('hidden');
            let count = 0;
            entries.forEach(e => {{
                const match = e.dataset.name.includes(q) || e.dataset.desc.includes(q) || e.dataset.category.includes(q);
                if (match) {{
                    e.classList.add('visible');
                    count++;
                }} else {{
                    e.classList.remove('visible');
                }}
            }});
            resultCount.textContent = count + ' result' + (count !== 1 ? 's' : '');
            resultCount.classList.remove('hidden');
        }});
    </script>
</body>
</html>"""

    with open(os.path.join(output_dir, "index.html"), "w") as f:
        f.write(html)


def main():
    readme_path = os.environ.get("README_PATH", "README.md")
    output_dir = os.environ.get("OUTPUT_DIR", "public")

    print(f"Parsing {readme_path}...")
    categories = parse_readme(readme_path)

    print(f"Found {len(categories)} categories")

    # Build API JSON files
    api_dir = os.path.join(output_dir, "api")
    api_count, cat_count = build_api(categories, api_dir)
    print(f"Built API: {api_count} entries across {cat_count} categories")

    # Build landing page
    build_landing_page(categories, output_dir, api_count, cat_count)
    print(f"Built landing page at {output_dir}/index.html")

    print("Done!")


if __name__ == "__main__":
    main()
