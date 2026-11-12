import React, { Suspense, lazy, useCallback, useEffect, useRef, useState, startTransition } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import AgyBridgeDrawer from './components/AgyBridgeDrawer';
import LoginPage from './components/LoginPage';
import CoursesHome from './components/CoursesHome';
import CourseView from './components/CourseView';
import ReviewSession from './components/ReviewSession';
import DesktopKeySetup, { KEY_NOTE } from './components/DesktopKeySetup';
import RewardLayer, { StreakChip } from './components/Rewards';
import { BookOpen, FlaskConical, Compass } from 'lucide-react';
import { TuxIcon } from './components/PenguinShadow';
import { api, useAgyEvents, loadProfile, saveProfile, setToken } from './lib/api';

// The lesson viewer, the IDE and the workspaces load on demand
const TopicViewer = lazy(() => import('./components/TopicViewer'));
const ChemKit = lazy(() => import('./components/ChemKit'));
const EduStudioIDE = lazy(() => import('./components/EduStudioIDE'));
const MathLab = lazy(() => import('./components/MathLab'));
const SubjectWorkspace = lazy(() => import('./components/SubjectWorkspace'));
const AdvisorPage = lazy(() => import('./components/AdvisorPage'));

// Its own boundary at every use site, so a first chunk load never suspends (and unmounts) MathLab or a workspace
const LessonView = (props) => <Suspense fallback={<p className="hint">Loading the lesson…</p>}><TopicViewer {...props} /></Suspense>;

// Bundled sample lessons, loaded only when the server has none to give (offline, error or an empty library)
const DEFAULT_TOPIC_ID = 'rolling-without-slipping';
const loadFallbackModules = () => Promise.all([
  import('../content/topics/rolling-without-slipping.json'),
  import('../content/topics/billiard-ball-collisions.json'),
  import('../content/topics/lagrangian-mechanics.json'),
]).then((ms) => ms.map((m) => m.default));

const topicSig = new WeakMap();  // topic object -> its JSON, computed once per object
const sigOf = (t) => { let v = topicSig.get(t); if (v === undefined) { v = JSON.stringify(t); topicSig.set(t, v); } return v; };

/** The new list, reusing the previous object for every lesson whose content did not change (and the old array if none did). */
export function mergeTopics(prev, next) {
  const old = new Map(prev.map((t) => [t.id, t]));
  let changed = prev.length !== next.length;
  const out = next.map((t, i) => {
    const p = old.get(t.id);
    if (p && sigOf(p) === sigOf(t)) { if (prev[i] !== p) changed = true; return p; }
    changed = true;
    return t;
  });
  return changed ? out : prev;
}

/**
 * Where a topic opens. Course classes: their course's workspace (the server always sets source.workspace).
 * Library topics: an explicit `workspace`, or Math for a math-kit simulation; otherwise Lab. No guessing from
 * text here: physics lessons mention geometry, integrals and vectors too.
 */
export const workspaceOf = (t) => {
  if (!t) return 'lab';
  if (t.source?.workspace) return t.source.workspace;
  if (t.workspace) return t.workspace;
  if (!t.source?.courseId && t.simulation?.kind === 'math') return 'math';
  return 'lab';
};

