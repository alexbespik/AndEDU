import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';

// Markdown + KaTeX, no raw HTML (react-markdown escapes it), shared by lessons, quizzes and chat.
const REMARK = [remarkMath, remarkGfm];
const REHYPE = [rehypeKatex];

// Control characters that a JSON "\f", "\t", "\b"... turned out of a LaTeX command ("\frac" -> form feed + "rac")
const CONTROL = { '\f': 'f', '\b': 'b', '\u0007': 'a', '\u000b': 'v' };

/**
 * Generated text uses several math conventions; KaTeX via remark-math only understands $...$ and $$...$$.
 * - \( ... \) and \[ ... \] become $ ... $ and $$ ... $$
 * - "( \frac{a}{b} )" whose backslash-paren was lost becomes $ ... $ when it holds a LaTeX command
 * - $$...$$ inside a table row becomes inline math (display math can't live in a table cell)
 * - a line holding only $$...$$ is display math (remark-math reads one-line $$x$$ as inline)
 */
const LATEX_NAMES = /^(frac|dfrac|sqrt|sin|cos|tan|log|ln|exp|omega|theta|alpha|beta|gamma|delta|epsilon|lambda|sigma|infty|cdot|times|text|mathrm|mathbf|left|right|hat|vec|implies|approx|sum|int|lim|pi|mu|tau|rho|phi|psi)$/;

/** A whole string that is just a formula (LaTeX commands, almost no ordinary words) and has no $ markers. */
function bareFormula(t) {
  if (t.includes('$') || !/\\[a-zA-Z]+/.test(t) || t.includes('\n') || t.length > 160) return false;
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

export default function Md({ children, className }) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={REMARK} rehypePlugins={REHYPE}>
        {displayMath(String(children ?? ''))}
      </ReactMarkdown>
    </div>
  );
}

/** Inline math/markdown without a wrapping block (for option labels and short strings). */
export function MdInline({ children }) {
  return (
    <ReactMarkdown
      remarkPlugins={REMARK}
      rehypePlugins={REHYPE}
      components={{ p: ({ children: c }) => <>{c}</> }}
    >
      {normalizeMath(children)}
    </ReactMarkdown>
  );
}
