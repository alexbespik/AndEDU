// Desktop shell for &.edu: starts the bundled Python backend on 127.0.0.1 and shows the app in a window.
// The backend contract (env allowlist, stdin settings line, instance id) is described in desktop_main.py
// and ARCHITECTURE.md section 5.4.
const { app, BrowserWindow, dialog, ipcMain, safeStorage, session, shell } = require('electron');
const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');
const { StringDecoder } = require('node:string_decoder');
const { buildStartPage, parseStartupChunk, renderLog } = require('./startpage.cjs');

const PORT_RANGE = [38090, 38190];
const READY_TIMEOUT_MS = 60_000;
const LOG_LIMIT_BYTES = 5 * 1024 * 1024;
const START_PAGE_URL = 'data:text/html;charset=utf-8,' + encodeURIComponent(buildStartPage());
const STARTUP_LINES = 6;
const STARTUP_READ_BYTES = 64 * 1024;
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

let dataDir, configPath, deviceKeyPath, legacyKeyPath, logDir;
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

// On Linux, safeStorage falls back to 'basic_text' (a fixed password built into Chromium) when no keyring
// (GNOME Keyring, KWallet) answers; that is no better than plain text, so no secret is stored or read then.
// Call only after app 'ready'.
function secureStoreOk() {
  if (!safeStorage.isEncryptionAvailable()) return false;
  if (process.platform !== 'linux') return true;
  return !['basic_text', 'unknown'].includes(safeStorage.getSelectedStorageBackend());
}

// The device key (32 random bytes, base64) seals the Gemini keys of accounts without a password (userkeys.py).
// Made once, kept in the Keychain/keyring through safeStorage. A file that exists but does not open (another build
// the Keychain no longer trusts, a locked keyring) is never replaced: that would lose every key sealed with it.
// No secure store: no device key, and only accounts with a password can keep a key.
function loadDeviceKey() {
  if (!secureStoreOk()) return '';
  let sealed;
  try {
    sealed = fs.readFileSync(deviceKeyPath);
  } catch (err) {
    if (err.code !== 'ENOENT') return '';
    try {
      const key = crypto.randomBytes(32).toString('base64');
      fs.mkdirSync(path.dirname(deviceKeyPath), { recursive: true, mode: 0o700 });
      const tmp = deviceKeyPath + '.tmp';
      fs.writeFileSync(tmp, safeStorage.encryptString(key), { mode: 0o600 });
      fs.renameSync(tmp, deviceKeyPath);
      return key;
    } catch {
      return '';
    }
  }
  try {
    const key = safeStorage.decryptString(sealed);
    return Buffer.from(key, 'base64').length === 32 ? key : '';
  } catch {
    return '';
  }
}

