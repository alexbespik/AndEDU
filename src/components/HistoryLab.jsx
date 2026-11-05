import React, { useEffect, useMemo, useState } from 'react';
import { BookOpen, GraduationCap, Layers, CalendarRange, Zap, ShieldAlert, FileText, Map as MapIcon, Users, Gamepad2 } from 'lucide-react';
import { CoursesTab } from './MathLab';
import { FlashcardDeck } from './Activities';
import HistoryCrisisLab from './HistoryCrisisLab';
import PrimarySourceLab from './PrimarySourceLab';
import WorkspaceShell from './WorkspaceShell';
import HistoryTimeline from './history/HistoryTimeline';
import { MapTab, SourcesTab, FiguresTab, GamesTab } from './history/HistoryTabs';

let handledRequest = null;

/**
 * History workspace: history course classes open here next to a merged timeline (era bands, zoom), a map of the
 * places in every class, crisis simulations, primary sources with their questions, historical figures to talk to,
 * a daily games mix, and every flashcard.
 */
export default function HistoryLab({ classTopic, topics = [], onOpenTopic, renderClass, requestedTab }) {
  const [tab, setTab] = useState(classTopic ? 'class' : 'courses');
  useEffect(() => { if (classTopic) setTab('class'); }, [classTopic?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!requestedTab?.tab || requestedTab.at === handledRequest) return;
    handledRequest = requestedTab.at;  // a remount must not replay an old request
    setTab(requestedTab.tab);
  }, [requestedTab?.at]); // eslint-disable-line react-hooks/exhaustive-deps
  const cards = useMemo(() => topics.flatMap((t) => (t.flashcards || []).map((c) => ({ ...c, _t: t.id }))), [topics]);
  const events = useMemo(() => topics.flatMap((t) => t.timeline || []).sort((a, b) => a.year - b.year), [topics]);
  const tabs = [
    ...(classTopic ? [{ id: 'class', label: `Class ${classTopic.source?.classSeq ?? ''}`.trim(), icon: BookOpen }] : []),
    { id: 'courses', label: 'Courses', icon: GraduationCap },
    { id: 'crisis', label: 'Crisis Simulator', icon: ShieldAlert },
    { id: 'sources', label: 'Primary Sources', icon: FileText },
    { id: 'map', label: 'Map', icon: MapIcon },
    { id: 'figures', label: 'Figures', icon: Users },
    { id: 'games', label: 'Games', icon: Gamepad2 },
    { id: 'cards', label: `All flashcards${cards.length ? ` (${cards.length})` : ''}`, icon: Layers },
    { id: 'timeline', label: 'Timeline', icon: CalendarRange },
  ];
  const current = tabs.some((t) => t.id === tab) ? tab : 'courses';
  return (
    <WorkspaceShell kind="history" title="History" tabs={tabs} current={current} onTab={setTab}
      intro="Your history classes with counterfactual crisis simulations, primary source investigations, a map of the places you have studied, historical figures to interview, daily games, a timeline of everything you have studied, and flashcards."
      footer={current === 'courses' && topics.some((t) => (t.quiz || []).length >= 3) && (
        <p className="hint"><Zap size={13} aria-hidden="true" /> Every class with 3 or more quiz questions has a Speed round tab.</p>
      )}>
      {current === 'class' && classTopic && renderClass(classTopic)}
      {current === 'courses' && <CoursesTab topics={topics} onOpenTopic={onOpenTopic} activeId={classTopic?.id} empty="No history courses yet. Start one from My courses: its classes open here." />}
      {current === 'crisis' && (
        <div style={{ marginTop: 'var(--space-4)' }}>
          <HistoryCrisisLab topic={classTopic} initialScenarioId={requestedTab?.crisisId} />
        </div>
      )}
      {current === 'sources' && (
        <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
          <SourcesTab topics={topics} />
          <PrimarySourceLab topic={classTopic} initialDocId={requestedTab?.docId} />
        </div>
      )}
      {current === 'map' && <div style={{ marginTop: 'var(--space-4)' }}><MapTab topics={topics} onOpenTopic={onOpenTopic} /></div>}
      {current === 'figures' && <div style={{ marginTop: 'var(--space-4)' }}><FiguresTab topics={topics} /></div>}
      {current === 'games' && <div style={{ marginTop: 'var(--space-4)' }}><GamesTab topics={topics} events={events} /></div>}
      {current === 'cards' && <div style={{ marginTop: 'var(--space-4)' }}><FlashcardDeck key={cards.length} cards={cards} topicId="history-all" /></div>}
      {current === 'timeline' && (
        <div style={{ marginTop: 'var(--space-4)' }}>
          <HistoryTimeline events={events} topicId="history-all" initialMode={requestedTab?.challenge ? 'challenge' : 'view'} />
        </div>
      )}
    </WorkspaceShell>
  );
}
