import React from 'react';
import { GraduationCap, FlaskConical, Code2, Sigma, Menu, Landmark, Languages, Compass } from 'lucide-react';
import AccountMenu from './AccountMenu';

const MODES = [
  { id: 'home', label: 'My courses', icon: GraduationCap },
  { id: 'physics', label: 'Lab', icon: FlaskConical, title: 'Physics and chemistry lessons and simulations' },
  { id: 'code', label: 'IDE', icon: Code2, title: 'Write and run code' },
  { id: 'math', label: 'Math', icon: Sigma, title: 'Graphing, LaTeX notes and practice' },
  { id: 'history', label: 'History', icon: Landmark, title: 'Timelines, flashcards and history classes' },
  { id: 'language', label: 'Languages', icon: Languages, title: 'Languages and linguistics: flashcards read aloud, pronunciation, IPA' },
  { id: 'advisor', label: 'Advisor', icon: Compass, title: 'Course advisor: your record, the catalog, readiness checks' },
];

/** W&M masthead: brand, mode switch, connection, AGY toggle and profile. Every row wraps; nothing overlaps. */
export default function Navbar({ studioMode, onSwitchStudioMode, user, onSignOut, online, panelOpen, onTogglePanel, onOpenTopics, assistantName = 'Assistant', streakChip }) {
  return (
    <header className="masthead">
      <button type="button" className="brand" onClick={() => onSwitchStudioMode('home')} aria-label="&.edu, go to my courses">
        <span className="brand-monogram" aria-hidden="true">&amp;</span>
        <span className="brand-mark">.edu</span>
      </button>

      <nav className="modes" aria-label="Workspace">
        {studioMode === 'physics' && (
          <button type="button" className="mode only-narrow" onClick={onOpenTopics}>
            <Menu size={16} aria-hidden="true" /> Topics
          </button>
        )}
        {MODES.map(({ id, label, icon: Icon, title }) => (
          <button key={id} type="button" className="mode" aria-pressed={studioMode === id} title={title} onClick={() => onSwitchStudioMode(id)}>
            <Icon size={16} aria-hidden="true" /> {label}
          </button>
        ))}
      </nav>

      <div className="masthead-right">
        {streakChip}
        <AccountMenu user={user} online={online} onSignOut={onSignOut} />
      </div>
    </header>
  );
}
