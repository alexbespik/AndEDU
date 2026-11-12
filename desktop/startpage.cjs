// The start page the desktop window shows while the backend starts (and again on every relaunch):
// a progress bar and the backend's latest "[startup] ..." log lines. The page has no script of its own;
// main.cjs fills the list with renderLog through executeJavaScript.
const PREFIX = '[startup] ';
const MAX_LINE = 120;
const MAX_CARRY = 4096;  // a partial line longer than this is cut: only its first MAX_LINE characters are shown

// Colours and fonts follow src/styles/lab.css (light and dark tokens); system fonts only, nothing from the network.
function buildStartPage() {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<meta name="color-scheme" content="light dark">
<title>Starting &amp;.edu…</title>
<style>
  :root {
    --paper: #f1f0ea; --surface: #ffffff; --ink: #0b0f0d; --muted: #4f5953; --rule: #cbc7b9;
    --accent: #0e4a37; --accent-tint: #e2ebe5; --gold: #c9a24a;
    --font-body: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    --font-mono: "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --paper: #050806; --surface: #0e1411; --ink: #f4f7f5; --muted: #9eada5; --rule: #2b3b34;
      --accent: #5aae8b; --accent-tint: #142a21; --gold: #e0bb62;
    }
  }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--paper); color: var(--ink); font: 15px/1.5 var(--font-body);
    display: grid; place-items: center;
  }
  main {
    width: min(520px, 86vw); padding: 32px; background: var(--surface);
    border: 1px solid var(--rule); border-top: 3px solid var(--gold); border-radius: 6px;
  }
  h1 { margin: 0 0 16px; font: 600 20px/1.3 var(--font-mono); letter-spacing: -0.01em; }
  .bar { position: relative; height: 6px; overflow: hidden; border-radius: 3px; background: var(--accent-tint); }
  .bar::before {
    content: ""; position: absolute; top: 0; bottom: 0; left: -40%; width: 40%;
    border-radius: 3px; background: var(--accent); animation: slide 1.4s ease-in-out infinite;
  }
  @keyframes slide { from { left: -40%; } to { left: 100%; } }
  @media (prefers-reduced-motion: reduce) {
    .bar::before { animation: none; left: 0; width: 100%; opacity: 0.6; }
  }
  ol {
    list-style: none; margin: 16px 0 0; padding: 0; min-height: 9em;
    font: 12px/1.5 var(--font-mono); color: var(--muted);
  }
  li { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  li:last-child { color: var(--ink); }
</style>
</head>
<body>
<main>
  <h1>Starting &amp;.edu…</h1>
  <div class="bar" role="progressbar" aria-label="Starting &amp;.edu" aria-busy="true"></div>
  <ol id="log" role="log" aria-live="polite"></ol>
</main>
</body>
</html>
`;
}

// Takes a new piece of backend.log; returns the "[startup] " lines it completes (prefix stripped, control
// characters removed, at most MAX_LINE characters each) and the unfinished last line to pass back next time.
function parseStartupChunk(text, carry) {
  const parts = (String(carry || '') + String(text || '')).split('\n');
  const rest = parts.pop();
  const lines = [];
  for (const part of parts) {
    if (!part.startsWith(PREFIX)) continue;
    const line = part.slice(PREFIX.length).replace(/[\u0000-\u001f\u007f-\u009f]/g, '').trim().slice(0, MAX_LINE);
    if (line) lines.push(line);
  }
  return { lines, carry: rest.slice(0, MAX_CARRY) };
}

// Runs in the start page (serialized with toString), so it must not use anything from this module.
/* global document */
function renderLog(lines) {
  const list = document.getElementById('log');
  if (!list) return;
  const items = [];
  for (const text of Array.isArray(lines) ? lines : []) {
    const item = document.createElement('li');
    item.textContent = String(text);
    items.push(item);
  }
  list.replaceChildren(...items);
}

module.exports = { buildStartPage, parseStartupChunk, renderLog };
