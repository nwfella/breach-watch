"""BreachWatch daily refresh: collect -> bake -> verify -> deploy (gh-pages).

Runs the collector against live sources, rebuilds the static site from the
updated archive, verifies the baked page boots (jsdom), and pushes to the
gh-pages branch ONLY when the artifact actually changed. Stdout is the
no_agent cron report; exit non-zero on any failure.

Deploy target: a shallow gh-pages working clone (breach-watch-pages).
"""
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGES = Path(os.environ.get('BW_PAGES_CLONE', r'C:/Users/homee/projects/breach-watch-pages'))
PAGES_URL = 'https://github.com/nwfella/breach-watch.git'

ENV = os.environ.copy()
ENV['GIT_TERMINAL_PROMPT'] = '0'


def run(cmd, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          cwd=cwd or REPO, env=ENV, encoding='utf-8', errors='replace')


def fail(msg: str, detail: str = '') -> None:
    print(f'ERROR: {msg}')
    if detail:
        print(detail[-3000:])
    sys.exit(1)


def main() -> None:
    print(f'BreachWatch daily refresh — {datetime.now():%Y-%m-%d %H:%M %Z}')

    # 1) collect
    print('collecting…')
    p = run([sys.executable, '-u', 'main.py'])
    if p.returncode != 0:
        fail('collector exited non-zero', p.stdout + p.stderr)
    new_total = 0
    for line in p.stdout.splitlines():
        line = line.strip()
        if line.startswith('[ok]') or line.startswith('[FAIL]'):
            print('  ' + line)
        m = re.search(r'\[ok\]\s+\w+:\s+(\d+) new', line)
        if m:
            new_total += int(m.group(1))
    print(f'  new events this run: {new_total}')

    # 2) bake
    print('baking…')
    p = run([sys.executable, '-u', 'scripts/build_site.py'])
    if p.returncode != 0:
        fail('build_site failed', p.stdout + p.stderr)
    bake = [l for l in p.stdout.splitlines() if 'baked' in l.lower() or 'window:' in l]
    for l in bake[-2:]:
        print('  ' + l.strip())

    # 3) verify (jsdom boot test) — never deploy an unverified artifact
    print('verifying…')
    p = run(['node', 'scripts/verify_site.js'])
    if p.returncode != 0:
        fail('site verification FAILED — not deploying', p.stdout + p.stderr)
    vok = [l for l in p.stdout.splitlines() if l.startswith('ok:')]
    print(f'  verify passed ({len(vok)} checks)')

    # 4) deploy — only when the artifact changed
    html = (REPO / 'out' / 'index.html').read_bytes()
    target = PAGES / 'index.html'
    if target.exists() and target.read_bytes() == html:
        print('deploy: no change — site already current')
        return
    if not PAGES.exists():
        print('  cloning gh-pages worktree…')
        p = run(['git', 'clone', '-q', '-b', 'gh-pages', '--depth', '1', PAGES_URL], cwd=PAGES.parent)
        if p.returncode != 0:
            fail('could not clone gh-pages worktree', p.stdout + p.stderr)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(html)
    msg = f'site: daily refresh {datetime.now():%Y-%m-%d}'
    p = run(['git', 'add', 'index.html'], cwd=PAGES)
    p = run(['git', 'commit', '-q', '-m', msg], cwd=PAGES)
    if p.returncode != 0:
        fail('deploy commit failed', p.stdout + p.stderr)
    p = run(['git', 'push', '-q', 'origin', 'gh-pages'], cwd=PAGES)
    if p.returncode != 0:
        fail('deploy push failed', p.stdout + p.stderr)
    print(f'deploy: pushed ({msg})')


if __name__ == '__main__':
    main()
