"""Tunable configuration for the Google News (no-dump announcement) leg."""

import re

# --- Google News RSS queries -------------------------------------------------
# Each: name (short id), region tag, locale params, raw query.
NEWS_QUERIES = [
    {
        'name': 'ca_breach',
        'region': 'ca',
        'hl': 'en-CA', 'gl': 'CA', 'ceid': 'CA:en',
        'q': '"data breach" Canada',
    },
    {
        'name': 'ca_incident',
        'region': 'ca',
        'hl': 'en-CA', 'gl': 'CA', 'ceid': 'CA:en',
        'q': '"cyber incident" OR "cybersecurity incident" OR "security incident" Canada',
    },
    {
        'name': 'ca_orgs',
        'region': 'ca',
        'hl': 'en-CA', 'gl': 'CA', 'ceid': 'CA:en',
        'q': None,  # built from CA_ORG_WATCHLIST below
    },
    {
        'name': 'qc_fr',
        'region': 'qc',
        'hl': 'fr-CA', 'gl': 'CA', 'ceid': 'CA:fr',
        'q': '"renseignements personnels" (fuite OR piratage OR incident)',
    },
]

# Consumer-facing Canadian orgs most likely to disclose breaches (watchlist).
CA_ORG_WATCHLIST = [
    'Bell', 'Rogers', 'Telus', 'Shopify', 'Air Canada', 'WestJet',
    'Canadian Tire', 'Loblaw', 'Shoppers Drug Mart', 'Desjardins',
    'TD Bank', 'RBC', 'Scotiabank', 'BMO', 'CIBC', 'Canada Post',
    'LCBO', 'Hydro One', 'BC Hydro', 'Sun Life', 'Manulife',
    'Canada Life', 'SickKids', 'Air Transat',
]


def org_watch_query() -> str:
    orgs = ' OR '.join(f'"{o}"' for o in CA_ORG_WATCHLIST)
    return f'({orgs}) (breach OR hacked OR ransomware OR leaked OR stolen)'


for _q in NEWS_QUERIES:
    if _q['q'] is None:
        _q['q'] = org_watch_query()

# --- filters -----------------------------------------------------------------
# Items whose title matches these are derivative noise, not new events.
NOISE_RE = re.compile(
    r'how to|tips for|protect yourself|what to do|here.s how|here.s what'
    r'|you could be owed|eligible for|compensation|check if you qualify'
    r'|claims? (?:now )?open|claim deadline|deadline|submit your claim'
    r'|days? left|last day|settlement|class action|payout|owed up to'
    r'|apps? for|ibm report|costs mount|cyber insurance|trends|insights'
    r'|costs hit record|cost of data breaches|record high|part [0-9]'
    r'|privacy breach insights|eligible canadians|claim up to|what do do now'
)

# Items must mention a breach/security indicator.
BREACH_INDICATOR_RE = re.compile(
    r'breach|leak|leaked|hack|hacked|hacking|ransomware|exposed|stolen'
    r'|cyberattack|cyber attack|cyber incident|security incident'
    r'|privacy incident|fuite|piratage|violation|atteinte|incident de'
)

# Phrases stripped from titles before the dedupe key is computed, so the same
# story from many outlets collapses to one event.
TITLE_SUFFIX_NOISE = [
    "here's how to check if you qualify", "here's what to know",
    'canadians could be part of class-action lawsuit filed against',
    'you could be owed', 'was your', 'submit your claim now for',
]
