// ---------------------------------------------------------------------------
// Runs student Python in the browser (Pyodide in a Web Worker): no server execution,
// and a stuck loop is stopped by terminating the worker. Same Pyodide build as the IDE.
// ---------------------------------------------------------------------------
const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';

const WORKER_SOURCE = `
importScripts('${PYODIDE_URL}pyodide.js');
const ready = loadPyodide({ indexURL: '${PYODIDE_URL}' });
self.onmessage = async (e) => {
  const py = await ready;
  let out = '';
  py.setStdout({ batched: (s) => { out += s + '\\n'; } });
  py.setStderr({ batched: (s) => { out += s + '\\n'; } });
  try {
    const scope = py.globals.get('dict')();
    await py.runPythonAsync(e.data.code, { globals: scope });
    self.postMessage({ ok: true, output: out });
  } catch (err) {
    // keep the student-relevant tail of the traceback
    self.postMessage({ ok: false, output: out, error: String(err.message || err).trim() });
  }
};
`;

let worker = null;

function getWorker() {
  if (!worker) {
    const url = URL.createObjectURL(new Blob([WORKER_SOURCE], { type: 'text/javascript' }));
    worker = new Worker(url);
  }
  return worker;
}

/** Runs code + tests; resolves {ok, output, error, timedOut}. The first run also downloads Pyodide (~10 MB). */
export function runPython(code, { timeoutMs = 8000, firstRunTimeoutMs = 60000 } = {}) {
  const firstRun = !worker;
  const w = getWorker();
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      w.terminate();
      worker = null;  // next run starts a fresh interpreter
      resolve({ ok: false, timedOut: true, output: '', error: 'Stopped after a few seconds: is there an infinite loop?' });
    }, firstRun ? firstRunTimeoutMs : timeoutMs);
    w.onmessage = (e) => { clearTimeout(timer); resolve(e.data); };
    w.onerror = (e) => {
      clearTimeout(timer);
      w.terminate();
      worker = null;
      resolve({ ok: false, output: '', error: e.message || 'Python could not start (offline?)' });
    };
    w.postMessage({ code });
  });
}
