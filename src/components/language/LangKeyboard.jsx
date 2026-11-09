// A row of letters a keyboard may lack (German ä ö ü ß), inserted at the cursor of a typed answer.
import React, { useState } from 'react';

const KEYS = { de: ['ä', 'ö', 'ü', 'ß'] };
const upper = (k) => (k === 'ß' ? 'ẞ' : k.toUpperCase());

/** Letter buttons for lang (nothing for languages without extra letters). Shift gives capitals (Ä Ö Ü ẞ). */
export default function LangKeyboard({ lang, inputRef, value, onChange, disabled = false }) {
  const [caps, setCaps] = useState(false);
  const keys = KEYS[String(lang || '').toLowerCase().split('-')[0]];
  if (!keys) return null;
  const insert = (ch) => {
    const el = inputRef?.current;
    const start = el?.selectionStart ?? value.length, end = el?.selectionEnd ?? value.length;
    onChange(value.slice(0, start) + ch + value.slice(end));
    requestAnimationFrame(() => {  // put the cursor right after the new letter
      if (!el) return;
      el.focus();
      el.setSelectionRange(start + ch.length, start + ch.length);
    });
  };
  return (
    <div className="lang-keyboard" role="group" aria-label="Special letters">
      {keys.map((k) => {
        const ch = caps ? upper(k) : k;
        return (
          <button key={k} type="button" className="btn btn-quiet btn-sm lang-key" disabled={disabled}
            onMouseDown={(e) => e.preventDefault()} onClick={() => insert(ch)} aria-label={`Insert ${ch}`}>{ch}</button>
        );
      })}
      <button type="button" className="btn btn-quiet btn-sm lang-key" disabled={disabled} aria-pressed={caps}
        onMouseDown={(e) => e.preventDefault()} onClick={() => setCaps((c) => !c)} aria-label="Capital letters">⇧</button>
    </div>
  );
}
