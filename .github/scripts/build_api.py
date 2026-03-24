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

    # random.json — 10 random entries (changes on each deploy, not per request)
    sample_size = min(10, len(all_entries))
    random_entries = random.sample(all_entries, sample_size)
    with open(os.path.join(output_dir, "random.json"), "w") as f:
        json.dump({
            "count": sample_size,
            "entries": random_entries,
            "note": "Static file — changes on each deploy, not per request. For true randomness, fetch /api/all.json and sample client-side",
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
    """Generate a lightweight landing page that fetches data from JSON API."""

    # Build category data for inline bootstrap (small, just names + counts)
    cat_json = json.dumps([
        {"name": name, "slug": slugify(name), "count": len(entries)}
        for name, entries in sorted(categories.items())
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Public API Lists — {api_count}+ Free APIs for Developers</title>
<meta name="description" content="A curated list of {api_count}+ free public APIs across {cat_count} categories. Search, browse, and access via our free JSON API.">
<meta property="og:title" content="Public API Lists">
<meta property="og:description" content="{api_count}+ free public APIs across {cat_count} categories">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#128279;</text></svg>">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--bg:#0a0a0a;--s1:#141414;--s2:#1a1a1a;--b:#262626;--b2:#333;--t:#fafafa;--t2:#a1a1aa;--t3:#71717a;--ac:#3b82f6;--ac2:#60a5fa;--gn:#22c55e;--pp:#a78bfa;--mono:'SF Mono',ui-monospace,monospace}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--t);line-height:1.5;-webkit-font-smoothing:antialiased}}
a{{color:var(--ac2);text-decoration:none}}a:hover{{text-decoration:underline}}
.w{{max-width:1100px;margin:0 auto;padding:0 20px}}

header{{padding:64px 0 40px;text-align:center}}
h1{{font-size:clamp(28px,5vw,44px);font-weight:800;letter-spacing:-.02em;margin-bottom:12px}}
.sub{{font-size:clamp(15px,2.5vw,18px);color:var(--t2);max-width:520px;margin:0 auto 28px}}
.nums{{display:flex;gap:40px;justify-content:center;margin-bottom:24px}}
.num span:first-child{{font-size:28px;font-weight:700;color:var(--t)}}
.num span:last-child{{font-size:13px;color:var(--t3);display:block;margin-top:2px}}
.nav{{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:40px}}
.nav a{{font-size:13px;color:var(--t2);padding:7px 16px;border:1px solid var(--b);border-radius:8px;transition:.15s}}
.nav a:hover{{border-color:var(--ac);color:var(--t);text-decoration:none}}

.search-wrap{{max-width:560px;margin:0 auto 32px;position:relative}}
#q{{width:100%;padding:12px 16px 12px 40px;border-radius:10px;border:1px solid var(--b);background:var(--s1);color:var(--t);font-size:15px;outline:none;transition:.15s}}
#q:focus{{border-color:var(--ac);box-shadow:0 0 0 3px rgba(59,130,246,.15)}}
#q::placeholder{{color:var(--t3)}}
.si{{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--t3);font-size:15px;pointer-events:none}}

#bar{{text-align:center;margin-bottom:20px;font-size:13px;color:var(--t3);display:none}}
#bar button{{background:none;border:none;color:var(--ac2);cursor:pointer;font-size:13px;margin-left:8px}}
#bar button:hover{{text-decoration:underline}}

.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:8px;margin-bottom:48px}}
.cat{{background:var(--s1);border:1px solid var(--b);border-radius:8px;padding:12px 16px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;transition:.15s;user-select:none}}
.cat:hover{{border-color:var(--ac);background:var(--s2)}}
.cat .n{{font-weight:600;font-size:14px}}.cat .c{{color:var(--t3);font-size:13px;font-variant-numeric:tabular-nums}}
.cat.active{{border-color:var(--ac);background:rgba(59,130,246,.08)}}

.sponsor{{text-align:center;margin-bottom:48px;padding:24px;border:1px solid var(--b);border-radius:12px;background:var(--s1)}}
.sponsor p{{font-size:12px;color:var(--t3);margin-bottom:12px}}
.sponsor a img{{border-radius:8px;opacity:.9;transition:.15s}}
.sponsor a img:hover{{opacity:1}}
.sponsor .sp-name{{font-size:13px;color:var(--t2);margin-top:8px}}
.sponsor .sp-cta{{font-size:12px;color:var(--t3);margin-top:12px}}
.sponsor .sp-cta a{{color:var(--ac2);font-size:12px}}

#list{{margin-bottom:48px}}
.e{{background:var(--s1);border:1px solid var(--b);border-radius:8px;padding:14px 16px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}}
.e:hover{{border-color:var(--b2)}}
.e-l{{flex:1;min-width:200px}}
.e-n{{font-weight:600;font-size:15px}}
.e-d{{font-size:13px;color:var(--t2);margin-top:2px}}
.e-r{{display:flex;gap:5px;flex-wrap:wrap;align-items:center}}
.tg{{font-size:11px;padding:2px 7px;border-radius:5px;font-family:var(--mono);white-space:nowrap}}
.tg-a{{color:var(--pp);background:rgba(167,139,250,.1)}}.tg-h{{color:var(--gn);background:rgba(34,197,94,.1)}}.tg-c{{color:var(--ac2);background:rgba(59,130,246,.1)}}
.empty{{text-align:center;color:var(--t3);padding:40px 0}}

details{{max-width:560px;margin:0 auto 48px;border:1px solid var(--b);border-radius:10px;background:var(--s1)}}
summary{{padding:14px 16px;cursor:pointer;font-weight:600;font-size:14px;color:var(--t2);list-style:none}}
summary::-webkit-details-marker{{display:none}}
summary::before{{content:'\\25B6\\FE0F';margin-right:8px;font-size:11px}}
details[open] summary::before{{content:'\\25BC\\FE0F'}}
.api-list{{padding:4px 16px 16px}}
.api-row{{display:flex;justify-content:space-between;align-items:baseline;padding:8px 0;border-bottom:1px solid var(--b)}}
.api-row:last-child{{border:none}}
.api-row code{{font-size:13px;color:var(--gn);font-family:var(--mono)}}
.api-row span{{font-size:12px;color:var(--t3)}}

footer{{text-align:center;padding:32px 0;color:var(--t3);font-size:13px;border-top:1px solid var(--b)}}

.ld{{display:inline-block;width:16px;height:16px;border:2px solid var(--b2);border-top-color:var(--ac);border-radius:50%;animation:sp .6s linear infinite}}
@keyframes sp{{to{{transform:rotate(360deg)}}}}

@media(max-width:600px){{
  header{{padding:40px 0 24px}}
  .nums{{gap:24px}}.num span:first-child{{font-size:22px}}
  .grid{{grid-template-columns:1fr 1fr}}
  .e{{flex-direction:column}}
}}
</style>
</head>
<body>
<div class="w">
  <header>
    <h1>Public API Lists</h1>
    <p class="sub">A curated list of free, open, and developer-friendly APIs for your next project</p>
    <div class="nums">
      <div class="num"><span>{api_count}</span><span>APIs</span></div>
      <div class="num"><span>{cat_count}</span><span>Categories</span></div>
      <div class="num"><span>100%</span><span>Free</span></div>
    </div>
    <div class="nav">
      <a href="https://github.com/public-api-lists/public-api-lists">GitHub</a>
      <a href="https://github.com/public-api-lists/public-api-lists/blob/master/.github/CONTRIBUTING.md">Contribute</a>
      <a href="https://github.com/public-api-lists/public-api-lists/blob/master/.github/SPONSORS.md">Sponsor</a>
    </div>
  </header>

  <div class="search-wrap">
    <span class="si">&#128269;</span>
    <input type="text" id="q" placeholder="Search {api_count} APIs..." autocomplete="off">
  </div>

  <div class="sponsor">
    <p>Sponsored by</p>
    <a href="https://serpapi.com/?utm_source=public-api-lists">
      <img src="https://raw.githubusercontent.com/public-api-lists/public-api-lists/master/assets/serpapi.png" width="280" alt="SerpApi">
    </a>
    <div class="sp-name">Scrape Google and other search engines with a simple API</div>
    <div class="sp-cta"><a href="https://github.com/public-api-lists/public-api-lists/blob/master/.github/SPONSORS.md">Become a sponsor</a></div>
  </div>

  <div id="bar"></div>
  <div id="cats" class="grid"></div>
  <div id="list"></div>

  <details>
    <summary>Free JSON API</summary>
    <div class="api-list">
      <div class="api-row"><code>GET /api/all.json</code><span>All {api_count} entries</span></div>
      <div class="api-row"><code>GET /api/categories.json</code><span>{cat_count} categories</span></div>
      <div class="api-row"><code>GET /api/{{slug}}.json</code><span>By category</span></div>
      <div class="api-row"><code>GET /api/random.json</code><span>10 random entries (per deploy)</span></div>
      <div class="api-row"><code>GET /api/stats.json</code><span>Aggregate stats</span></div>
    </div>
  </details>

  <footer>
    Built by the <a href="https://github.com/public-api-lists/public-api-lists">public-api-lists</a> community &middot; {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
  </footer>
</div>

<script>
const CATS={cat_json};
const BASE='api/';
let allData=null;
let activeCats=new Set();
const cache={{}};

const $=s=>document.querySelector(s);
const cats$=$('#cats'),list$=$('#list'),bar$=$('#bar'),q$=$('#q');

function renderCats(){{
  cats$.innerHTML=CATS.map(c=>
    `<div class="cat${{activeCats.has(c.slug)?' active':''}}" data-s="${{c.slug}}"><span class="n">${{c.name}}</span><span class="c">${{c.count}}</span></div>`
  ).join('');
  cats$.querySelectorAll('.cat').forEach(el=>el.onclick=()=>{{
    const s=el.dataset.s;
    if(activeCats.has(s)){{ activeCats.delete(s) }}
    else{{ activeCats.add(s) }}
    renderCats();
    if(activeCats.size===0){{ list$.innerHTML='';bar$.style.display='none' }}
    else{{ loadSelected() }}
  }});
}}

function renderEntries(entries,label){{
  if(!entries.length){{ list$.innerHTML='<div class="empty">No APIs found</div>';bar$.innerHTML=label;bar$.style.display='block';return }}
  bar$.innerHTML=`${{entries.length}} ${{label}}`;
  const btn=document.createElement('button');btn.textContent='Clear all';btn.onclick=clearView;bar$.appendChild(btn);
  bar$.style.display='block';
  list$.innerHTML=entries.map(e=>{{
    let tags='';
    if(e.auth&&e.auth!=='No')tags+=`<span class="tg tg-a">${{e.auth}}</span>`;
    if(e.https)tags+=`<span class="tg tg-h">HTTPS</span>`;
    if(e.cors==='Yes')tags+=`<span class="tg tg-c">CORS</span>`;
    return`<div class="e"><div class="e-l"><div class="e-n"><a href="${{e.url}}" target="_blank" rel="noopener">${{e.name}}</a></div><div class="e-d">${{e.description}}</div></div><div class="e-r">${{tags}}</div></div>`;
  }}).join('');
}}

function clearView(){{ activeCats.clear();list$.innerHTML='';bar$.style.display='none';q$.value='';renderCats();cats$.style.display='' }}

async function loadSelected(){{
  list$.innerHTML='<div class="empty"><span class="ld"></span></div>';
  const all=[];
  for(const slug of activeCats){{
    if(!cache[slug]){{
      const r=await fetch(BASE+slug+'.json');const d=await r.json();
      cache[slug]=d.entries;
    }}
    all.push(...cache[slug]);
  }}
  const names=[...activeCats].map(s=>CATS.find(c=>c.slug===s)?.name).filter(Boolean);
  renderEntries(all,`APIs in ${{names.join(', ')}}`);
}}

async function loadAll(){{
  if(allData)return allData;
  const r=await fetch(BASE+'all.json');const d=await r.json();
  allData=d.entries;return allData;
}}

let timer;
q$.addEventListener('input',()=>{{
  clearTimeout(timer);
  timer=setTimeout(async()=>{{
    const v=q$.value.trim().toLowerCase();
    if(!v){{ clearView();return }}
    activeCats.clear();renderCats();cats$.style.display='none';
    list$.innerHTML='<div class="empty"><span class="ld"></span></div>';
    const data=await loadAll();
    const res=data.filter(e=>e.name.toLowerCase().includes(v)||e.description.toLowerCase().includes(v)||e.category.toLowerCase().includes(v));
    renderEntries(res,'result'+(res.length!==1?'s':''));
  }},200);
}});

renderCats();
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
