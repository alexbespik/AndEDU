import React, { useEffect, useRef, useState } from 'react';
import { useModalFocus } from '../lib/useModalFocus';
import { getState, setMuted, loadPacks, setVoice, setRough, say, summon } from '../lib/commissar';

const HELP = ['help   this list', 'voices   list the voices', 'voice <id>   use a voice (auto or a pack)', 'rough <0-3>   how rough the Commissar voice is (0 clean, 3 gravel)', 'mute   silence the voice', 'unmute   restore the voice', 'clear   empty the log', 'exit   close the console'];
const BLOCKED = 'input, textarea, select, [contenteditable=""], [contenteditable="true"], [contenteditable="plaintext-only"], .cm-editor, canvas';

/** Hidden console: ` or ~ opens it. One of its commands switches Commissar mode. */
export default function CommissarConsole() {
  const [open, setOpen] = useState(false);
  const [log, setLog] = useState([]);
  const [value, setValue] = useState('');
  const panel = useRef(null);
  const input = useRef(null);
  const logEnd = useRef(null);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.key !== '`' && e.key !== '~') || e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
      const t = e.target;
      if (t instanceof Element && t.closest(BLOCKED)) return;
      const ae = document.activeElement;
      if (ae && ae !== document.body && ae.closest?.(BLOCKED)) return;
      const modal = document.querySelector('[role="dialog"][aria-modal="true"]');
      if (modal && modal !== panel.current) return;
      e.preventDefault();
      setOpen((o) => !o);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useModalFocus(open, panel, () => setOpen(false));
  useEffect(() => { if (open) input.current?.focus(); }, [open]);
  useEffect(() => { logEnd.current?.scrollIntoView?.({ block: 'end' }); }, [log]);

  if (!open) return null;

  const run = (raw) => {
    const cmd = raw.trim().toLowerCase();
    if (!cmd) return;
    const out = [`> ${raw.trim()}`];
    if (cmd === 'rough' || cmd.startsWith('rough ')) {
      const lvl = cmd.slice(5).trim();
      if (!lvl) out.push(`rough: ${getState().rough} (0 clean .. 3 gravel)`);
      else if (setRough(lvl)) { out.push(`rough: ${lvl}`); say('on'); }
      else out.push('rough takes 0, 1, 2 or 3');
      setLog((l) => [...l, ...out].slice(-60));
      return;
    }
    if (cmd === 'voices' || cmd.startsWith('voice ')) {
      const want = cmd.startsWith('voice ') ? cmd.slice(6).trim() : null;
      loadPacks(true).then((packs) => {
        const lines = want == null
          ? [`current: ${getState().voice}`, 'auto   the premade Commissar pack',
            ...packs.map((p) => `${p.id}   ${p.name} (${Object.values(p.events).reduce((n, f) => n + f.length, 0)} clips)`)]
          : [setVoice(want) ? `voice: ${want}` : 'no such voice: type voices'];
        setLog((l) => [...l, ...out, ...lines].slice(-60));
      });
      return;
    }
    if (cmd === 'help') out.push(...HELP);
    else if (cmd === 'mute') { setMuted(true); out.push('muted'); }
    else if (cmd === 'unmute') { setMuted(false); out.push('unmuted'); }
    else if (cmd === 'clear') { setLog([]); return; }
    else if (cmd === 'exit') { setOpen(false); return; }
    else if (/^[a-z]{3,20}$/.test(cmd)) {  // yarrik, or a voice pack's own summon word
      summon(cmd).then((line) => setLog((l) => [...l, ...out, line].slice(-60)));
      return;
    } else out.push('unknown command');
    setLog((l) => [...l, ...out].slice(-60));
  };

  return (
    <div className="cmd-console-scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
      <div ref={panel} className="cmd-console" role="dialog" aria-modal="true" aria-label="Console" tabIndex={-1}>
        <div className="cmd-log" role="log" aria-live="polite">
          {log.map((l, i) => <div key={i}>{l}</div>)}
          <div ref={logEnd} />
        </div>
        <form onSubmit={(e) => { e.preventDefault(); run(value); setValue(''); }}>
          <input ref={input} value={value} onChange={(e) => setValue(e.target.value)} placeholder="type a command"
            aria-label="Console command" autoComplete="off" autoCapitalize="off" spellCheck={false} />
        </form>
      </div>
    </div>
  );
}
