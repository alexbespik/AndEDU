import React, { useEffect, useState } from 'react';
import { Monitor, Sun, Moon } from 'lucide-react';

const KEY = 'andedu_lab_theme';
const OPTIONS = [
  { id: 'system', label: 'System', icon: Monitor },
  { id: 'light', label: 'Light', icon: Sun },
  { id: 'dark', label: 'Dark', icon: Moon },
];

function readChoice() {
  try { return localStorage.getItem(KEY) || 'system'; } catch { return 'system'; }
}

export function applyTheme(choice) {
  const root = document.documentElement;
  if (choice === 'light' || choice === 'dark') root.dataset.theme = choice;
  else delete root.dataset.theme;
}

/** System / Light / Dark. "System" leaves data-theme unset so prefers-color-scheme decides. */
export default function ThemeSwitch() {
  const [choice, setChoice] = useState(readChoice);

  useEffect(() => {
    applyTheme(choice);
    try { localStorage.setItem(KEY, choice); } catch { /* storage blocked: applies to this tab */ }
  }, [choice]);

  return (
    <div className="theme-switch" role="group" aria-label="Color theme">
      {OPTIONS.map(({ id, label, icon: Icon }) => (
        <button key={id} type="button" aria-pressed={choice === id} onClick={() => setChoice(id)} title={`${label} theme`}>
          <Icon size={14} aria-hidden="true" />
          <span className="visually-hidden">{label}</span>
        </button>
      ))}
    </div>
  );
}
