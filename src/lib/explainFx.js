// Visual effects for one step of the "Explain it to me" walkthrough. Everything is classes on elements that are
// already on the page plus a CSS Custom Highlight for the phrase: React's text nodes are never changed. Each call
// returns a cleanup that removes every class and timer it added. Styles: the "== explain ==" block in lab.css.

export const ANIMATIONS = ['pulse', 'underline', 'zoom', 'reveal_steps', 'trace', 'node_step'];
const HIGHLIGHT = 'explain-phrase';

export const prefersReducedMotion = () => Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

/**
 * A Range over the first case-insensitive match of phrase in el's visible text (whitespace collapsed), or null.
 * KaTeX's hidden MathML copy is skipped; each character is lowercased on its own, so map stays one entry per character
 * even when lowercasing changes the length (e.g. "İ").
 */
function phraseRange(el, phrase) {
  const want = String(phrase || '').replace(/\s+/g, ' ').trim().toLowerCase();
  if (!want) return null;
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement?.closest('.katex-mathml') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  const map = [];
  let text = '';
  let space = true;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    for (let i = 0; i < node.data.length; i += 1) {
      const ws = /\s/.test(node.data[i]);
      if (ws && space) continue;
      const low = ws ? ' ' : node.data[i].toLowerCase();
      text += low;
      for (let k = 0; k < low.length; k += 1) map.push([node, i]);
      space = ws;
    }
  }
  const at = text.indexOf(want);
  if (at < 0) return null;
  const [startNode, startOffset] = map[at];
  const [endNode, endOffset] = map[at + want.length - 1];
  const range = document.createRange();
  range.setStart(startNode, startOffset);
  range.setEnd(endNode, endOffset + 1);
  return range;
}

export function clearPhrase() {
  try { window.CSS?.highlights?.delete(HIGHLIGHT); } catch { /* no Highlight API */ }
}

function highlightPhrase(el, phrase) {
  if (!phrase || !window.CSS?.highlights || typeof window.Highlight !== 'function') return;
  try {
    const range = phraseRange(el, phrase);
    if (range) window.CSS.highlights.set(HIGHLIGHT, new window.Highlight(range));
  } catch (e) {  // a missing phrase light never stops the step
    console.warn('Walkthrough highlight failed', e);
  }
}

/** Lights up parts one after another: on = the current part, seen = parts already passed. */
function stepThrough(parts, interval, { on, seen, timers }) {
  parts.forEach((p, i) => {
    timers.push(setTimeout(() => {
      parts[i - 1]?.classList.remove(on);
      if (seen) parts[i - 1]?.classList.add(seen);
      p.classList.add(on);
    }, i * interval));
  });
  timers.push(setTimeout(() => {
    parts[parts.length - 1]?.classList.remove(on);
    if (seen) parts[parts.length - 1]?.classList.add(seen);
  }, parts.length * interval));
}

function revealParts(el) {
  if (el.matches('table')) return [...el.querySelectorAll('tbody tr')];
  if (el.matches('li')) return [...el.querySelectorAll(':scope > ul > li, :scope > ol > li')];
  return [...el.querySelectorAll('.katex-html > .base')];  // equation or key formula: one part per line/term group
}

function traceTerms(el) {
  return [...el.querySelectorAll('.katex-html > .base > span')].filter((s) => !s.classList.contains('strut') && s.textContent.trim());
}

/**
 * Spotlights el for one step: dims the page around it, pops it, lights the phrase and plays the animation over
 * about durationMs. With reduced motion only the spotlight and the phrase stay (no movement, no timers).
 */
export function showStep(el, { highlight, animation, durationMs = 6000, reduced = prefersReducedMotion() } = {}) {
  if (!el) return () => {};
  const timers = [];
  const touched = new Set([el]);
  const add = (node, ...cls) => { node.classList.add(...cls); touched.add(node); };
  const fx = ['fx-pulse', 'fx-underline', 'fx-zoom', 'fx-dim', 'fx-trace', 'fx-node', 'fx-node-seen'];

  clearPhrase();
  add(el, 'explain-spot');
  el.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
  highlightPhrase(el, highlight);

  if (!reduced) {
    add(el, 'explain-pop');
    let anim = animation;
    if (anim === 'reveal_steps') {
      const parts = revealParts(el);
      if (parts.length >= 2) {
        parts.forEach((p) => add(p, 'fx-dim'));
        const gap = Math.min(1400, Math.max(400, durationMs / (parts.length + 1)));
        parts.forEach((p, i) => timers.push(setTimeout(() => p.classList.remove('fx-dim'), (i + 1) * gap)));
      } else anim = 'pulse';
    }
    if (anim === 'trace') {
      const terms = traceTerms(el);
      if (terms.length >= 2) {
        terms.forEach((t) => touched.add(t));
        stepThrough(terms, Math.min(900, Math.max(250, durationMs / (terms.length + 1))), { on: 'fx-trace', timers });
      } else anim = 'underline';
    }
    if (anim === 'node_step') {
      const nodes = [...el.querySelectorAll('g.node')];
      if (nodes.length) {
        nodes.forEach((n) => touched.add(n));
        stepThrough(nodes, Math.min(1500, Math.max(400, durationMs / (nodes.length + 1))), { on: 'fx-node', seen: 'fx-node-seen', timers });
      } else anim = 'pulse';
    }
    if (anim === 'pulse' || !ANIMATIONS.includes(anim)) add(el, 'fx-pulse');
    if (anim === 'underline') add(el, 'fx-underline');
    if (anim === 'zoom') add(el, 'fx-zoom');
  }

  return () => {
    timers.forEach(clearTimeout);
    touched.forEach((node) => node.classList.remove('explain-spot', 'explain-pop', ...fx));
    clearPhrase();
  };
}
