// jsdom boot verification for the baked BreachWatch site.
// Loads out/index.html with scripts enabled, asserts the embedded payload
// exists, the synchronous render populated stats + the event list, and that
// no error was thrown during execution.
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

assert(typeof window.BW_DATA === 'object' && window.BW_DATA !== null, 'embedded BW_DATA payload present');
const D = window.BW_DATA;
assert(Array.isArray(D.events) && D.events.length > 100, `events baked (${D.events.length})`);
assert(D.stats.events > 6000, `stats.events=${D.stats.events}`);

const stats = doc.querySelectorAll('#statsRow .stat .v');
assert(stats.length === 5, `5 stat cards rendered (got ${stats.length})`);
assert(doc.getElementById('updatedVal').textContent !== '—', 'updated chip filled: ' + doc.getElementById('updatedVal').textContent);

const cards = doc.querySelectorAll('#list .ev');
assert(cards.length > 0, `${cards.length} event cards in default (14d) view`);
const countLbl = doc.getElementById('countLbl').textContent;
console.log('count label: ' + countLbl);
assert(/events?/.test(countLbl), 'count label rendered');

// first card should be a real headline with a link
const first = cards[0];
assert(first.querySelector('h3 a'), 'first card has title link');
assert(first.querySelector('.rtag'), 'first card has region tag');
console.log('first card: ' + first.querySelector('h3').textContent.trim().slice(0, 90));

// interaction smoke: click "Canada" region chip and re-check list re-rendered
const caChip = Array.from(doc.querySelectorAll('#regionChips .chip')).find(c => c.getAttribute('data-r') === 'ca');
caChip.click();
const caCards = doc.querySelectorAll('#list .ev');
const allCa = Array.from(caCards).every(c => c.querySelector('.rtag').textContent.trim() !== 'United States');
assert(caCards.length > 0 && allCa, `Canada filter works (${caCards.length} cards)`);

// search smoke
const q = doc.getElementById('q');
q.value = 'thomson reuters';
q.dispatchEvent(new window.Event('input', { bubbles: true }));
const searchCards = doc.querySelectorAll('#list .ev');
assert(searchCards.length >= 1, `search finds Thomson Reuters (${searchCards.length} cards)`);

console.log('boot errors: ' + (errors.length ? errors.map(String).join(' | ') : 'none'));
assert(errors.length === 0, 'no JS errors during boot');
console.log(process.exitCode ? '\nVERIFY FAILED' : '\nVERIFY PASSED');
