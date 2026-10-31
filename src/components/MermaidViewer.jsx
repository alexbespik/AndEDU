import React, { useEffect, useRef } from 'react';
import { theme } from '../theme';

export default function MermaidViewer({ chart }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!chart || !containerRef.current) return;

    if (window.mermaid) {
      window.mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          darkMode: true,
          background: '#121212',
          primaryColor: '#23a55a',
          primaryTextColor: '#f8f8f2',
          primaryBorderColor: '#383838',
          lineColor: '#e5b85c',
          secondaryColor: '#1e1e1e',
          tertiaryColor: '#161616',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: '13px'
        }
      });

      const id = `mermaid-${Math.random().toString(36).substring(2, 9)}`;
      window.mermaid.render(id, chart).then(({ svg }) => {
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      }).catch((err) => {
        if (containerRef.current) {
          containerRef.current.innerHTML = `<pre style="color: ${theme.accentPink}; font-family: monospace; font-size: 0.8rem;">Diagram render error: ${err.message}</pre>`;
        }
      });
    }
  }, [chart]);

  return (
    <div 
      ref={containerRef} 
      style={{
        background: '#0d0d0d',
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        padding: 20,
        margin: '16px 0',
        overflowX: 'auto',
        display: 'flex',
        justifyContent: 'center'
      }}
    />
  );
}
