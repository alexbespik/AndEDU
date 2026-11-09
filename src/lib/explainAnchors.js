// Rehype plugin for the "Explain it to me" walkthrough: numbers the lesson's blocks in reading order with a
// data-explain id the server's walkthrough points at. h<n> headings, p<n> paragraphs, eq<n> display math (after
// rehype-katex: span.katex-display), li<n> list items, tbl<n> tables. A numbered block's insides are not numbered.
// Key formulas (f<i>) and the diagram ("diagram") are tagged by TopicViewer itself.

const KIND = { h: 'heading', p: 'paragraph', eq: 'equation', li: 'list_item', tbl: 'table', f: 'formula', diagram: 'diagram' };

function prefixFor(node) {
  const tag = node.tagName;
  if (/^h[1-6]$/.test(tag)) return 'h';
  if (tag === 'p') return 'p';
  if (tag === 'li') return 'li';
  if (tag === 'table') return 'tbl';
  const cls = node.properties?.className;
  if (tag === 'span' && Array.isArray(cls) && cls.includes('katex-display')) return 'eq';
  return null;
}

export default function explainAnchors() {
  return (tree) => {
    const count = {};
    const walk = (node) => {
      for (const child of node.children || []) {
        if (child.type !== 'element') continue;
        const prefix = prefixFor(child);
        if (prefix) {
          count[prefix] = (count[prefix] || 0) + 1;
          child.properties = { ...child.properties, dataExplain: `${prefix}${count[prefix]}` };
        } else if (child.tagName !== 'pre' && child.tagName !== 'code') {
          walk(child);
        }
      }
    };
    walk(tree);
  };
}

const MAX_ANCHORS = 60;
const MAX_TEXT = 160;
const MAX_CHARS = 4000;

/** el's visible text: KaTeX's hidden MathML copy (and its TeX annotation) is left out, so math isn't counted three times. */
function visibleText(el) {
  if (!el.querySelector('.katex-mathml')) return el.textContent || '';
  const copy = el.cloneNode(true);
  copy.querySelectorAll('.katex-mathml').forEach((m) => m.remove());
  return copy.textContent || '';
}

/** The text the walkthrough writer sees for one block: TeX source for math, visible text otherwise. */
function anchorText(el, id) {
  if (id === 'diagram') return el.dataset.explainText || '';
  if (id.startsWith('f')) return el.dataset.explainText || visibleText(el);
  if (id.startsWith('eq')) return el.querySelector('annotation')?.textContent || visibleText(el);
  return visibleText(el);
}

/** The page's anchors under root, in document order: [{id, kind, text}], at most 60 and 4000 characters of text. */
export function collectAnchors(root) {
  const out = [];
  let budget = MAX_CHARS;
  for (const el of root?.querySelectorAll('[data-explain]') || []) {
    const id = el.dataset.explain;
    const kind = KIND[id.replace(/\d+$/, '')];
    if (!kind || out.some((a) => a.id === id)) continue;
    // the diagram is always listed (its text comes from the chart source, not the SVG), so a fast and a slow render
    // send the same anchors and share one cached walkthrough
    const text = anchorText(el, id).replace(/\s+/g, ' ').trim().slice(0, Math.min(MAX_TEXT, budget));
    budget -= text.length;
    out.push({ id, kind, text });
    if (out.length >= MAX_ANCHORS) break;
  }
  return out;
}
