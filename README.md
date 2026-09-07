# BreachWatch

Daily breach monitor for Canada/US breach news, with plain-English reporting.
Free forever + donate/affiliate model (no subscription).

## Status

Skeleton v0.2 - collectors verified against **live sources** on 2026-09-07.
Google News no-dump leg added; 45-day news backfill archived (28 events).

## What the live-source test found

| Source | Endpoint | What it gives | Verified |
|---|---|---|---|
| HIBP API v3 | `api/v3/breaches` | Full dump-indexed corpus (1,034 breaches), **keyless** | ✅ 200, parsed |
| HIBP RSS | FeedBurner | Recent breaches + narrative descriptions | ✅ 200, parsed |
| OPC (federal) | news search `q[0]=51` | **Curated** regulator items (investigations, statements) | ✅ 200, parsed |
| CAI (Quebec) | news sitemap | Law 25 / privacy news items | ✅ sitemap index confirmed |
| CA DOJ | `/privacy/databreach/list` | SB-24 registry, ~105 pages of notices | ✅ 200, parsed |
| Google News RSS | `news.google.com/rss/search` | **No-dump announcements**: CA orgs, regulator news, press coverage (4 queries, EN+FR, org watchlist) | ✅ live, 28 events backfilled |
| OIPC Alberta | - | **Down / unreachable** from this network (000/56) | ❌ |
| Maine AG registry | agviewer | Old URLs 404; registry moved behind site search | ⏳ phase 2 |

**The honest Canada finding:** neither the OPC nor Quebec's CAI publishes a
real-time per-incident public registry. Canada's model is *report to the
regulator, regulator publishes curated news + annual aggregates*. So the
"no-dump, announcement-based" wedge rests on:
1. OPC breach-topic news (sparse but high-signal - last item May 2026)
2. CAI/Quebec Law 25 news
3. Company press releases (phase 2: news-RSS trackers)
4. HIBP for the dump side (the only fully machine-readable corpus)

## Run

```bash
python main.py            # incremental: new events since last run (auto-full on first run)
python main.py --full     # force full backfill
python main.py --max-pages 5   # CA DOJ pages per run
```

Output: per-source status + digest of new events. Events append to
`data/events.jsonl`; dedupe state in `data/state.json` (per-source seen sets).

Stdlib only - no pip installs. Python 3.9+.

## Roadmap

- **Phase 2 - no-dump leg (in progress):** Google News trackers **done** -
  4 queries (CA breaches, CA incidents, 24-org CA watchlist, Quebec FR/Law 25)
  with noise filters and same-story dedupe in `config.py`. Remaining: Maine AG
  registry (new endpoint), HHS OCR (US healthcare), CISA; region/geo inference
  for HIBP items (domain + description heuristics) so the digest can filter
  "US/Canada-relevant".
- **Phase 3 - product:** entity resolution across sources (same breach from
  HIBP + CA DOJ + OPC), plain-English LLM digests, daily email delivery
  (Hermes cron), per-breach landing pages for organic capture.
- **Monetization:** free forever. Donations (OpenCollective), affiliate
  placements (password managers etc.), later optional paid API/research tier.
