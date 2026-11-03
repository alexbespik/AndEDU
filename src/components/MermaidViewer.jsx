import React, { useEffect, useRef, useState } from 'react';

let initialized = false;

function whenMermaidReady(cb) {
  // mermaid loads with `defer`; wait for it instead of silently rendering nothing
  if (window.mermaid) return cb(window.mermaid);
  const t = setInterval(() => {
    if (window.mermaid) { clearInterval(t); cb(window.mermaid); }
  }, 150);
  return () => clearInterval(t);
}

export default function MermaidViewer({ chart }) {
  const ref = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!chart) return undefined;
    let cancelled = false;
    setError(null);
    const stop = whenMermaidReady((mermaid) => {
      if (!initialized) {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: 'base',
          themeVariables: {
            background: '#fdfdfb',
            primaryColor: '#e8f0ec',
            primaryTextColor: '#1c2622',
            primaryBorderColor: '#115740',
            lineColor: '#8a6b33',
            secondaryColor: '#f5efe3',
            tertiaryColor: '#f0f2ee',
            fontFamily: '"Source Sans 3", "Segoe UI", sans-serif',
            fontSize: '15px',
          },
        });
        initialized = true;
      }
      const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`;
      mermaid.render(id, chart)
        .then(({ svg }) => { if (!cancelled && ref.current) ref.current.innerHTML = svg; })
        // error text can echo the chart source, so it is rendered as text, never as HTML
        .catch((err) => { if (!cancelled) setError(err?.message || 'Diagram could not be drawn'); });
    });
    return () => { cancelled = true; if (typeof stop === 'function') stop(); };
  }, [chart]);

  if (!chart) return null;
  return (
    <figure className="diagram" aria-label="Concept diagram" style={{ margin: 0 }}>
      {error ? <p className="diagram-error">Diagram error: {error}</p> : <div ref={ref} />}
    </figure>
  );
}
