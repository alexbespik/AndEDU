import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// rehype-katex renders with its own KaTeX (0.16.x). Every other `katex` import (the CSS, the IDE's
// renderToString) must use that same copy, or the HTML and stylesheet disagree and fractions and
// subscripts render garbled. Resolve it the way rehype-katex does, so any npm layout works.
const rehypeKatexEntry = fileURLToPath(import.meta.resolve('rehype-katex'));
const katexDir = path.dirname(createRequire(rehypeKatexEntry).resolve('katex/package.json'));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [{ find: /^katex(\/.*)?$/, replacement: `${katexDir}$1` }],
  },
  build: {
    chunkSizeWarningLimit: 800,
    rolldownOptions: {
      output: {
        // libraries change far less often than app code: separate chunks stay cached across deploys
        codeSplitting: {
          groups: [
            { name: 'react', test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/ },
            { name: 'katex', test: /node_modules[\\/]katex[\\/]/ },
            { name: 'markdown', test: /node_modules[\\/](react-markdown|remark-[^\\/]+|rehype-[^\\/]+|micromark[^\\/]*|mdast-[^\\/]+|hast-[^\\/]+|unist-[^\\/]+|unified|vfile[^\\/]*|property-information|space-separated-tokens|comma-separated-tokens|decode-named-character-reference|character-entities[^\\/]*|html-url-attributes|devlop|bail|trough|is-plain-obj|zwitch|longest-streak|ccount|markdown-table|escape-string-regexp|trim-lines|estree-util-is-identifier-name|style-to-js|style-to-object|inline-style-parser)[\\/]/ },
          ],
        },
      },
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8090',
        changeOrigin: true,
      }
    }
  }
});
