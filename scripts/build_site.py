"""Build the BreachWatch static site from the event archive.

Reads data/events.jsonl, curates a digest window, computes archive stats, and
bakes everything into out/index.html (template.html + embedded JSON payload).
The page performs ZERO runtime fetches — required for IT environments that
neuter XHR on github.io. Stdlib only.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
EVENTS = BASE / 'data' / 'events.jsonl'
TEMPLATE = BASE / 'site' / 'template.html'
OUT = BASE / 'out' / 'index.html'

START = '/*__BW_DATA_START__*/'
END = '/*__BW_DATA_END__*/'

WINDOW_DAYS = 400

# Google News same-story collapse: keep the highest-trust outlet per story.
PREFERRED = ['CBC', 'Reuters', 'Globe and Mail', 'CTV News', 'National Post',
             'Toronto Star', 'Radio-Canada', 'Global News', 'La Presse',
             'CP24', 'The Canadian Press', 'CBC News']


def outlet_rank(name: str) -> int:
    low = (name or '').lower()
    for i, pref in enumerate(PREFERRED):
        if pref.lower() in low:
            return i
    return len(PREFERRED)


def load_events() -> list:
    if not EVENTS.exists():
        raise SystemExit(f'no archive at {EVENTS} — run the collector first (python main.py)')
    out = []
    for line in EVENTS.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


DATE_LIKE = re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$|^\d{4}-\d{2}-\d{2}$')


def is_date_like(s: str) -> bool:
    return bool(DATE_LIKE.match(s.strip()))


def hibp_name(e: dict) -> str:
    return e.get('url', '').rstrip('/').rsplit('/Breach/', 1)[-1]


def compact(e: dict, title: str, desc: str) -> dict:
    c = {'s': e['source'], 'r': e.get('region') or 'unknown',
         'd': e.get('date_published') or '', 't': title, 'u': e.get('url', '')}
    n = int(e.get('records') or 0)
    if n:
        c['n'] = n
    dc = [d for d in (e.get('data_classes') or []) if d][:8]
    if dc:
        c['dc'] = dc
    if desc:
        c['x'] = desc
    raw = e.get('raw') or {}
    if raw.get('is_sensitive'):
        c['sens'] = 1
    return c


def main() -> None:
    events = load_events()
    now = datetime.utcnow()
    cutoff = (now - timedelta(days=WINDOW_DAYS)).strftime('%Y-%m-%d')

    # --- archive stats (full corpus) ---
    n_total = len(events)
    src = {}
    records_total = 0
    nd_sources = {'opc_news', 'cai_news', 'google_news', 'hibp_rss'}
    nd_items = 0
    for e in events:
        s = e['source']
        src[s] = src.get(s, 0) + 1
        if s == 'hibp_api':
            records_total += int(e.get('records') or 0)
        if s in nd_sources:
            nd_items += 1

    # --- digest window (last WINDOW_DAYS by published date) ---
    window = [e for e in events
              if e.get('date_published', '') >= cutoff]

    # drop HIBP RSS items when the same breach is in the API corpus (it always is)
    api_names = {hibp_name(e) for e in window if e['source'] == 'hibp_api'}
    window = [e for e in window
              if not (e['source'] == 'hibp_rss' and hibp_name(e) in api_names)]

    # google_news same-story collapse by normalized core title
    stories = {}
    for e in [e for e in window if e['source'] == 'google_news']:
        title = e.get('title', '')
        core = re.sub(r'\s*\[[^\]]+\]\s*$', '', title)
        outlet = (re.search(r'\[([^\]]+)\]\s*$', title) or [None, ''])[1] or ''
        key = re.sub(r'[^a-z0-9]+', '', core.lower())[:72]
        cur = stories.get(key)
        if cur is None or outlet_rank(outlet) < outlet_rank(cur[0]):
            stories[key] = (outlet, e, core)
    news_kept = {id(e) for _, e, _ in stories.values()}
    window = [e for e in window
              if not (e['source'] == 'google_news' and id(e) not in news_kept)]

    # --- build compact event list ---
    out_events = []
    for e in sorted(window, key=lambda x: x.get('date_published', ''), reverse=True):
        s = e['source']
        title = e.get('title', '')
        desc = ''
        if s == 'hibp_api':
            desc = (e.get('description') or '')[:300]
        elif s == 'google_news':
            core = re.sub(r'\s*\[[^\]]+\]\s*$', '', title)
            desc = (e.get('description') or '')[:300]
            if desc.lower().startswith(core.lower()[:60]):
                desc = ''  # description is just the headline repeated
        elif s == 'ca_doj':
            cells = (e.get('raw') or {}).get('cells') or []
            if cells:
                title = cells[0]
                rest = [c for c in cells[1:] if c and not is_date_like(c)]
                if rest:
                    desc = ' · '.join(rest)[:220]
        out_events.append(compact(e, title, desc))

    # --- payload ---
    payload = {
        'built': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'updated': max(e.get('ingested_at', '') for e in events) or now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'stats': {
            'events': n_total,
            'hibp': src.get('hibp_api', 0),
            'filings': src.get('ca_doj', 0),
            'ndItems': nd_items,
            'records': records_total,
        },
        'events': out_events,
    }
    js = ('window.BW_DATA = ' +
          json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
          .replace('<', '\\u003c') + ';')

    # --- bake (byte-level splice between persistent markers) ---
    html = TEMPLATE.read_bytes()
    s, e2 = html.find(START.encode()), html.find(END.encode())
    if s < 0 or e2 < 0:
        raise SystemExit('template markers not found — aborting')
    head, tail = html[:s + len(START)], html[e2:]
    html = head + b'\n' + js.encode('utf-8') + b'\n' + tail

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(html)

    print(f'archive: {n_total} events | window: {len(out_events)} '
          f'(last {WINDOW_DAYS}d) | payload: {len(js)//1024}KB | out: {len(html)//1024}KB')
    from collections import Counter
    c = Counter(e['s'] for e in out_events)
    print('window by source:', dict(c))
    print('stats:', payload['stats'])
    print(f'baked -> {OUT}')


if __name__ == '__main__':
    main()
