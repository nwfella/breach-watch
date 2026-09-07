"""Summarize the events.jsonl archive: counts by source + newest items per source."""
import json
from collections import Counter
from pathlib import Path

path = Path(__file__).resolve().parent / 'data' / 'events.jsonl'
counts = Counter()
newest = {}
n = 0
with open(path, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        n += 1
        counts[e['source']] += 1
        cur = newest.get(e['source'])
        if cur is None or (e.get('date_published') or '') > (cur.get('date_published') or ''):
            newest[e['source']] = e

print(f'total events: {n}')
for src, c in counts.most_common():
    ne = newest.get(src) or {}
    print(f'  {src:>10}: {c:>6}  | newest: {ne.get("date_published", "?")}  {ne.get("title", "")[:80]}')

# top 12 newest events overall across the whole archive
rows = []
with open(path, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            rows.append(json.loads(line))
rows.sort(key=lambda e: e.get('date_published') or '', reverse=True)
print('\n--- 12 newest events in archive ---')
for e in rows[:12]:
    rec = f' | {e["records"]:,} rec' if e.get('records') else ''
    print(f'[{e["date_published"]}] {e["source"]:<9} {e["title"][:90]}{rec}')
