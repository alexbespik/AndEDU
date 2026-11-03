import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';

// Markdown + KaTeX, no raw HTML (react-markdown escapes it), shared by lessons, quizzes and chat.
const REMARK = [remarkMath, remarkGfm];
const REHYPE = [rehypeKatex];

export default function Md({ children, className }) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={REMARK} rehypePlugins={REHYPE}>
        {String(children ?? '')}
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
      {String(children ?? '')}
    </ReactMarkdown>
  );
}
