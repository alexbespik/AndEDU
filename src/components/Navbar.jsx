import React, { useEffect, useRef, useState } from 'react';
import { GraduationCap, FlaskConical, Code2, Sigma, Menu, Landmark, Languages, Compass, BookOpen, ChevronDown } from 'lucide-react';
import AccountMenu from './AccountMenu';

// Workspaces by mode id (ids and course.workspace values never change; only the navigation groups them)
const SUBJECTS = {
  physics: { label: 'Lab', icon: FlaskConical, title: 'Physics and chemistry lessons and simulations' },
  code: { label: 'IDE', icon: Code2, title: 'Write and run code' },
  math: { label: 'Math', icon: Sigma, title: 'Graphing, LaTeX notes and practice' },
  history: { label: 'History', icon: Landmark, title: 'Timelines, flashcards and history classes' },
  language: { label: 'Languages', icon: Languages, title: 'Languages and linguistics: flashcards read aloud, pronunciation, IPA' },
};

// Similar disciplines share one tab. A group with one subject is a plain tab; with more, it opens a menu.
// A new subject (Philosophy, Statistics, Biology...) joins a group's members instead of adding a tab.
const NAV = [
  { mode: 'home', label: 'My courses', icon: GraduationCap },
  { group: 'math', label: 'Math', icon: Sigma, members: ['math'] },
  { group: 'it', label: 'IT', icon: Code2, members: ['code'] },
  { group: 'lab', label: 'Lab', icon: FlaskConical, members: ['physics'] },
  { group: 'liberal', label: 'Liberal arts', icon: BookOpen, members: ['history', 'language'] },
  { mode: 'advisor', label: 'Advisor', icon: Compass, title: 'Course advisor: your record, the catalog, readiness checks' },
];

const lastKey = (group) => `andedu.navGroup.${group}`;
function readLast(group, members) {
  try {
    const v = localStorage.getItem(lastKey(group));
    return members.includes(v) ? v : members[0];
  } catch {
    return members[0];
  }
}

/** A tab for a group of subjects. From another workspace one click returns to the subject used last; in the group,
 * the tab opens a menu of its subjects. */
function GroupMenu({ item, studioMode, onSwitch }) {
  const { group, label, icon: Icon, members } = item;
  const [open, setOpen] = useState(false);
  const [alignRight, setAlignRight] = useState(false);  // a tab on the right half opens its menu leftwards
  const [last, setLast] = useState(() => readLast(group, members));
  const wrap = useRef(null);
  const trigger = useRef(null);
  const active = members.includes(studioMode);
  const current = active ? studioMode : last;
  const popId = `nav-group-${group}`;

  // remember the subject however it was opened (this menu, a course, the assistant)
  useEffect(() => {
    if (!active) return;
    setLast(studioMode);
    try { localStorage.setItem(lastKey(group), studioMode); } catch { /* storage blocked: only a convenience */ }
  }, [active, studioMode, group]);

  useEffect(() => {
    if (!open) return undefined;
    // a click or focus landing outside closes it (focusin, not blur: Safari doesn't focus clicked buttons)
    const away = (e) => { if (!wrap.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => {
      if (e.key !== 'Escape') return;
      const inside = wrap.current?.contains(document.activeElement);
      setOpen(false);
      if (inside) trigger.current?.focus();
    };
    document.addEventListener('pointerdown', away);
    document.addEventListener('focusin', away);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('pointerdown', away);
      document.removeEventListener('focusin', away);
      document.removeEventListener('keydown', esc);
    };
  }, [open]);

  const pick = (id) => { setOpen(false); onSwitch(id); trigger.current?.focus(); };
  const press = () => {
    if (!active) { onSwitch(last); return; }  // back to the subject used last
    const r = trigger.current?.getBoundingClientRect();
    setAlignRight(Boolean(r) && r.left > window.innerWidth / 2);
    setOpen((o) => !o);
  };
  return (
    <div className="mode-group" ref={wrap}>
      <button ref={trigger} type="button" className="mode" data-active={active || undefined}
        aria-expanded={active ? open : undefined} aria-controls={open ? popId : undefined}
        aria-label={active ? `${label}, ${SUBJECTS[current].label}: choose a subject` : `${label}: ${SUBJECTS[current].label}`}
        title={active ? 'Choose a subject' : `Open ${SUBJECTS[current].label}`}
        onClick={press}>
        <Icon size={16} aria-hidden="true" /> {label}
        <span className="mode-sub" aria-hidden="true">· {SUBJECTS[current].label}</span>
        {active && <ChevronDown size={14} className="mode-chev" aria-hidden="true" />}
      </button>
      {open && (
        <div id={popId} className={`menu mode-pop${alignRight ? ' mode-pop-right' : ''}`} role="group" aria-label={`${label} subjects`}>
          {members.map((id) => {
            const { label: subject, icon: SubIcon, title } = SUBJECTS[id];
            return (
              <button key={id} type="button" title={title} aria-current={studioMode === id ? 'true' : undefined} onClick={() => pick(id)}>
                <SubIcon size={16} aria-hidden="true" /> {subject}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

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
        {NAV.map((item) => {
          if (item.members?.length > 1) {
            return <GroupMenu key={item.group} item={item} studioMode={studioMode} onSwitch={onSwitchStudioMode} />;
          }
          const id = item.mode || item.members[0];
          const { label, icon: Icon } = item;
          const title = item.title || SUBJECTS[id]?.title;
          return (
            <button key={id} type="button" className="mode" aria-pressed={studioMode === id} title={title} onClick={() => onSwitchStudioMode(id)}>
              <Icon size={16} aria-hidden="true" /> {label}
            </button>
          );
        })}
      </nav>

      <div className="masthead-right">
        {streakChip}
        <AccountMenu user={user} online={online} onSignOut={onSignOut} />
      </div>
    </header>
  );
}
