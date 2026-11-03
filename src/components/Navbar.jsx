import React from 'react';
import { GraduationCap, BookOpen, Code2, Sigma, MessageSquare, LogOut, Menu } from 'lucide-react';
import ThemeSwitch from './ThemeSwitch';

const MODES = [
  { id: 'home', label: 'My courses', icon: GraduationCap },
  { id: 'physics', label: 'Studio', icon: BookOpen },
  { id: 'code', label: 'Code', icon: Code2 },
  { id: 'math', label: 'Math', icon: Sigma },
];

/** W&M masthead: brand, mode switch, connection, AGY toggle and profile. Every row wraps; nothing overlaps. */
export default function Navbar({ studioMode, onSwitchStudioMode, user, onSignOut, online, panelOpen, onTogglePanel, onOpenTopics, assistantName = 'Assistant' }) {
  return (
    <header className="masthead">
      <button type="button" className="brand" onClick={() => onSwitchStudioMode('home')} aria-label="&.edu LAB, go to my courses">
        <span className="brand-monogram" aria-hidden="true">&amp;</span>
        <span className="brand-mark">.edu LAB</span>
      </button>

      <nav className="modes" aria-label="Workspace">
        {studioMode === 'physics' && (
          <button type="button" className="mode only-narrow" onClick={onOpenTopics}>
            <Menu size={16} aria-hidden="true" /> Topics
          </button>
        )}
        {MODES.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" className="mode" aria-pressed={studioMode === id} onClick={() => onSwitchStudioMode(id)}>
            <Icon size={16} aria-hidden="true" /> {label}
          </button>
        ))}
      </nav>

      <div className="masthead-right">
        <ThemeSwitch />
        <span className="conn" data-state={online ? 'online' : 'offline'} role="status">
          {online ? 'Connected' : 'Backend offline'}
        </span>
        <button type="button" className="btn btn-quiet btn-sm" aria-pressed={panelOpen} onClick={onTogglePanel}>
          <MessageSquare size={15} aria-hidden="true" /> {panelOpen ? `Hide ${assistantName}` : assistantName === 'AGY' ? 'Ask AGY' : 'Assistant'}
        </button>
        {user && (
          <>
            <span className="conn">Signed in as {user.name}</span>
            <button type="button" className="btn btn-quiet btn-sm" onClick={onSignOut}>
              <LogOut size={15} aria-hidden="true" /> Sign out
            </button>
          </>
        )}
      </div>
    </header>
  );
}
