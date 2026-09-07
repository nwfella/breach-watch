"""BreachWatch: daily breach monitoring collector (Canada + US focus).

Stdlib-only so it runs anywhere (python 3.9+) without pip installs.
Sources (all verified live 2026-09-07):
  - hibp_api : HaveIBeenPwned v3 /breaches  (keyless list endpoint, 1034 breaches)
  - hibp_rss : HIBP FeedBurner RSS (narrative descriptions)
  - opc_news : OPC filtered news search (topic=51 privacy breaches) - curated regulator action
  - cai_news : Quebec CAI news sitemap (Law 25 / privacy items)
  - ca_doj   : California DOJ SB-24 data security breach registry (Drupal table, ~105 pages)
"""