export default function App() {
  const [user, setUser] = useState(loadProfile);
  const [mode, setMode] = useState('home'); // home | course | physics | code | math
  const [courseId, setCourseId] = useState(null);
  const [topics, setTopics] = useState([]);
  const [selectedTopicId, setSelectedTopicId] = useState(DEFAULT_TOPIC_ID);
  const [labView, setLabView] = useState('lesson'); // lesson | chem (the Chemistry kit)
  const [activeTab, setActiveTab] = useState('theory');
  const [liveSimConfig, setLiveSimConfig] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [online, setOnline] = useState(true);
  const [toasts, setToasts] = useState([]);
  const [agyCli, setAgyCli] = useState(false);
  const [ideRequest, setIdeRequest] = useState(null); // a practice set asked for in My courses
  const [homePreset, setHomePreset] = useState(null);
  const [progress, setProgress] = useState(null); // streak, daily goal, quests (engage.py)
  const [workspaceTab, setWorkspaceTab] = useState(null);  // {tab, at} for History/Languages, sent by MCP tools
  const [mathPush, setMathPush] = useState(null);  // functions or a widget sent by the assistant / MCP tools
  const [pendingPrompt, setPendingPrompt] = useState(null);
  const [desktopKey, setDesktopKey] = useState(null);  // desktop app: {reason: missing|rejected|manage, activeJobs} shows the key card
  const keyCardDismissed = useRef(false);  // "Later" on a rejected key: don't reopen it on every window focus

  useEffect(() => {
    const onAgyAsk = (e) => {
      if (e.detail?.prompt) {
        setPendingPrompt({ prompt: e.detail.prompt, level: e.detail.level });
        setPanelOpen(true);
      }
    };
    window.addEventListener('agy:ask', onAgyAsk);
    return () => window.removeEventListener('agy:ask', onAgyAsk);
  }, []);

  useEffect(() => {
    api('/api/status').then((st) => {
      setAgyCli(Boolean(st.agy_cli_enabled));
      if (window.sciedu?.isDesktop && (!st.gemini_configured || st.gemini_key_invalid)) {
        setDesktopKey({ activeJobs: st.active_jobs || 0, reason: st.gemini_configured ? 'rejected' : 'missing' });
      }
    }).catch(() => {});
  }, []);
  // fetch the lesson viewer's chunk once signed in, so the first lesson opens without a loading step
  useEffect(() => { if (user) import('./components/TopicViewer'); }, [user]);
  const versionRef = useRef(null);

  const toast = useCallback((text) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t.slice(-2), { id, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);

  // One refetch at a time (the version poll and TOPIC_UPDATED events often fire together). Unchanged lessons keep
  // their objects, so memoized views skip them, and the update renders as a transition that never blocks input.
  const fallbackLoad = useRef(null);  // loads the sample lessons once; server topics always win the merge
  const loadFallbackTopics = useCallback(() => {
    if (!fallbackLoad.current) {
      fallbackLoad.current = loadFallbackModules().catch((err) => { fallbackLoad.current = null; throw err; });  // retry on the next miss
    }
    return fallbackLoad.current
      .then((fb) => setTopics((p) => (p.length ? p : fb)))
      .catch((err) => console.warn('Sample lessons could not be loaded', err));
  }, []);

  const topicsFetch = useRef(null);
  const topicsDirty = useRef(false);  // asked again while a fetch was running: that fetch may predate the change
  const fetchTopics = useCallback(() => {
    if (topicsFetch.current) { topicsDirty.current = true; return topicsFetch.current; }
    const run = () => api('/api/topics')
      .then((data) => {
        if (Array.isArray(data) && data.length) startTransition(() => setTopics((prev) => mergeTopics(prev, data)));
        else loadFallbackTopics();
      })
      .catch(() => { loadFallbackTopics(); /* keep what we have, or the sample lessons if that is nothing */ })
      .then(() => { if (topicsDirty.current) { topicsDirty.current = false; return run(); } return undefined; });
    topicsFetch.current = run().finally(() => { topicsFetch.current = null; });
    return topicsFetch.current;
  }, [loadFallbackTopics]);

  // Cheap change detection: refetch the (large) topic list only when files changed
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const { version } = await api('/api/topics/version');
        setOnline(true);
        if (version !== versionRef.current) {
          versionRef.current = version;
          await fetchTopics();
        }
      } catch {
        setOnline(false);
        loadFallbackTopics();  // no-op once any lessons are loaded
      }
      if (!stop) setTimeout(tick, document.hidden ? 8000 : 3000);
    };
    tick();
    return () => { stop = true; };
  }, [fetchTopics, loadFallbackTopics]);

  // Course classes open in their own view (any subject); Lab is the physics/chemistry library.
  // A topic missing from the list (just written, or the list is still loading) is fetched, never swapped for another.
  const [classTopicId, setClassTopicId] = useState(null);
  const topicsRef = useRef(topics);
  topicsRef.current = topics;
  const openTopic = useCallback(async (id, tab = 'theory') => {
    if (!id) return;
    let t = topicsRef.current.find((x) => x.id === id);
    if (!t) {
      try {
        t = await api(`/api/topics/${encodeURIComponent(id)}`);
        setTopics((ts) => (ts.some((x) => x.id === t.id) ? ts : [...ts, t]));
      } catch {
        toast('That lesson could not be found. It may still be being written.');
        return;
      }
    }
    setActiveTab(tab);
    const ws = workspaceOf(t);
    if (ws === 'math' || ws === 'history' || ws === 'language') { setClassTopicId(t.id); setMode(ws); }  // library lessons too
    else if (ws === 'code') { setClassTopicId(t.id); setMode('class'); }
    else { setSelectedTopicId(t.id); setLabView('lesson'); setMode('physics'); }
  }, [toast]);

  const labTopics = topics.filter((t) => workspaceOf(t) === 'lab');
  const mathTopics = topics.filter((t) => t.source?.courseId && workspaceOf(t) === 'math');
  const activeTopic = labTopics.find((t) => t.id === selectedTopicId) || labTopics[0];
  const classTopic = topics.find((t) => t.id === classTopicId) || null;
  const mathClass = classTopic && workspaceOf(classTopic) === 'math' ? classTopic : null;
  const subjectClass = classTopic && workspaceOf(classTopic) === mode ? classTopic : null;
  const subjectTopics = topics.filter((t) => workspaceOf(t) === mode);  // course classes and library lessons of this subject
  const codeClass = classTopic && workspaceOf(classTopic) === 'code' ? classTopic : null;
  const viewedTopic = mode === 'math' ? mathClass : mode === 'class' ? codeClass : mode === 'history' || mode === 'language' ? subjectClass : activeTopic;

  const [pendingNav, setPendingNav] = useState(null);

  useEffect(() => {
    if (!pendingNav) return;
    const timer = setTimeout(() => setPendingNav(null), 14000);
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setPendingNav(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [pendingNav]);

  useAgyEvents((evt) => {
    const p = evt.payload || {};
    switch (evt.type) {
      case 'GEMINI_KEY_INVALID':
        keyCardDismissed.current = false;
        openKeyCard('rejected');
        break;
      case 'SWITCH_TOPIC': {
        if (p.topicId) {
          const targetTopic = topics.find((x) => x.id === p.topicId);
          const targetTitle = targetTopic?.title || p.topicId;
          const targetTab = p.tab || 'theory';
          const isCurrentTopic = viewedTopic?.id === p.topicId;
          const isCurrentTab = activeTab === targetTab;

          if (!isCurrentTopic || !isCurrentTab) {
            setPendingNav({
              id: `topic-${p.topicId}-${evt.seq || Date.now()}`,
              message: `AGY recommends switching to "${targetTitle}"${p.tab ? ` (${targetTab})` : ''}.`,
              actionLabel: 'Switch now',
              onConfirm: () => openTopic(p.topicId, targetTab),
            });
          }
        } else if (p.mode && mode !== p.mode) {
          setPendingNav({
            id: `mode-${p.mode}-${evt.seq || Date.now()}`,
            message: `AGY recommends switching to ${p.mode} mode.`,
            actionLabel: 'Switch mode',
            onConfirm: () => setMode(p.mode),
          });
        }
        break;
      }
      case 'SWITCH_TAB': {
        if (p.tab && activeTab !== p.tab) {
          setPendingNav({
            id: `tab-${p.tab}-${evt.seq || Date.now()}`,
            message: `AGY recommends switching to the "${p.tab}" tab.`,
            actionLabel: `View ${p.tab}`,
            onConfirm: () => {
              setActiveTab(p.tab);
              setLabView('lesson');
              setMode((m) => (['class', 'math', 'history', 'language'].includes(m) ? m : 'physics'));
            },
          });
        }
        break;
      }
      case 'MATH_GRAPH': {
        setMathPush({ graph: p, at: evt.seq });
        if (mode !== 'math') {
          setPendingNav({
            id: `math-graph-${evt.seq || Date.now()}`,
            message: 'AGY prepared a math graph. Open in Math Lab?',
            actionLabel: 'Open Math Lab',
            onConfirm: () => setMode('math'),
          });
        }
        break;
      }
      case 'MATH_PREVIEW':
      case 'GEOMETRY_PREVIEW': {
        setMathPush({ spec: p.spec, at: evt.seq });
        if (mode !== 'math') {
          setPendingNav({
            id: `geometry-preview-${evt.seq || Date.now()}`,
            message: evt.type === 'GEOMETRY_PREVIEW' ? 'AGY prepared a geometry/FBD diagram. Open in Math Lab?' : 'AGY prepared a math preview. Open in Math Lab?',
            actionLabel: 'Open Math Lab',
            onConfirm: () => setMode('math'),
          });
        }
        break;
      }
      case 'SWITCH_STUDIO_MODE': {
        const needsModeChange = p.mode && mode !== p.mode;
        const needsTabChange = p.tab && workspaceTab?.tab !== p.tab;
        if (needsModeChange || needsTabChange) {
          setPendingNav({
            id: `studio-${p.mode || ''}-${evt.seq || Date.now()}`,
            message: `AGY recommends switching to ${p.mode || 'workspace'}${p.tab ? ` (${p.tab})` : ''}.`,
            actionLabel: 'Switch now',
            onConfirm: () => {
              if (p.mode) setMode(p.mode);
              if (p.tab) setWorkspaceTab({ ...p, tab: p.tab, mode: p.sessionMode || p.mode, unitId: p.unitId, at: evt.seq });
            },
          });
        }
        break;
      }
      case 'SET_SIM_CONFIG': {
        setLiveSimConfig({ ...p, _at: evt.seq });
        const isViewingSim = activeTab === 'simulation' && ((mode === 'physics' && labView === 'lesson') || mode === 'class');
        if (isViewingSim) {
          toast('AGY updated the simulation settings.');
        } else {
          setPendingNav({
            id: `sim-config-${evt.seq || Date.now()}`,
            message: 'AGY updated simulation parameters. View simulation?',
            actionLabel: 'View simulation',
            onConfirm: () => {
              setActiveTab('simulation');
              setLabView('lesson');
              setMode((m) => (m === 'class' ? 'class' : 'physics'));
            },
          });
        }
        break;
      }
      case 'TOPIC_UPDATED':
      case 'TOPIC_CREATED': {
        fetchTopics();
        if (p.topicId && p.autoSelect === true && viewedTopic?.id !== p.topicId) {
          setPendingNav({
            id: `topic-created-${p.topicId}-${evt.seq || Date.now()}`,
            message: `AGY created a new lesson: "${p.title || p.topicId}". Open it?`,
            actionLabel: 'Open lesson',
            onConfirm: () => openTopic(p.topicId),
          });
        }
        if (evt.type === 'TOPIC_CREATED' && p.title && p.autoSelect !== false) toast(`New lesson: ${p.title}`);
        break;
      }
      case 'CLASS_ADAPTED':
        toast(`Class ${p.seq} is being rewritten ${p.direction === 'easier' ? 'with more support' : 'to be more challenging'} after your ${Math.round(p.score * 100)}% quiz.`);
        break;
      case 'JOB_UPDATE':
        if (p.status === 'error' && p.kind === 'simulation') toast(`Simulation failed: ${p.error}`);
        if (p.status === 'done' && p.kind === 'simulation') toast('A new simulation is ready.');
        break;
      default:
    }
  });

  const openKeyCard = useCallback((reason) => {
    if (!window.sciedu?.isDesktop) return;
    api('/api/status')
      .then((st) => setDesktopKey({ activeJobs: st.active_jobs || 0, reason }))
      .catch(() => setDesktopKey({ activeJobs: 0, reason }));
  }, []);
  // desktop: the account menu opens the card to replace or remove the key; a key Google rejected while the
  // window was in the background shows up when it comes back
  useEffect(() => {
    if (!window.sciedu?.isDesktop) return undefined;
    const onManage = () => openKeyCard('manage');
    const onVisible = () => {
      if (document.hidden || keyCardDismissed.current) return;
      api('/api/status').then((st) => {
        if (st.gemini_key_invalid) setDesktopKey((k) => k || { activeJobs: st.active_jobs || 0, reason: 'rejected' });
      }).catch(() => {});
    };
    window.addEventListener('sciedu:key-setup', onManage);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('sciedu:key-setup', onManage);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [openKeyCard]);
  useEffect(() => {
    let note = null;
    try { note = sessionStorage.getItem(KEY_NOTE); sessionStorage.removeItem(KEY_NOTE); } catch { /* no storage */ }
    if (note) toast(note);
  }, [toast]);
  const loadProgress = useCallback(() => {
    if (!user?.id) return;
    api(`/api/engage/${user.id}`).then(setProgress).catch(() => {});
  }, [user?.id]);
  useEffect(() => { loadProgress(); }, [loadProgress, mode]);
  // a new day can start while the tab is open
  useEffect(() => {
    const onVisible = () => { if (!document.hidden) loadProgress(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [loadProgress]);

  const signIn = (u) => { saveProfile(u); setUser(u); setMode('home'); };
  const signOut = useCallback(() => {
    api('/api/auth/logout', { method: 'POST' }).catch(() => {});
    setToken(null);
    saveProfile(null); setUser(null); setCourseId(null); setProgress(null); setMode('home'); setPanelOpen(false);
  }, []);

  useEffect(() => {
    const onExpired = () => { setToken(null); saveProfile(null); setUser(null); setProgress(null); setMode('home'); };
    window.addEventListener('andedu:signed-out', onExpired);
    return () => window.removeEventListener('andedu:signed-out', onExpired);
  }, []);
  const switchMode = (m) => { setMode(m); if (m === 'home') setCourseId(null); };
  const openCourse = (id) => { setCourseId(id); setMode('course'); };

  if (!user) return <LoginPage onSignedIn={signIn} />;

  // previous/next class for whichever course class is on screen
  const siblingsOf = (t) => (t?.source?.courseId
    ? topics.filter((x) => x.source?.courseId === t.source.courseId).sort((a, b) => (a.source.classSeq || 0) - (b.source.classSeq || 0))
    : []);
  const classNav = (t) => {
    const sib = siblingsOf(t), i = sib.findIndex((x) => x.id === t?.id);
    return i < 0 ? {} : {
      prevClass: sib[i - 1], nextClass: sib[i + 1], onHome: () => switchMode('home'),
      onOpenClass: (id) => { openTopic(id); document.getElementById('main')?.scrollTo(0, 0); },
    };
  };
  const showSidebar = mode === 'physics';
  const ideMode = mode === 'code';
  const navMode = mode === 'class' ? 'code' : mode === 'course' || mode === 'review' ? 'home' : mode;

  return (
    <div className="app">
      <Navbar
        studioMode={navMode}
        onSwitchStudioMode={switchMode}
        user={user}
        onSignOut={signOut}
        online={online}
        panelOpen={panelOpen}
        onTogglePanel={() => setPanelOpen((o) => !o)}
        assistantName={agyCli ? 'AGY' : 'Assistant'}
        onOpenTopics={() => setSidebarOpen(true)}
        streakChip={(
          <StreakChip
            progress={progress}
            onOpen={() => {
              if (mode === 'home') return;
              setPendingNav({
                id: `open-home-${Date.now()}`,
                message: 'Switch to My courses dashboard?',
                actionLabel: 'Go to My courses',
                onConfirm: () => switchMode('home'),
              });
            }}
          />
        )}
      />

      <div className={`workspace${showSidebar ? '' : ' no-sidebar'}${panelOpen ? ' has-panel' : ''}`}>
        {showSidebar && (
          <Sidebar topics={labTopics} selectedTopicId={activeTopic?.id} open={sidebarOpen}
            onClose={() => setSidebarOpen(false)} onSelectTopic={(id) => openTopic(id)} />
        )}

        <main className="main" id="main">
          {mode === 'home' && (
            <CoursesHome user={user} onOpenCourse={openCourse} initialPreset={homePreset}
              progress={progress} onProgress={setProgress} onOpenTopic={(id) => openTopic(id)} onReview={() => setMode('review')}
              onCodePractice={(req) => { setIdeRequest(req); setMode('code'); }} />
          )}
          {(mode === 'history' || mode === 'language') && (
            <Suspense fallback={<div className="page"><p className="hint">Loading…</p></div>}>
              <SubjectWorkspace key={mode} kind={mode} requestedTab={workspaceTab} classTopic={subjectClass} topics={subjectTopics} onOpenTopic={(id) => openTopic(id)}
                renderClass={(t) => (
                  <LessonView key={t.id} embedded topic={t} activeTab={activeTab} setActiveTab={setActiveTab}
                    liveSimConfig={liveSimConfig} userId={user.id} onOpenCourse={openCourse} {...classNav(t)} />
                )} />
            </Suspense>
          )}
          {mode === 'advisor' && (
            <Suspense fallback={<div className="page"><p className="hint">Loading…</p></div>}>
              <AdvisorPage user={user} onOpenCourse={openCourse} />
            </Suspense>
          )}
          {mode === 'review' && <ReviewSession userId={user.id} onDone={() => switchMode('home')} />}
          {mode === 'course' && courseId && (
            <CourseView key={courseId} courseId={courseId} onBack={() => switchMode('home')} onOpenTopic={(id) => openTopic(id)} />
          )}
          {mode === 'physics' && (
            <div className="page">
              <div className="btn-row" role="group" aria-label="Lab view">
                <button type="button" className={`btn btn-sm ${labView === 'lesson' ? 'btn-secondary' : 'btn-quiet'}`}
                  aria-pressed={labView === 'lesson'} onClick={() => setLabView('lesson')}>
                  <BookOpen size={14} aria-hidden="true" /> Lesson
                </button>
                <button type="button" className={`btn btn-sm ${labView === 'chem' ? 'btn-secondary' : 'btn-quiet'}`}
                  aria-pressed={labView === 'chem'} onClick={() => setLabView('chem')}>
                  <FlaskConical size={14} aria-hidden="true" /> Chemistry kit
                </button>
              </div>
              {labView === 'chem' ? (
                <section aria-labelledby="chem-kit-title">
                  <header className="page-head">
                    <div>
                      <h1 id="chem-kit-title">Chemistry kit</h1>
                      <p>Interactive chemistry widgets: reaction rates, equilibrium, titration, gas laws and more. Press Lesson, or pick a topic from the list, to go back to the lesson.</p>
                    </div>
                  </header>
                  <Suspense fallback={<p className="hint">Loading the Chemistry kit…</p>}>
                    <ChemKit />
                  </Suspense>
                </section>
              ) : activeTopic ? (
                <LessonView embedded topic={activeTopic} activeTab={activeTab} setActiveTab={setActiveTab}
                  liveSimConfig={liveSimConfig} userId={user.id} onOpenCourse={openCourse} {...classNav(activeTopic)} />
              ) : <p className="hint">Loading lessons…</p>}
            </div>
          )}
          {mode === 'class' && (codeClass ? (
            <Suspense fallback={<div className="page"><p className="hint">Loading the IDE…</p></div>}>
              <EduStudioIDE initialMode="code" classTopic={codeClass} {...classNav(codeClass)} userId={user.id} onOpenTopic={(id) => openTopic(id)} onSwitchToPhysics={() => setMode('physics')} />
            </Suspense>
          ) : <div className="page"><p className="hint">Loading the class…</p></div>)}
          {ideMode && (
            <Suspense fallback={<div className="page"><p className="hint">Loading the IDE…</p></div>}>
              <EduStudioIDE initialMode="code" onSwitchToPhysics={() => setMode('physics')} request={ideRequest}
                onNewPracticeSet={() => { setHomePreset({ intent: 'code', at: Date.now() }); setMode('home'); }} />
            </Suspense>
          )}
          {mode === 'math' && (
            <Suspense fallback={<div className="page"><p className="hint">Loading Math…</p></div>}>
              <MathLab user={user} classTopic={mathClass} mathTopics={mathTopics} onOpenTopic={(id) => openTopic(id)} push={mathPush}
                renderClass={(t) => (
                  <LessonView key={t.id} embedded topic={t} activeTab={activeTab} setActiveTab={setActiveTab}
                    liveSimConfig={liveSimConfig} userId={user.id} onOpenCourse={openCourse} {...classNav(t)} />
                )} />
            </Suspense>
          )}
        </main>

        <AgyBridgeDrawer open={panelOpen} onClose={() => setPanelOpen(false)} activeTopicId={viewedTopic?.id} agyCli={agyCli}
          courseId={mode === 'course' ? courseId : viewedTopic?.source?.courseId}
          pendingPrompt={pendingPrompt} onClearPendingPrompt={() => setPendingPrompt(null)} />
      </div>

      {!panelOpen && (
        <button type="button" className={`assistant-fab${mode === 'code' || mode === 'class' ? ' fab-left' : ''}`} onClick={() => setPanelOpen(true)} aria-label={agyCli ? 'Ask AGY' : 'Open the assistant'}>
          <TuxIcon size={22} /><span>{agyCli ? 'Ask AGY' : 'Assistant'}</span>
        </button>
      )}
      {pendingNav && (
        <aside className="nav-proposal-banner" role="alert" aria-live="polite">
          <div className="nav-proposal-content">
            <Compass size={18} className="nav-proposal-icon" aria-hidden="true" />
            <span className="nav-proposal-text">{pendingNav.message}</span>
          </div>
          <div className="nav-proposal-actions">
            <button
              type="button"
              className="btn btn-sm btn-primary nav-proposal-confirm"
              onClick={() => {
                const fn = pendingNav.onConfirm;
                setPendingNav(null);
                fn?.();
              }}
            >
              {pendingNav.actionLabel || 'Switch'}
            </button>
            <button
              type="button"
              className="btn btn-sm btn-quiet nav-proposal-dismiss"
              onClick={() => setPendingNav(null)}
              aria-label="Dismiss navigation suggestion"
            >
              Dismiss
            </button>
          </div>
        </aside>
      )}
      <RewardLayer focusMode={progress?.focusMode} onReward={loadProgress} />
      {desktopKey && (
        <DesktopKeySetup key={desktopKey.reason} reason={desktopKey.reason} activeJobs={desktopKey.activeJobs}
          onClose={() => { keyCardDismissed.current = true; setDesktopKey(null); }} />
      )}
      <div className="toast-region" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className="toast">{t.text}</div>)}
      </div>
    </div>
  );
}
