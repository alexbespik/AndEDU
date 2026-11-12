// node --test "desktop/*.test.cjs"
const test = require('node:test');
const assert = require('node:assert');
const vm = require('node:vm');
const { buildStartPage, parseStartupChunk, renderLog } = require('./startpage.cjs');

test('the start page has no script, a strict CSP and an escaped title', () => {
  const html = buildStartPage();
  assert.doesNotMatch(html, /<script/i);
  assert.match(html, /<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">/);
  assert.match(html, /<title>Starting &amp;\.edu…<\/title>/);
  assert.doesNotMatch(html, /&\.edu/);  // every & is escaped
  assert.match(html, /role="progressbar"[^>]*aria-busy="true"/);
  assert.match(html, /<ol id="log" role="log" aria-live="polite"><\/ol>/);
  assert.match(html, /prefers-color-scheme: dark/);
  assert.match(html, /prefers-reduced-motion: reduce/);
  assert.doesNotMatch(html, /https?:\/\//);  // nothing from the network
});

test('a line split across chunks is kept until it ends', () => {
  let r = parseStartupChunk('[startup] Settings read\n[startup] Loading the', '');
  assert.deepStrictEqual(r.lines, ['Settings read']);
  assert.strictEqual(r.carry, '[startup] Loading the');
  r = parseStartupChunk(' lesson engine\n', r.carry);
  assert.deepStrictEqual(r.lines, ['Loading the lesson engine']);
  assert.strictEqual(r.carry, '');
});

test('only [startup] lines are kept', () => {
  const text = 'INFO: Started server\n  [startup] indented\n[startup]no space\nTraceback ...\n[startup] Ready\n';
  assert.deepStrictEqual(parseStartupChunk(text, '').lines, ['Ready']);
});

test('control characters are removed and lines are capped', () => {
  assert.deepStrictEqual(parseStartupChunk('[startup] a\u001b[31mb\u0007c\r\n', '').lines, ['a[31mbc']);
  const long = parseStartupChunk(`[startup] ${'x'.repeat(500)}\n`, '').lines[0];
  assert.strictEqual(long.length, 120);
  assert.ok(parseStartupChunk('[startup] ' + 'y'.repeat(10000), '').carry.length <= 4096);
});

test('renderLog replaces the list with text-only items', () => {
  const made = [];
  const list = { children: ['old'], replaceChildren(...items) { this.children = items; } };
  const document = {
    getElementById: (id) => (id === 'log' ? list : null),
    createElement(tag) {
      const el = { tag, textContent: '' };
      Object.defineProperty(el, 'innerHTML', { set() { throw new Error('innerHTML used'); } });
      made.push(el);
      return el;
    },
  };
  // run the serialized function the way main.cjs does, with only the fake document in scope
  vm.runInNewContext(`(${renderLog.toString()})(${JSON.stringify(['one', '<b>two</b>'])})`, { document });
  assert.deepStrictEqual(list.children.map((el) => [el.tag, el.textContent]), [['li', 'one'], ['li', '<b>two</b>']]);
  assert.strictEqual(made.length, 2);
});
