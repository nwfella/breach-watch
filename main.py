import argparse
from pathlib import Path

from breachwatch.digest import render
from breachwatch.sources import SOURCES
from breachwatch.store import Store

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'


def main() -> None:
    ap = argparse.ArgumentParser(description='BreachWatch collector - daily breach monitoring')
    ap.add_argument('--full', action='store_true',
                    help='backfill full history (automatic on very first run)')
    ap.add_argument('--max-pages', type=int, default=3,
                    help='CA DOJ pages to scan per default run (default 3)')
    ap.add_argument('--limit', type=int, default=0,
                    help='print only first N digest lines (0 = all)')
    args = ap.parse_args()

    store = Store(DATA)
    first_run = not store.state
    do_full = args.full or first_run

    all_new, stats = [], []
    for name, fn in SOURCES.items():
        cfg = store.state.setdefault(name, {'cursor': '', 'seen': {}})
        try:
            events, cfg2 = fn(cfg, full=do_full, max_pages=args.max_pages)
        except Exception as e:  # keep going even if one source breaks
            stats.append(f'[FAIL] {name}: {type(e).__name__}: {e}')
            continue
        store.state[name] = cfg2
        new = [e.to_dict() for e in events]
        store.append_events(new)
        all_new.extend(new)
        stats.append(f'[ok]   {name}: {len(new):>5} new')
    store.save_state()

    print('--- source status ---')
    print('\n'.join(stats))
    if first_run:
        print(f'\n=== FIRST RUN: baseline ingest complete, {len(all_new)} events archived ===')
        print(render(all_new[:15], header='Sample of ingested events:'))
    else:
        print()
        print(render(all_new))


if __name__ == '__main__':
    main()
