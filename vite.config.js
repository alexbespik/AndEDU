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
