// Extra Languages tabs: Stories, Alphabets, Dialogues (AI roleplay items) and Grammar tips.
// Exposed to LanguageLab through EXTRA_LANGUAGE_TABS in ./index.js; each tab gets the language topics.
import React, { useMemo, useState } from 'react';
import Md from '../Md';
import { StoryPlayer, DialogueChat, ScriptMatch } from '../../practice/language_extra';
import { speak, noVoiceHelp, languageName } from '../../lib/speech';
import { reportXp } from '../../lib/engage';
import { SCRIPT_IDS, scriptTable, scriptDrill } from './alphabets';
import { grammarSections, itemsOfType } from './util';

function Empty({ children }) {
  return <p className="notice notice-info" style={{ marginTop: 'var(--space-4)' }}>{children}</p>;
}

/** Pick one entry of a list ({topic, item}) shown as chips. */
function Picker({ entries, current, onPick, label }) {
  return (
    <div className="lx-picker" role="group" aria-label={label}>
      {entries.map(({ topic, item }, i) => (
        <button key={`${topic.id}:${item.id}`} type="button" className="btn btn-quiet btn-sm" aria-pressed={i === current} onClick={() => onPick(i)}>
          {item.title || item.persona || item.prompt}<span className="hint"> · {topic.title}</span>
        </button>
      ))}
    </div>
  );
}

export function StoriesTab({ topics }) {
  const stories = useMemo(() => itemsOfType(topics, 'story'), [topics]);
  const [k, setK] = useState(0);
  const [listenOnly, setListenOnly] = useState(false);
  if (!stories.length) return <Empty>No stories yet. Language classes add them, or an agent can with the add_story tool.</Empty>;
  const cur = stories[Math.min(k, stories.length - 1)];
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      <Picker entries={stories} current={k} onPick={setK} label="Stories" />
      <label className="lx-toggle"><input type="checkbox" checked={listenOnly} onChange={(e) => setListenOnly(e.target.checked)} /> Listen only (hide the text)</label>
      <div className="panel">
        <StoryPlayer key={`${cur.topic.id}:${cur.item.id}`} item={cur.item} listenOnly={listenOnly}
          onResult={(ok) => ok && reportXp('practice_correct', `lang:${cur.topic.id}:${cur.item.id}`)} />
      </div>
    </div>
  );
}

export function AlphabetsTab() {
  const [script, setScript] = useState(SCRIPT_IDS[0]);
  const [drill, setDrill] = useState(null);
  const [note, setNote] = useState(null);
  const table = scriptTable(script);
  const hear = (l) => speak(l.say, table.lang, { rate: 0.75 }).then((r) => setNote(r.ok ? null : r.reason === 'no-voice' ? noVoiceHelp(r.language) : 'This browser cannot read text aloud.'));
  const choose = (id) => { setScript(id); setDrill(null); setNote(null); };
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      <div className="lx-picker" role="group" aria-label="Writing systems">
        {SCRIPT_IDS.map((id) => (
          <button key={id} type="button" className="btn btn-quiet btn-sm" aria-pressed={id === script} onClick={() => choose(id)}>{scriptTable(id).label}</button>
        ))}
      </div>
      <p className="hint">{table.label}: tap a letter to hear it ({languageName(table.lang)} voice).</p>
      {note && <p className="notice notice-info">{note}</p>}
      <div className="lx-glyphs" lang={table.lang}>
        {table.letters.map((l) => (
          <button key={l.glyph} type="button" className="lx-glyph" onClick={() => hear(l)} aria-label={`${l.glyph}, ${l.roman}`}>
            <span className="lx-glyph-char">{l.glyph}</span><span className="lx-glyph-roman">{l.roman}</span>
          </button>
        ))}
      </div>
      <div className="btn-row">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => setDrill(scriptDrill(script))}>{drill ? 'New drill' : 'Quick drill'}</button>
      </div>
      {drill && (
        <div className="panel stack-sm">
          <strong>{drill.prompt}</strong>
          <ScriptMatch key={drill.id} item={drill} onResult={(ok) => ok && reportXp('practice_correct', `lang:alphabet:${script}`)} />
        </div>
      )}
    </div>
  );
}

export function DialoguesTab({ topics }) {
  const dialogues = useMemo(() => itemsOfType(topics, 'dialogue'), [topics]);
  const [k, setK] = useState(0);
  if (!dialogues.length) return <Empty>No dialogues yet. Language classes add them, or an agent can with the add_dialogue tool. The Roleplay tab has ready-made scenarios.</Empty>;
  const cur = dialogues[Math.min(k, dialogues.length - 1)];
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      <Picker entries={dialogues} current={k} onPick={setK} label="Dialogues" />
      <div className="panel"><DialogueChat key={`${cur.topic.id}:${cur.item.id}`} item={cur.item} /></div>
    </div>
  );
}

export function GrammarTipsTab({ topics }) {
  const units = useMemo(() => (topics || []).map((t) => ({ topic: t, sections: grammarSections(t.markdownContent) })).filter((u) => u.sections.length), [topics]);
  if (!units.length) return <Empty>No grammar notes yet. Lesson sections with "Grammar" or "Tip" in their heading are collected here.</Empty>;
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      {units.map(({ topic, sections }) => (
        <section key={topic.id} className="panel stack-sm">
          <h3 style={{ margin: 0 }}>{topic.title}</h3>
          {sections.map((s, i) => (
            <details key={i} className="lx-tip-section" open={i === 0}>
              <summary>{s.heading}</summary>
              <Md>{s.body}</Md>
            </details>
          ))}
        </section>
      ))}
    </div>
  );
}
