import hashlib
import html
import json
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urljoin
from xml.etree import ElementTree as ET

from . import config
from .fetch import http_get
from .schema import BreachEvent

# --- source endpoints (verified live 2026-09-07) -------------------------------
HIBP_API = 'https://haveibeenpwned.com/api/v3/breaches'          # keyless list endpoint
HIBP_FEED = 'https://feeds.feedburner.com/HaveIBeenPwnedLatestBreaches'
OPC_BASE = 'https://www.priv.gc.ca'
# OPC news search filtered to topic 51 (privacy breaches), newest first
OPC_NEWS = OPC_BASE + '/en/opc-news/news-and-announcements/?q%5b0%5d=51&o=d&Page={page}&Filter=True'
CAI_ACTUS_SITEMAP = 'https://www.cai.gouv.qc.ca/sitemaps-1-section-actualites-1-sitemap.xml'
CA_DOJ = 'https://oag.ca.gov/privacy/databreach/list'            # SB-24 registry

SITEMAP_NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


def _clean(s) -> str:
    return re.sub(r'\s+', ' ', html.unescape(s or '')).strip()


def _strip_html(s) -> str:
    return _clean(re.sub(r'<[^>]+>', ' ', s or ''))


def _cap_seen(seen: dict, cap: int = 4000) -> dict:
    """Trim oldest-inserted keys when a source's seen-set grows too large."""
    while len(seen) > cap:
        seen.pop(next(iter(seen)))
    return seen


def collect_hibp_api(cfg: dict, full: bool = False, max_pages: int = 3) -> tuple:
    """Full breach corpus from HIBP v3 (keyless). Cursor = latest AddedDate seen."""
    seen = cfg.setdefault('seen', {})
    cursor = cfg.get('cursor') or '1970-01-01T00:00:00Z'
    data = json.loads(http_get(HIBP_API, timeout=90))
    data.sort(key=lambda b: b.get('AddedDate', ''))
    events, new_cursor = [], cursor
    for b in data:
        name = b.get('Name', '')
        added = b.get('AddedDate', '')
        if not name or name in seen:
            continue
        if not full and added <= cursor:
            continue
        ev = BreachEvent(
            source='hibp_api',
            external_id=name,
            url=f'https://haveibeenpwned.com/Breach/{name}',
            title=_clean(b.get('Title') or name),
            date_published=added[:10],
            date_breach=(b.get('BreachDate') or '')[:10],
            records=int(b.get('PwnCount') or 0),
            data_classes=b.get('DataClasses') or [],
            description=_strip_html(b.get('Description') or ''),
            region='unknown',  # HIBP has no country field; geo tagging is phase 2
            raw={'domain': b.get('Domain', ''),
                 'is_verified': b.get('IsVerified'),
                 'is_sensitive': b.get('IsSensitive'),
                 'is_retired': b.get('IsRetired'),
                 'is_spam_list': b.get('IsSpamList')},
        )
        events.append(ev)
        seen[name] = 1
        if added > new_cursor:
            new_cursor = added
    cfg['cursor'] = new_cursor
    cfg['seen'] = _cap_seen(seen)
    return events, cfg


def collect_hibp_rss(cfg: dict, full: bool = False, max_pages: int = 3) -> tuple:
    """HIBP FeedBurner RSS - recent breaches with narrative descriptions."""
    seen = cfg.setdefault('seen', {})
    xml = http_get(HIBP_FEED)
    root = ET.fromstring(xml)
    events = []
    for it in root.iter('item'):
        link = _clean(it.findtext('link') or '')
        if not link or link in seen:
            continue
        title = _clean(it.findtext('title') or '')
        pub = _clean(it.findtext('pubDate') or '')
        desc = _strip_html(it.findtext('description') or '')
        d = ''
        m = re.search(r'\d{1,2} \w{3} \d{4}', pub)
        if m:
            try:
                d = datetime.strptime(m.group(0), '%d %b %Y').strftime('%Y-%m-%d')
            except ValueError:
                d = ''
        name = link.rstrip('/').rsplit('/', 1)[-1]
        mrec = re.search(r'([\d,]+) breached accounts', title)
        events.append(BreachEvent(
            source='hibp_rss',
            external_id=link,
            url=link,
            title=title[:160] or name,
            date_published=d,
            records=int(mrec.group(1).replace(',', '')) if mrec else 0,
            description=desc,
            region='unknown',
        ))
        seen[link] = 1
    cfg['seen'] = _cap_seen(seen, 2000)
    return events, cfg


