import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import GeometrySim from '../simulations/GeometrySim';
import explainAnchors from '../lib/explainAnchors';

// Markdown + KaTeX, no raw HTML (react-markdown escapes it), shared by lessons, quizzes and chat.
const REMARK = [remarkMath, remarkGfm];
const KATEX_OPTIONS = {
  throwOnError: false,
  errorColor: '#f92672',
  strict: false,
  macros: {
    '\\ihat': '\\hat{\\imath}',
    '\\jhat': '\\hat{\\jmath}',
    '\\khat': '\\hat{k}',
    '\\uvec': '\\mathbf{\\hat{#1}}',
  },
};
const REHYPE = [[rehypeKatex, KATEX_OPTIONS]];
// the lesson body only (ids must be unique on the page): blocks get data-explain ids for the walkthrough
const REHYPE_EXPLAIN = [...REHYPE, explainAnchors];

// Control characters that a JSON "\f", "\t", "\b"... turned out of a LaTeX command ("\frac" -> form feed + "rac")
const CONTROL = { '\f': 'f', '\b': 'b', '\u0007': 'a', '\u000b': 'v' };

/**
 * Generated text uses several math conventions; KaTeX via remark-math only understands $...$ and $$...$$.
 * - \( ... \) and \[ ... \] become $ ... $ and $$ ... $$
 * - "( \frac{a}{b} )" whose backslash-paren was lost becomes $ ... $ when it holds a LaTeX command
 * - $$...$$ inside a table row becomes inline math (display math can't live in a table cell)
 * - a line holding only $$...$$ is display math (remark-math reads one-line $$x$$ as inline)
 */
const LATEX_NAMES = /^(frac|dfrac|sqrt|sin|cos|tan|log|ln|exp|omega|theta|alpha|beta|gamma|delta|epsilon|lambda|sigma|infty|cdot|times|text|mathrm|mathbf|left|right|hat|vec|implies|approx|sum|int|lim|pi|mu|tau|rho|phi|psi|ihat|jhat|khat|imath|jmath|uvec)$/;

