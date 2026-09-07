"""One-off repair: backfill date_published for archived ca_doj events.

The original collector only matched ISO / Month-name dates; CA DOJ rows use
MM/DD/YYYY (breach date then reported date). This re-derives the REPORTED date
(the last date in the row) from the stored raw cells and rewrites events.jsonl
in place. Idempotent: rows already carrying an ISO date are left alone.
"""
import json
import re
from datetime import datetime
from pathlib import Path

path = Path(__file__).resolve().parent.parent / 'data' / 'events.jsonl'
DATE_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|[A-Z][a-z]+ \d{1,2}, \d{4})')


def to_iso(raw: str) -> str:
    if '-' in raw:
        return raw
    if '/' in raw:
        return datetime.strptime(raw, '%m/%d/%Y').strftime('%Y-%m-%d')
    return datetime.strptime(raw, '%B %d, %Y').strftime('%Y-%m-%d')


fixed = skipped = total = 0
lines = path.read_text(encoding='utf-8').splitlines()
out = []
for line in lines:
    if not line.strip():
        continue
    e = json.loads(line)
    total += 1
    if e.get('source') == 'ca_doj' and not e.get('date_published'):
        cells = (e.get('raw') or {}).get('cells') or []
        text = ' | '.join(cells) if cells else e.get('title', '')
        dates = DATE_RE.findall(text)
        if dates:
            try:
                e['date_published'] = to_iso(dates[-1])
                fixed += 1
            except ValueError:
                skipped += 1
    out.append(json.dumps(e, ensure_ascii=False))

path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'total={total} fixed={fixed} skipped={skipped}')

# sanity: date distribution
from collections import Counter
c = Counter()
for line in out:
    e = json.loads(line)
    if e.get('source') == 'ca_doj':
        c[e.get('date_published', '')[:7]] += 1
print('ca_doj by month:', dict(sorted(c.items())[-8:]))
