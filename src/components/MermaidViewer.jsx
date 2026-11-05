import React, { useEffect, useRef, useState } from 'react';

let mermaidPromise = null;

// mermaid is large, so it loads on the first diagram only; every viewer shares the one initialized copy
function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'base',
        themeVariables: {
          background: '#ffffff',
          primaryColor: '#e2ebe5',
          primaryTextColor: '#0b0f0d',
          primaryBorderColor: '#0e4a37',
          lineColor: '#6f5114',
          secondaryColor: '#f7eed6',
          tertiaryColor: '#f1f0ea',
          fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
          fontSize: '15px',
        },
      });
      return mermaid;
    }).catch((err) => { mermaidPromise = null; throw err; }); // a failed chunk load can be retried
  }
  return mermaidPromise;
}

/**
 * Generated diagrams often break Mermaid's grammar in the same few ways: labels with ( ) , : or quotes
 * left unquoted, LaTeX $...$ inside labels, and literal "\n". Quote and clean them before parsing.
 */
export function sanitizeMermaid(src) {
  const clean = (label) => label.replace(/\$/g, '').replace(/\\n/g, ' ').replace(/"/g, "'").trim();
  const kept = [];
  const keep = (text) => { kept.push(text); return `\u0000${kept.length - 1}\u0000`; };
  const isKept = (label) => /^\u0000\d+\u0000$/.test(label.trim());

  let text = String(src || '').replace(/\\n/g, '\n');
  // 1. edge labels first: they often hold math like v_{TE}, whose braces read as a decision shape
  text = text.replace(/\|([^|\n]*)\|/g, (_, label) => keep(`|"${clean(label.replace(/^"|"$/g, ''))}"|`));
  // 2. set aside labels that are already quoted, so they are never quoted twice
  text = text.replace(/"[^"\n]*"/g, (q) => keep(q));
  // 3. quote bare node labels: A[label], A(label), A{label}
  text = text
    .replace(/(\b[\w-]+)\[([^\]\n]*)\]/g, (m, id, label) => (isKept(label) ? m : `${id}["${clean(label)}"]`))
    .replace(/(\b[\w-]+)\(([^()\n]*)\)/g, (m, id, label) => (isKept(label) || /^(click|style|classDef)$/.test(id) ? m : `${id}("${clean(label)}")`))
    .replace(/(\b[\w-]+)\{([^{}\n]*)\}/g, (m, id, label) => (isKept(label) ? m : `${id}{"${clean(label)}"}`));
  return text.replace(/\u0000(\d+)\u0000/g, (_, i) => kept[Number(i)]);
}

export default function MermaidViewer({ chart }) {
  const ref = useRef(null);
  const [state, setState] = useState('loading'); // loading | ok | skipped

  useEffect(() => {
    if (!chart) return undefined;
    let cancelled = false;
    setState('loading');
    (async () => {
      let mermaid;
      try { mermaid = await loadMermaid(); } catch { if (!cancelled) setState('skipped'); return; }
      if (cancelled) return;
      // Try the diagram as written, then the repaired version; parse() with suppressErrors never
      // touches the page, unlike render(), which leaves "Syntax error in text" in the document body.
      let source = null;
      for (const candidate of [chart, sanitizeMermaid(chart)]) {
        try {
          if (await mermaid.parse(candidate, { suppressErrors: true })) { source = candidate; break; }
        } catch { /* try the next candidate */ }
      }
      if (cancelled) return;
      if (!source) { setState('skipped'); return; }
      const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`;
      try {
        const { svg } = await mermaid.render(id, source);
        if (!cancelled && ref.current) { ref.current.innerHTML = svg; setState('ok'); }
      } catch {
        if (!cancelled) setState('skipped');
      } finally {
        // render() can leave its temporary container behind on failure
        document.getElementById(`d${id}`)?.remove();
      }
    })();
    return () => { cancelled = true; };
  }, [chart]);

  if (!chart || state === 'skipped') return null; // a broken diagram is left out, not shown as an error
  return (
    <figure className="diagram" aria-label="Concept diagram" style={{ margin: 0 }}>
      <div ref={ref} />
    </figure>
  );
}
