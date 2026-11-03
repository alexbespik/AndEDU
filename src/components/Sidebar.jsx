import React, { useMemo, useState } from 'react';
import { BookOpen, Compass, X } from 'lucide-react';

const BUILTIN_SIMS = new Set(['rolling_without_slipping', 'billiard_collisions']);

/** Topic list grouped by course (for generated classes) or by category. */
export default function Sidebar({ topics, selectedTopicId, onSelectTopic, open, onClose }) {
  const [query, setQuery] = useState('');

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const map = new Map();
    for (const t of topics) {
      if (q && !`${t.title} ${t.category} ${t.summary || ''}`.toLowerCase().includes(q)) continue;
      const key = t.source?.courseTitle || t.category || 'Other';
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(t);
    }
    for (const list of map.values()) list.sort((a, b) => (a.source?.classSeq ?? 0) - (b.source?.classSeq ?? 0));
    return [...map.entries()];
  }, [topics, query]);

  return (
    <nav className={`sidebar${open ? ' open' : ''}`} aria-label="Topics">
      <div className="sidebar-search">
        <div className="btn-row" style={{ flexWrap: 'nowrap' }}>
          <label htmlFor="topic-search" className="visually-hidden">Search topics</label>
          <input id="topic-search" className="input" type="search" placeholder="Search topics"
            value={query} onChange={(e) => setQuery(e.target.value)} />
          <button type="button" className="btn btn-quiet btn-icon only-narrow" onClick={onClose} aria-label="Close topic list"><X size={16} /></button>
        </div>
      </div>
      {groups.length === 0 && <p className="sidebar-empty">No topics match “{query}”.</p>}
      {groups.map(([name, list]) => (
        <div key={name} className="sidebar-group">
          <h3>{name}</h3>
          {list.map((t) => {
            const Icon = t.simulation || BUILTIN_SIMS.has(t.simulationType) ? Compass : BookOpen;
            return (
              <button key={t.id} type="button" className="topic-link"
                aria-current={t.id === selectedTopicId ? 'page' : undefined}
                onClick={() => { onSelectTopic(t.id); onClose?.(); }}>
                <Icon size={16} aria-hidden="true" />
                <span>
                  {t.source?.classSeq ? `${t.source.classSeq}. ` : ''}{t.title}
                  <span className="topic-meta">{t.difficulty || 'Lesson'}{t.quiz?.length ? `, ${t.quiz.length} questions` : ''}</span>
                </span>
              </button>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
