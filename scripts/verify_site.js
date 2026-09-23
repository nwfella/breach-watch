// jsdom boot verification for the baked BreachWatch site.
// Loads out/index.html with scripts enabled, asserts the embedded payload
// exists, the synchronous render populated stats + the event list, and that
// no error was thrown during execution.
//
// Every assertion is derived from the payload at run time, never from a
// hardcoded headline: a fixture like "search finds Thomson Reuters" fails the
// day that incident ages past the default time range, which is exactly how the
// daily cron started failing on 2026-09-22.
//
// Usage: npm i -D jsdom (once) && node scripts/verify_site.js
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const html = fs.readFileSync(path.join(__dirname, '..', 'out', 'index.html'), 'utf-8');
const errors = [];
const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  beforeParse(window) {
    window.addEventListener('error', (e) => errors.push(String(e.error || e.message)));
  },
});
const { window } = dom;
const doc = window.document;

function assert(cond, msg) {
  if (!cond) { console.error('FAIL: ' + msg); process.exitCode = 1; }
  else { console.log('ok: ' + msg); }
}

const cards = () => doc.querySelectorAll('#list .ev');
const label = () => doc.getElementById('countLbl').textContent;
const countIn = () => {
  const m = /^(\d+)\s+events?\b/.exec(label().trim());
  return m ? +m[1] : null;
};

assert(typeof window.BW_DATA === 'object' && window.BW_DATA !== null, 'embedded BW_DATA payload present');
const D = window.BW_DATA;
assert(Array.isArray(D.events) && D.events.length > 100, `events baked (${D.events.length})`);
assert(D.stats.events > 6000, `stats.events=${D.stats.events}`);

const stats = doc.querySelectorAll('#statsRow .stat .v');
assert(stats.length === 5, `5 stat cards rendered (got ${stats.length})`);
assert(doc.getElementById('updatedVal').textContent !== '—', 'updated chip filled: ' + doc.getElementById('updatedVal').textContent);

// default view: the list and the count label must agree (paired UI)
assert(cards().length > 0, `${cards().length} event cards in the default 14d view`);
assert(countIn() === cards().length,
  `count label agrees with the list (${countIn()} vs ${cards().length} cards)`);
console.log('count label: ' + label());

// first card should be a real headline with a link
const first = cards()[0];
assert(first.querySelector('h3 a'), 'first card has title link');
assert(first.querySelector('.rtag'), 'first card has region tag');
console.log('first card: ' + first.querySelector('h3').textContent.trim().slice(0, 90));

// interaction smoke: region chip filters, then we put the filter back
const chip = (r) => Array.from(doc.querySelectorAll('#regionChips .chip'))
  .find((c) => c.getAttribute('data-r') === r);
const caChip = chip('ca');
caChip.click();
const caCards = cards();
const allCa = Array.from(caCards).every((c) => c.querySelector('.rtag').textContent.trim() !== 'United States');
assert(caCards.length > 0 && allCa, `Canada filter works (${caCards.length} cards)`);
const allChip = chip('all');
assert(!!allChip, 'region "all" chip present (needed to reset between checks)');
allChip.click();
assert(countIn() === cards().length, `count label agrees after resetting the region filter (${countIn()}/${cards().length})`);

// search must reach the whole baked window, not just the default range. Pick a
// term from a payload event that is definitively older than the default view,
// so this check can never age out the way the old fixture did.
const typeIn = (value) => {
  const q = doc.getElementById('q');
  q.value = value;
  q.dispatchEvent(new window.Event('input', { bubbles: true }));
};
const rangeDays = +doc.getElementById('rangeSel').value || 14;
const cut = new Date();
cut.setDate(cut.getDate() - rangeDays);
const cutoff = cut.toISOString().slice(0, 10);
const older = D.events.filter((e) => e.d && e.d < cutoff);
assert(older.length > 0, `${older.length} payload events sit outside the ${rangeDays}-day default view`);

const STOP = new Set(['breach', 'breaches', 'data', 'exposed', 'cyber', 'attack', 'report', 'reports', 'incident', 'million']);
const freq = new Map();
for (const e of D.events) {
  for (const w of new Set(String(e.t || '').toLowerCase().match(/[a-z]{6,}/g) || [])) {
    freq.set(w, (freq.get(w) || 0) + 1);
  }
}
let term = null;
for (const e of older) {
  for (const w of String(e.t || '').toLowerCase().match(/[a-z]{6,}/g) || []) {
    if (!STOP.has(w) && (freq.get(w) || 99) <= 3) { term = w; break; }
  }
  if (term) break;
}
assert(!!term, `picked a distinctive search term from an out-of-range event (${term})`);

if (term) {
  typeIn(term);
  const hits = cards();
  assert(hits.length >= 1, `search "${term}" finds a file past the ${rangeDays}-day range (${hits.length} cards)`);
  const allMatch = Array.from(hits).every((c) => c.textContent.toLowerCase().includes(term));
  assert(allMatch, 'every search hit actually contains the term');
  assert(/search covers the full archive/.test(label()), 'search reports its scope: ' + label());
  assert(/outside the last \d+ days/.test(label()),
    'the out-of-range hits are counted out loud, not hidden: ' + label());
  assert(countIn() === hits.length, `count label agrees with the search results (${countIn()}/${hits.length})`);

  // negative control: a query with no possible match must empty the list cleanly
  typeIn('zzqqxxnosuchbreach');
  assert(cards().length === 0, 'nonsense query returns no cards');
  assert(/^0 events/.test(label()), 'count label reads 0 for a nonsense query: ' + label());
  assert(/Nothing in the archive matches/.test(doc.getElementById('list').textContent),
    'empty state names the failed query instead of blaming the filters');

  // and clearing the search restores the bounded default view
  typeIn('');
  assert(!/search covers/.test(label()), 'clearing the query drops the search scope note: ' + label());
  assert(countIn() === cards().length, `list and label agree after clearing the search (${countIn()}/${cards().length})`);
}

console.log('boot errors: ' + (errors.length ? errors.map(String).join(' | ') : 'none'));
assert(errors.length === 0, 'no JS errors during boot');
console.log(process.exitCode ? '\nVERIFY FAILED' : '\nVERIFY PASSED');
