// Desktop shell for &.edu: starts the bundled Python backend on 127.0.0.1 and shows the app in a window.
// The backend contract (env allowlist, stdin settings line, instance id) is described in desktop_main.py
// and ARCHITECTURE.md section 5.4.
const { app, BrowserWindow, dialog, ipcMain, safeStorage, session, shell } = require('electron');
const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');

const PORT_RANGE = [38090, 38190];
const READY_TIMEOUT_MS = 60_000;
const LOG_LIMIT_BYTES = 5 * 1024 * 1024;
const KEY_RE = /^[A-Za-z0-9_-]{30,100}$/;
const DEV = !app.isPackaged;
const ROOT = path.resolve(__dirname, '..');
const BACKEND_DIR = DEV ? ROOT : path.join(process.resourcesPath, 'backend');

// index.html has one small inline script (apply the saved theme before first paint): allow exactly that by hash
function inlineScriptHashes() {
  try {
    const html = fs.readFileSync(path.join(BACKEND_DIR, 'dist', 'index.html'), 'utf8');
    return [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)]
      .map((m) => `'sha256-${crypto.createHash('sha256').update(m[1]).digest('base64')}'`).join(' ');
  } catch {
    return '';
  }
}

const CSP = [
  "default-src 'self'",
  // Pyodide (the in-browser Python runner) loads from jsdelivr and compiles WebAssembly in a blob worker
  `script-src 'self' ${inlineScriptHashes()} 'wasm-unsafe-eval' 'unsafe-eval' blob: https://cdn.jsdelivr.net`,
  "worker-src 'self' blob:",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' data: https://fonts.gstatic.com",
  "img-src 'self' data: blob:",
  "media-src 'self' data: blob:",
  "connect-src 'self' https://cdn.jsdelivr.net",
  "object-src 'none'",
  "frame-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ');

const PYTHON = DEV ? path.join(ROOT, '.venv', 'bin', 'python') : path.join(process.resourcesPath, 'python', 'bin', 'python3');
const SEED_DIR = path.join(BACKEND_DIR, 'seed', 'topics');

let dataDir, configPath, keyPath, logDir;
let win = null;
let backend = null;   // { child, port, origin, instanceId, ready }
let quitting = false;
let restarts = [];

function readConfig() {
  try { return JSON.parse(fs.readFileSync(configPath, 'utf8')); } catch { return {}; }
}

function writeConfig(cfg) {
  const tmp = configPath + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(cfg, null, 2), { mode: 0o600 });
  fs.renameSync(tmp, configPath);
}

function portIsFree(port) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.once('error', () => resolve(false));
    srv.listen(port, '127.0.0.1', () => srv.close(() => resolve(true)));
  });
}

// The same port every launch keeps the page's origin, so its browser storage (MathLab, ChemKit) survives.
async function choosePort(cfg) {
  if (cfg.port && await portIsFree(cfg.port)) return cfg.port;
  for (let p = PORT_RANGE[0]; p <= PORT_RANGE[1]; p++) {
    if (await portIsFree(p)) return p;
  }
  throw new Error(`No free port between ${PORT_RANGE[0]} and ${PORT_RANGE[1]}.`);
}

// First launch only: copy the library lessons. Later launches never put back a lesson the user deleted.
function seedContent(cfg) {
  const topics = path.join(dataDir, 'content', 'topics');
  fs.mkdirSync(topics, { recursive: true });
  if (cfg.seeded || DEV) return;  // dev runs leave the flag unset, so a later packaged run still seeds
  if (fs.existsSync(SEED_DIR)) {
    for (const name of fs.readdirSync(SEED_DIR)) {
      if (!/^[a-z0-9][a-z0-9-]*\.json$/.test(name)) continue;
      const dest = path.join(topics, name);
      if (!fs.existsSync(dest)) fs.copyFileSync(path.join(SEED_DIR, name), dest);
    }
  }
  cfg.seeded = true;
}

function openLog() {
  fs.mkdirSync(logDir, { recursive: true });
  const file = path.join(logDir, 'backend.log');
  try {
    if (fs.statSync(file).size > LOG_LIMIT_BYTES) fs.renameSync(file, file + '.1');
  } catch { /* no log yet */ }
  return fs.openSync(file, 'a', 0o600);
}

function loadKey() {
  try {
    if (!safeStorage.isEncryptionAvailable()) return '';
    return safeStorage.decryptString(fs.readFileSync(keyPath));
  } catch {
    return '';  // missing, or made by another build the Keychain no longer trusts: ask again
  }
}