def collect_opc(cfg: dict, full: bool = False, max_pages: int = 3) -> tuple:
    """OPC news search filtered to 'privacy breaches' topic (q[0]=51).

    NOTE: this is curated regulator output (investigations, statements,
    letters), NOT a per-incident registry - Canada does not publish one.
    """
    seen = cfg.setdefault('seen', {})
    events = []
    for page in range(1, 7):
        try:
            h = http_get(OPC_NEWS.format(page=page))
        except RuntimeError:
            break
        pairs = re.findall(
            r'href="(/en/opc-news/news-and-announcements/\d{4}/[^"]+)"[^>]*>([^<]+)<', h)
        dates = re.findall(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})"', h)
        if not pairs:
            break
        page_new = 0
        for i, (path, title) in enumerate(pairs):
            url = OPC_BASE + html.unescape(path)
            if url in seen:
                continue
            d = dates[i] if i < len(dates) else ''
            ev = BreachEvent(
                source='opc_news',
                external_id=url,
                url=url,
                title=_clean(title)[:200],
                date_published=d,
                description='OPC privacy-breach news item (investigation/statement/letter)',
                region='ca',
            )
            events.append(ev)
            seen[url] = 1
            page_new += 1
        if page_new == 0:
            break  # nothing new anywhere in this page -> later pages are older/seen
    cfg['seen'] = _cap_seen(seen, 3000)
    return events, cfg


def collect_cai(cfg: dict, full: bool = False, max_pages: int = 3) -> tuple:
    """Quebec CAI news via sitemap lastmod. CAI publishes no per-incident
    registry either - this catches Law 25 / privacy news items."""
    seen = cfg.setdefault('seen', {})
    xml = http_get(CAI_ACTUS_SITEMAP)
    root = ET.fromstring(xml)
    entries = []
    for u in root.findall('s:url', SITEMAP_NS):
        loc = (u.findtext('s:loc', default='', namespaces=SITEMAP_NS) or '').strip()
        lm = (u.findtext('s:lastmod', default='', namespaces=SITEMAP_NS) or '').strip()[:10]
        if loc:
            entries.append((loc, lm))
    events = []
    for loc, lm in entries:
        if loc in seen:
            continue
        slug = loc.rstrip('/').rsplit('/', 1)[-1]
        title = ' '.join(w.capitalize() for w in re.split(r'[-_]+', slug))
        ev = BreachEvent(
            source='cai_news',
            external_id=loc,
            url=loc,
            title=title[:160],
            date_published=lm,
            description='Quebec CAI (Law 25) news item',
            region='qc',
        )
        events.append(ev)
        seen[loc] = 1
    cfg['seen'] = _cap_seen(seen, 3000)
    return events, cfg


def collect_ca_doj(cfg: dict, full: bool = False, max_pages: int = 3) -> tuple:
    """California DOJ SB-24 data security breach registry (Drupal table).

    Default: scan `max_pages` newest pages. --full: crawl until rows run out
    (~105 pages). Rows deduped by content hash."""
    seen = cfg.setdefault('seen', {})
    events = []
    pages = 250 if full else max_pages
    for page in range(pages):
        url = CA_DOJ if page == 0 else f'{CA_DOJ}?page={page}'
        try:
            h = http_get(url)
        except RuntimeError:
            break
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', h, re.S)
        if not rows:
            break
        page_new = 0
        for row in rows:
            if '<th' in row:
                continue
            cells = [_clean(re.sub('<[^>]+>', ' ', c))
                     for c in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)]
            cells = [c for c in cells if c]
            if not cells:
                continue
            text = ' | '.join(cells)
            if len(text) < 4:
                continue
            eid = hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]
            if eid in seen:
                continue
            link = re.search(r'href="([^"]+)"', row)
            href = urljoin(CA_DOJ, link.group(1)) if link else url
            d = ''
            m = re.search(r'(\d{4}-\d{2}-\d{2}|[A-Z][a-z]+ \d{1,2}, \d{4})', text)
            if m:
                raw = m.group(1)
                try:
                    d = raw if '-' in raw else datetime.strptime(raw, '%B %d, %Y').strftime('%Y-%m-%d')
                except ValueError:
                    d = ''
            ev = BreachEvent(
                source='ca_doj',
                external_id=eid,
                url=href,
                title=text[:200],
                date_published=d,
                description='California DOJ SB-24 data security breach notice',
                region='us',
                raw={'cells': cells},
            )
            events.append(ev)
            seen[eid] = 1
            page_new += 1
        if page_new == 0:
            break  # entire page already seen -> later pages are older
    cfg['seen'] = _cap_seen(seen, 6000)
    return events, cfg


