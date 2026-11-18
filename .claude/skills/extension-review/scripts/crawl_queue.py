#!/usr/bin/env python3
"""Re-crawl the extensions.blender.org approval queue to refresh references/moderation-evidence.md.

Usage:
    python3 crawl_queue.py OUT_DIR [--recent N]

Writes OUT_DIR/queue.json (all entries) and OUT_DIR/reviews.jsonl (activity of every add-on review
page: author role, status change, text). Re-running resumes where it stopped. --recent N only
fetches the N most recently active add-ons (fast way to catch new moderator policies).

Polite by design: 3 parallel requests with a pause; a full crawl of ~2,100 add-ons takes ~12 min.
Then grep the moderator comments, e.g.:
    python3 -c "import json;[print(r['slug'],a['text'][:300]) for r in map(json.loads,open('OUT/reviews.jsonl')) for a in r['acts'] if a['role']=='Moderator' and 'delist' in a['text'].lower()]"
"""
import concurrent.futures as cf
import html
import json
import os
import re
import sys
import time
import urllib.request

BASE = "https://extensions.blender.org/approval-queue/"
UA = {"User-Agent": "Mozilla/5.0 (extension-review skill; slow crawler)"}


def get(url):
    for i in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode()
        except Exception:  # noqa: BLE001
            time.sleep(3 + 4 * i)
    return ""


def clean(x):
    x = re.sub(r"<br\s*/?>|</p>|</li>", "\n", x)
    return html.unescape(re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", "", x))).strip()


def crawl_index(limit_pages=None):
    items, page = {}, 1
    while True:
        s = get(f"{BASE}?filter_by=all&page={page}")
        n = 0
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
            m = re.search(r'href="/approval-queue/([^/"#]+)/"', r)
            if not m:
                continue
            cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            items[m.group(1)] = cells  # [type, name, maintainer, submitted, activity, comments, status]
            n += 1
        if n == 0 or f"page={page + 1}" not in s or (limit_pages and page >= limit_pages):
            break
        page += 1
        time.sleep(0.7)
    return items


def fetch(slug, meta):
    s = get(f"{BASE}{slug}/")
    if not s:
        return {"slug": slug, "error": True}
    acts = []
    for li in re.findall(r'<article class="activity-item comment-card">(.*?)</article>', s, re.S):
        role = re.search(r'<span title="([^"]+)"><i', li)
        who = re.search(r'<header>.*?<a href="/author/\d+/">\s*(.*?)\s*</a>', li, re.S)
        status = re.search(r'badge-status-[^"]*">\s*(.*?)\s*</span>', li, re.S)
        when = re.search(r'title="([^"]+\d{4} - [^"]+)"', li)
        body = re.search(r'<div class="comment-card-content">(.*?)</div>\s*</div>\s*$', li, re.S)
        acts.append({"role": role.group(1) if role else "", "who": who.group(1) if who else "",
                     "status": status.group(1).strip() if status else "",
                     "when": when.group(1) if when else "", "text": clean(body.group(1)) if body else ""})
    time.sleep(0.4)
    return {"slug": slug, "name": meta[1], "state": meta[-1], "acts": acts}


def main(argv):
    out = argv[0]
    recent = int(argv[argv.index("--recent") + 1]) if "--recent" in argv else None
    os.makedirs(out, exist_ok=True)
    items = crawl_index(limit_pages=(recent // 50 + 1) if recent else None)
    json.dump(items, open(os.path.join(out, "queue.json"), "w"), ensure_ascii=False, indent=0)
    slugs = [k for k, v in items.items() if v and v[0] == "Add-on"]
    if recent:
        slugs = slugs[:recent]
    path = os.path.join(out, "reviews.jsonl")
    done = set()
    if os.path.exists(path) and not recent:
        done = {json.loads(line)["slug"] for line in open(path)}
    todo = [s for s in slugs if s not in done]
    print(f"{len(items)} entries, {len(todo)} add-on pages to fetch", flush=True)
    with open(path, "a" if not recent else "w") as f, cf.ThreadPoolExecutor(3) as ex:
        for i, r in enumerate(ex.map(lambda s: fetch(s, items[s]), todo)):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            if i % 100 == 0:
                print(i, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