function backendEnv(port, instanceId) {
  const env = { PATH: '/usr/bin:/bin:/usr/sbin:/sbin' };
  for (const name of ['HOME', 'TMPDIR', 'LANG', 'USER']) {
    if (process.env[name]) env[name] = process.env[name];
  }
  Object.assign(env, {
    SCIEDU_HOST: '127.0.0.1',
    SCIEDU_PORT: String(port),
    SCIEDU_CONTENT_DIR: path.join(dataDir, 'content'),
    SCIEDU_ENV_FILE: 'none',
    SCIEDU_INSTANCE_ID: instanceId,
    SCIEDU_ALLOWED_ORIGINS: `http://127.0.0.1:${port}`,
    AGY_CLI: '0',
    SCIEDU_ELEVENLABS: '0',
    PYTHONDONTWRITEBYTECODE: '1',
  });
  return env;
}

async function startBackend() {
  const cfg = readConfig();
  seedContent(cfg);
  const port = await choosePort(cfg);
  cfg.port = port;
  writeConfig(cfg);

  const instanceId = crypto.randomUUID();
  const log = openLog();
  fs.writeSync(log, `\n--- ${new Date().toISOString()} starting on 127.0.0.1:${port}\n`);
  const child = spawn(PYTHON, ['-I', '-B', '-u', path.join(BACKEND_DIR, 'desktop_main.py')], {
    cwd: dataDir,
    env: backendEnv(port, instanceId),
    stdio: ['pipe', log, log],
  });
  fs.closeSync(log);
  const key = loadKey();
  child.stdin.write(JSON.stringify(key ? { gemini_key: key } : {}) + '\n');  // stdin stays open: EOF stops the backend
  child.stdin.on('error', () => {});

  const current = { child, port, origin: `http://127.0.0.1:${port}`, instanceId, ready: false, error: null };
  backend = current;
  child.on('error', (err) => { current.error = err; });  // e.g. the bundled Python is missing: no 'exit' follows
  child.on('exit', (code, signal) => onBackendExit(current, code, signal));
  await waitUntilReady(current);
  current.ready = true;
  return current;
}