def _gn_url(qcfg: dict) -> str:
    return 'https://news.google.com/rss/search?' + urlencode({
        'q': qcfg['q'], 'hl': qcfg['hl'], 'gl': qcfg['gl'], 'ceid': qcfg['ceid']})


def _norm_key(title: str) -> str:
    t = title.lower()
    for suf in config.TITLE_SUFFIX_NOISE:
        t = t.replace(suf, ' ')
    return re.sub(r'[^a-z0-9]+', '', t)[:80]


def collect_google_news(cfg: dict, full: bool = False, max_pages: int = 3) -> tuple:
    """Google News RSS - the announcement/no-dump leg.

    Catches breaches the day they are disclosed (press releases, regulator
    statements), including Canadian orgs that never appear in dumps. Noise is
    filtered in config (NOISE_RE); syndicated duplicates collapse via a
    normalized-title key shared across queries and runs."""
    seen_links = cfg.setdefault('seen', {})
    seen_titles = cfg.setdefault('seen_titles', {})
    cutoff = (datetime.utcnow() - timedelta(days=45)).strftime('%Y-%m-%d')
    events = []
    run_titles = set()
    for qcfg in config.NEWS_QUERIES:
        try:
            xml = http_get(_gn_url(qcfg), timeout=30)
        except RuntimeError:
            continue
        root = ET.fromstring(xml)
        for it in root.iter('item'):
            link = _clean(it.findtext('link') or '')
            if not link or link in seen_links:
                continue
            title_raw = _clean(it.findtext('title') or '')
            title = re.sub(r'\s+-\s+[^-]+$', '', title_raw).strip()  # strip trailing outlet
            outlet = _clean(it.findtext('source') or '')
            if not outlet:
                m = re.search(r'-\s+([^-]+)$', title_raw)
                outlet = m.group(1).strip() if m else ''
            d = ''
            pub = _clean(it.findtext('pubDate') or '')
            if pub:
                try:
                    d = parsedate_to_datetime(pub).strftime('%Y-%m-%d')
                except (TypeError, ValueError):
                    d = ''
            low = title.lower()
            if config.NOISE_RE.search(low):
                continue
            if not config.BREACH_INDICATOR_RE.search(low):
                continue
            if cutoff and d and d < cutoff:
                continue
            key = _norm_key(title)
            if key in run_titles:
                continue
            if not full and key in seen_titles:
                continue
            desc = _strip_html(it.findtext('description') or '')[:400]
            ev = BreachEvent(
                source='google_news',
                external_id=link,
                url=link,
                title=f'{title} [{outlet}]' if outlet else title,
                date_published=d,
                description=desc,
                region=qcfg['region'],
                raw={'query': qcfg['name'], 'outlet': outlet},
            )
            events.append(ev)
            run_titles.add(key)
            seen_links[link] = 1
            seen_titles[key] = d or ''
    cfg['seen'] = _cap_seen(seen_links, 6000)
    cfg['seen_titles'] = _cap_seen(seen_titles, 6000)
    return events, cfg


SOURCES = {
    'hibp_api': collect_hibp_api,
    'hibp_rss': collect_hibp_rss,
    'opc_news': collect_opc,
    'cai_news': collect_cai,
    'ca_doj': collect_ca_doj,
    'google_news': collect_google_news,
}