// The Gemini key older versions saved for the whole computer: handed to the backend, which offers it once to an
// account; the page then asks for the file to be deleted (removeLegacyKey).
function loadLegacyKey() {
  try {
    if (!secureStoreOk() || !fs.existsSync(legacyKeyPath)) return '';
    return safeStorage.decryptString(fs.readFileSync(legacyKeyPath));
  } catch {
    return '';  // made by another build the Keychain/keyring no longer trusts: nothing to offer
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
    SCIEDU_LOCAL_ACCOUNTS: '1',  // accounts on this computer: each with its own data and its own Gemini key
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
  const logStart = fs.fstatSync(log).size;  // the start page shows only this run's [startup] lines
  const child = spawn(PYTHON, ['-I', '-B', '-u', path.join(BACKEND_DIR, 'desktop_main.py')], {
    cwd: dataDir,
    env: backendEnv(port, instanceId),
    stdio: ['pipe', log, log],
  });
  fs.closeSync(log);
  // secrets go on stdin, never in env or argv (other processes of the user can read those); stdin stays open: EOF stops the backend
  const settings = {};
  const deviceKey = loadDeviceKey();
  if (deviceKey) settings.device_key = deviceKey;
  const legacyKey = loadLegacyKey();
  if (legacyKey) settings.legacy_gemini_key = legacyKey;
  child.stdin.write(JSON.stringify(settings) + '\n');
  child.stdin.on('error', () => {});

  const current = { child, port, origin: `http://127.0.0.1:${port}`, instanceId, ready: false, error: null };
  backend = current;
  child.on('error', (err) => { current.error = err; });  // e.g. the bundled Python is missing: no 'exit' follows
  child.on('exit', (code, signal) => onBackendExit(current, code, signal));
  await waitUntilReady(current, logStart);
  current.ready = true;
  return current;
}

function onStartPage() {
  return Boolean(win) && !win.isDestroyed() && win.webContents.getURL().startsWith('data:');
}

async function showStartPage() {
  if (!win || win.isDestroyed() || onStartPage()) return;
  await win.loadURL(START_PAGE_URL).catch(() => {});  // rejects only when another load replaces it
}

// Follows backend.log from `offset` and puts the last few "[startup] " lines on the start page.
function startupProgress(b, offset) {
  const file = path.join(logDir, 'backend.log');
  let carry = '';
  let decoder = new StringDecoder('utf8');  // a 64 KB cut can split a UTF-8 character
  let lines = [];
  let shown = null;  // push once even when empty: a restart on the start page clears the previous run's lines
  return () => {
    let fd = null;
    try {
      fd = fs.openSync(file, 'r');
      const size = fs.fstatSync(fd).size;
      if (size < offset) { offset = 0; carry = ''; decoder = new StringDecoder('utf8'); }
      const want = Math.min(size - offset, STARTUP_READ_BYTES);
      if (want > 0) {
        const buf = Buffer.alloc(want);
        const got = fs.readSync(fd, buf, 0, want, offset);
        offset += got;
        const parsed = parseStartupChunk(decoder.write(buf.subarray(0, got)), carry);
        carry = parsed.carry;
        if (parsed.lines.length) lines = [...lines, ...parsed.lines].slice(-STARTUP_LINES);
      }
    } catch {
      // the progress list is cosmetic: an unreadable log just leaves it as it was
    } finally {
      if (fd !== null) fs.closeSync(fd);
    }
    const next = JSON.stringify(lines);
    if (next !== shown && backend === b && onStartPage()) {
      shown = next;
      win.webContents.executeJavaScript(`(${renderLog.toString()})(${next})`).catch(() => {});
    }
  };
}

async function waitUntilReady(b, logStart) {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  const progress = startupProgress(b, logStart);
  while (Date.now() < deadline) {
    progress();
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
  // After an account took the old key (PUT /api/me/gemini-key {adoptLegacy}) or declined it (DELETE /api/me/legacy-key),
  // the file goes. The backend decides: while its /api/status says legacy_key_pending (no answer yet, or the account
  // could not store the key), or when it cannot be asked, the file stays and is offered again next launch.
  ipcMain.handle('sciedu:removeLegacyKey', async (event) => {
    if (!fromBackend(event)) return { ok: false };
    const b = backend;
    try {
      const res = await fetch(`${b.origin}/api/status`, { signal: AbortSignal.timeout(2000) });
      const st = res.ok ? await res.json() : null;
      if (!st || st.instance_id !== b.instanceId || st.legacy_key_pending !== false) return { ok: false };
    } catch {
      return { ok: false };
    }
    fs.rmSync(legacyKeyPath, { force: true });
    return { ok: true };
  });
}

// Starts and restarts run one at a time, so two of them never race for the port or the window.
let queue = Promise.resolve();
function serially(task) {
  queue = queue.then(task, task);
  return queue;
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
  win.on('closed', () => { win = null; });  // the first startAndShow loads the start page
}

async function startAndShow() {
  if (quitting) return;
  await showStartPage();  // restarts come from the app page: show the progress again
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
    deviceKeyPath = path.join(dataDir, 'secrets', 'device.key.enc');
    legacyKeyPath = path.join(dataDir, 'secrets', 'gemini.key.enc');  // older versions: one key for the computer
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