async function waitUntilReady(b) {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (b.error) throw new Error(`The backend could not be started (${b.error.message}).`);
    if (b.child.exitCode !== null || b.child.signalCode !== null) throw new Error('The backend stopped while starting.');
    try {
      const res = await fetch(`${b.origin}/api/status`, { signal: AbortSignal.timeout(2000) });
      if (res.ok && (await res.json()).instance_id === b.instanceId) return;
    } catch { /* not listening yet */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error('The backend did not start within a minute.');
}

function stopBackend() {
  const b = backend;
  backend = null;
  if (!b || b.error || b.child.exitCode !== null || b.child.signalCode !== null) return Promise.resolve();
  return new Promise((resolve) => {
    const kill = setTimeout(() => b.child.kill('SIGKILL'), 5000);
    b.child.once('exit', () => { clearTimeout(kill); resolve(); });
    b.child.kill('SIGTERM');
  });
}

async function onBackendExit(b, code, signal) {
  if (quitting || backend !== b || !b.ready) return;  // planned stops, and start failures (startBackend reports those)
  backend = null;
  restarts = restarts.filter((t) => Date.now() - t < 5 * 60_000);
  const canRestart = restarts.length < 3;
  const { response } = await dialog.showMessageBox(win, {
    type: 'error',
    message: 'The &.edu backend stopped.',
    detail: `Exit ${signal || code}. ${canRestart ? 'Restart it?' : 'It stopped three times in five minutes.'} The log is in ${logDir}.`,
    buttons: canRestart ? ['Restart', 'Open logs', 'Quit'] : ['Open logs', 'Quit'],
  });
  if (quitting) return;
  const choice = (canRestart ? ['restart', 'logs', 'quit'] : ['logs', 'quit'])[response];
  if (choice === 'logs') shell.openPath(logDir);
  if (choice === 'restart') {
    restarts.push(Date.now());
    await launch();
  } else {
    app.quit();
  }
}

function fromBackend(event) {
  try {
    return Boolean(backend) && new URL(event.senderFrame.url).origin === backend.origin;
  } catch {
    return false;
  }
}

function registerIpc() {
  ipcMain.handle('sciedu:hasKey', (event) => fromBackend(event) && Boolean(loadKey()));
  ipcMain.handle('sciedu:saveKey', async (event, value) => {
    if (!fromBackend(event)) return { ok: false, error: 'Not allowed.' };
    const key = typeof value === 'string' ? value.trim() : '';
    if (!KEY_RE.test(key)) return { ok: false, error: 'That does not look like a Gemini API key.' };
    if (!safeStorage.isEncryptionAvailable()) return { ok: false, error: 'The macOS Keychain is not available, so the key cannot be stored safely.' };
    fs.mkdirSync(path.dirname(keyPath), { recursive: true, mode: 0o700 });
    const tmp = keyPath + '.tmp';
    fs.writeFileSync(tmp, safeStorage.encryptString(key), { mode: 0o600 });
    fs.renameSync(tmp, keyPath);
    setTimeout(relaunchBackend, 100);  // reply first: the page reloads when the new backend is up
    return { ok: true };
  });
  ipcMain.handle('sciedu:clearKey', (event) => {
    if (!fromBackend(event)) return { ok: false };
    fs.rmSync(keyPath, { force: true });
    setTimeout(relaunchBackend, 100);
    return { ok: true };
  });
}

// Starts, restarts and key relaunches run one at a time, so two of them never race for the port or the window.
let queue = Promise.resolve();
function serially(task) {
  queue = queue.then(task, task);
  return queue;
}

function relaunchBackend() {
  return serially(async () => {
    await stopBackend();
    await startAndShow();
  });
}

function launch() {
  return serially(startAndShow);
}

function lockDown(contents) {
  contents.on('will-navigate', (event, url) => {
    let origin = null;
    try { origin = new URL(url).origin; } catch { /* malformed: blocked below */ }
    if (!backend || origin !== backend.origin) event.preventDefault();
  });
  contents.on('will-attach-webview', (event) => event.preventDefault());
  contents.setWindowOpenHandler(({ url }) => {
    if (/^https:\/\//.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
}

function hardenSession() {
  const ses = session.defaultSession;
  const sameOrigin = (url) => {
    try { return Boolean(backend) && new URL(url).origin === backend.origin; } catch { return false; }
  };
  // The microphone (speaking drills) is the only permission the app asks for.
  ses.setPermissionRequestHandler((wc, permission, callback, details) => {
    callback(permission === 'media' && sameOrigin(details.requestingUrl || wc.getURL()));
  });
  ses.setPermissionCheckHandler((wc, permission, origin) => permission === 'media' && sameOrigin(origin));
  ses.webRequest.onHeadersReceived((details, callback) => {
    const headers = { ...details.responseHeaders };
    if (sameOrigin(details.url) && details.resourceType === 'mainFrame') headers['Content-Security-Policy'] = [CSP];
    callback({ responseHeaders: headers });
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: '&.edu',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      webviewTag: false,
      spellcheck: false,
    },
  });
  lockDown(win.webContents);
  win.once('ready-to-show', () => win.show());
  win.on('closed', () => { win = null; });
  win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(
    '<!doctype html><title>&amp;.edu</title><body style="font:16px -apple-system,sans-serif;display:grid;place-items:center;height:90vh;color:#666">Starting &amp;.edu…</body>'));
}

async function startAndShow() {
  if (quitting) return;
  try {
    const b = await startBackend();
    if (win && backend === b) await win.loadURL(`${b.origin}/`);
  } catch (err) {
    await stopBackend();
    if (quitting) return;  // closed while starting: no "could not start" dialog
    const { response } = await dialog.showMessageBox(win, {
      type: 'error',
      message: '&.edu could not start.',
      detail: `${err.message} The log is in ${logDir}.`,
      buttons: ['Open logs', 'Quit'],
    });
    if (response === 0) await shell.openPath(logDir);
    app.quit();
  }
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.whenReady().then(async () => {
    dataDir = app.getPath('userData');
    configPath = path.join(dataDir, 'config.json');
    keyPath = path.join(dataDir, 'secrets', 'gemini.key.enc');
    logDir = path.join(dataDir, 'logs');
    fs.mkdirSync(dataDir, { recursive: true });
    registerIpc();
    hardenSession();
    app.on('web-contents-created', (_event, contents) => lockDown(contents));
    createWindow();
    await launch();
  });

  app.on('window-all-closed', () => app.quit());

  let stopped = false;
  app.on('before-quit', (event) => {
    quitting = true;
    if (stopped) return;
    event.preventDefault();
    stopBackend().finally(() => { stopped = true; app.quit(); });
  });
}