/** A whole string that is just a formula (LaTeX commands, almost no ordinary words) and has no $ markers. */
function bareFormula(t) {
  if (t.includes('$') || /\\[([]/.test(t) || !/\\[a-zA-Z]+/.test(t) || t.includes('\n') || t.length > 160) return false;  // \( \[ are converted later
  const words = (t.replace(/\\[a-zA-Z]+/g, ' ').match(/[A-Za-z]{4,}/g) || []).filter((w) => !LATEX_NAMES.test(w));
  return words.length === 0;
}

export function normalizeMath(text) {
  let t = String(text ?? '');
  if (bareFormula(t)) return `$${t.trim()}$`;
  t = t.replace(/[\f\b\u0007\u000b](?=[a-z])/g, (c) => `\\${CONTROL[c]}`)
    .replace(/\t(?=(?:heta|au|imes|ext|an(?![a-z])))/g, '\\t')
    .replace(/\r(?=(?:ight|ho)(?![a-z]))/g, '\\r').replace(/\r(?=ight)/g, '\\r');
  t = t.replace(/^([ \t]*\$\$[^$\n]+)\$[|<>][ \t]*$/gm, '$1$$$$');  // model typo: $$x$| closing a display formula
  t = t.replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `$$${m}$$`).replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => `$${m.trim()}$`);

  // Unit vector normalizations
  t = t.replace(/(?:[iı]\u0302|î)/g, '\\hat{\\imath}')
    .replace(/(?:[jȷ]\u0302|ĵ)/g, '\\hat{\\jmath}')
    .replace(/k\u0302/g, '\\hat{k}');
  t = t.replace(/(^|[^\w\\])(?:i\^|ı\^)(?![a-zA-Z0-9_{\(])/g, '$1\\hat{\\imath}')
    .replace(/(^|[^\w\\])(?:j\^|ȷ\^)(?![a-zA-Z0-9_{\(])/g, '$1\\hat{\\jmath}')
    .replace(/(^|[^\w\\])k\^(?![a-zA-Z0-9_{\(])/g, '$1\\hat{k}');
  t = t.replace(/\\hat\{i\}/g, '\\hat{\\imath}')
    .replace(/\\hat\{j\}/g, '\\hat{\\jmath}')
    .replace(/\\hat\s+i\b/g, '\\hat{\\imath}')
    .replace(/\\hat\s+j\b/g, '\\hat{\\jmath}');
  t = t.replace(/\\ihat\b/g, '\\hat{\\imath}')
    .replace(/\\jhat\b/g, '\\hat{\\jmath}')
    .replace(/\\khat\b/g, '\\hat{k}');

  t = t.split('\n').map((line) => {
    if (/^\s*\|.*\|\s*$/.test(line)) line = line.replace(/\$\$([^$]+)\$\$/g, (_, m) => `$${m.trim()}$`);
    // a parenthesised formula outside existing math: (\frac{v^2}{r}) or (a_c = \frac{v^2}{r})
    return line.split(/(\$\$?[^$]*\$\$?)/).map((part, i) => (i % 2 ? part
      : part.replace(/(?<!\\left)\(\s*((?:[^()]|\([^()]*\))*?\\[a-zA-Z]+(?:[^()]|\([^()]*\))*?)\s*(?<!\\right)\)/g,
        (all, m) => (/\\left\s*$|\\right\s*$/.test(m) ? all : `$${m}$`)))).join('');
  }).join('\n');
  return t.replace(/^[ \t]*\$\$([^\n$]+?)\$\$[ \t]*$/gm, '$$$$\n$1\n$$$$');
}
const displayMath = normalizeMath;

// Markdown + KaTeX parsing is the most expensive thing on most pages: memoized, so a re-render with the same
// text (a background topics refresh, a timer tick) costs nothing.
// Images only from this site or inline data: a model-written image URL could otherwise carry page data to another host.
const localSrc = (src) => typeof src === 'string' && ((src.startsWith('/') && !src.startsWith('//')) || src.startsWith('data:image/'));
const COMPONENTS = {
  img: ({ src, alt }) => (localSrc(src) ? <img src={src} alt={alt || ''} /> : null),
  code: ({ node, inline, className, children, ...props }) => {
    const isGeometry = className === 'language-geometry' || className === 'language-fbd';
    if (!inline && isGeometry) {
      const raw = String(children ?? '').replace(/\n$/, '');
      try {
        const spec = JSON.parse(raw);
        return <GeometrySim spec={spec} />;
      } catch (err) {
        return (
          <div className="geometry-sim-error diagram-error p-3 rounded my-2 border border-red-500/30 bg-red-950/20 text-red-300 text-xs font-mono">
            <strong>Geometry spec error:</strong> {err.message}
            <pre className="mt-1 text-[11px] opacity-75 overflow-x-auto">{raw}</pre>
          </div>
        );
      }
    }
    return <code className={className} {...props}>{children}</code>;
  },
  pre: ({ children, ...props }) => {
    const child = Array.isArray(children) ? children[0] : children;
    if (React.isValidElement(child) && (child.type === GeometrySim || child.props?.className?.includes('geometry-sim-error'))) {
      return children;
    }
    return <pre {...props}>{children}</pre>;
  },
};

const INLINE_COMPONENTS = { ...COMPONENTS, p: ({ children: c }) => <>{c}</> };

function Md({ children, className, explainIds = false }) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={REMARK} rehypePlugins={explainIds ? REHYPE_EXPLAIN : REHYPE} components={COMPONENTS}>
        {displayMath(String(children ?? ''))}
      </ReactMarkdown>
    </div>
  );
}

/** Inline math/markdown without a wrapping block (for option labels and short strings). */
function MdInlineView({ children }) {
  return (
    <ReactMarkdown
      remarkPlugins={REMARK}
      rehypePlugins={REHYPE}
      components={INLINE_COMPONENTS}
    >
      {normalizeMath(children)}
    </ReactMarkdown>
  );
}

export default React.memo(Md);
export const MdInline = React.memo(MdInlineView);
