import React, { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import TopicViewer from './components/TopicViewer';
import AgyBridgeDrawer from './components/AgyBridgeDrawer';
import LoginPage from './components/LoginPage';
import CoursesHome from './components/CoursesHome';
import CourseView from './components/CourseView';
import ReviewSession from './components/ReviewSession';
import RewardLayer, { StreakChip } from './components/Rewards';
import rollingTopic from '../content/topics/rolling-without-slipping.json';
import lagrangianTopic from '../content/topics/lagrangian-mechanics.json';
import billiardTopic from '../content/topics/billiard-ball-collisions.json';
import { MessageSquare } from 'lucide-react';
import { api, useAgyEvents, loadProfile, saveProfile, setToken } from './lib/api';

// The IDE and the math workspace load on demand
const EduStudioIDE = lazy(() => import('./components/EduStudioIDE'));
const MathLab = lazy(() => import('./components/MathLab'));
const SubjectWorkspace = lazy(() => import('./components/SubjectWorkspace'));
const AdvisorPage = lazy(() => import('./components/AdvisorPage'));

const FALLBACK_TOPICS = [rollingTopic, billiardTopic, lagrangianTopic];

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
  const [topics, setTopics] = useState(FALLBACK_TOPICS);
  const [selectedTopicId, setSelectedTopicId] = useState(FALLBACK_TOPICS[0].id);
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
  const [mathPush, setMathPush] = useState(null);  // functions or a widget sent by the assistant / MCP tools

  useEffect(() => {
    api('/api/status').then((st) => setAgyCli(Boolean(st.agy_cli_enabled))).catch(() => {});
  }, []);
  const versionRef = useRef(null);

  const toast = useCallback((text) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t.slice(-2), { id, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);

  const fetchTopics = useCallback(async () => {
    try {
      const data = await api('/api/topics');
      if (Array.isArray(data) && data.length) setTopics(data);
    } catch { /* keep what we have */ }
  }, []);

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
      }
      if (!stop) setTimeout(tick, document.hidden ? 8000 : 3000);
    };
    tick();
    return () => { stop = true; };
  }, [fetchTopics]);

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
    else { setSelectedTopicId(t.id); setMode('physics'); }
  }, [toast]);

  useAgyEvents((evt) => {
    const p = evt.payload || {};
    switch (evt.type) {
      case 'SWITCH_TOPIC':
        if (p.mode && p.mode !== 'physics') setMode(p.mode);
        else if (p.topicId) openTopic(p.topicId, p.tab || 'theory');
        break;
      case 'SWITCH_TAB':
        if (p.tab) { setActiveTab(p.tab); setMode((m) => (m === 'class' ? 'class' : 'physics')); }
        break;
      case 'MATH_GRAPH':
        setMathPush({ graph: p, at: evt.seq }); setMode('math');
        break;
      case 'MATH_PREVIEW':
        setMathPush({ spec: p.spec, at: evt.seq }); setMode('math');
        break;
      case 'SWITCH_STUDIO_MODE':
        if (p.mode) setMode(p.mode);
        break;
      case 'SET_SIM_CONFIG':
        setLiveSimConfig({ ...p, _at: evt.seq });
        setActiveTab('simulation');
        setMode((m) => (m === 'class' ? 'class' : 'physics'));
        toast('AGY updated the simulation settings.');
        break;
      case 'TOPIC_UPDATED':
      case 'TOPIC_CREATED':
        fetchTopics();
        if (p.topicId && p.autoSelect === true) setSelectedTopicId(p.topicId);
        if (evt.type === 'TOPIC_CREATED' && p.title && p.autoSelect !== false) toast(`New lesson: ${p.title}`);
        break;
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
    saveProfile(null); setUser(null); setCourseId(null); setMode('home'); setPanelOpen(false);
  }, []);

  useEffect(() => {
    const onExpired = () => { setToken(null); saveProfile(null); setUser(null); setMode('home'); };
    window.addEventListener('andedu:signed-out', onExpired);
    return () => window.removeEventListener('andedu:signed-out', onExpired);
  }, []);
  const switchMode = (m) => { setMode(m); if (m === 'home') setCourseId(null); };
  const openCourse = (id) => { setCourseId(id); setMode('course'); };

  if (!user) return <LoginPage onSignedIn={signIn} />;

  const labTopics = topics.filter((t) => workspaceOf(t) === 'lab');
  const mathTopics = topics.filter((t) => t.source?.courseId && workspaceOf(t) === 'math');
  const activeTopic = labTopics.find((t) => t.id === selectedTopicId) || labTopics[0];
  const classTopic = topics.find((t) => t.id === classTopicId) || null;
  const mathClass = classTopic && workspaceOf(classTopic) === 'math' ? classTopic : null;
  const subjectClass = classTopic && workspaceOf(classTopic) === mode ? classTopic : null;
  const subjectTopics = topics.filter((t) => workspaceOf(t) === mode);  // course classes and library lessons of this subject
  const codeClass = classTopic && workspaceOf(classTopic) === 'code' ? classTopic : null;
  const viewedTopic = mode === 'math' ? mathClass : mode === 'class' ? codeClass : mode === 'history' || mode === 'language' ? subjectClass : activeTopic;
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
        streakChip={<StreakChip progress={progress} onOpen={() => switchMode('home')} />}
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
              <SubjectWorkspace key={mode} kind={mode} classTopic={subjectClass} topics={subjectTopics} onOpenTopic={(id) => openTopic(id)}
                renderClass={(t) => (
                  <TopicViewer key={t.id} embedded topic={t} activeTab={activeTab} setActiveTab={setActiveTab}
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
            <TopicViewer topic={activeTopic} activeTab={activeTab} setActiveTab={setActiveTab}
              liveSimConfig={liveSimConfig} userId={user.id} onOpenCourse={openCourse} {...classNav(activeTopic)} />
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
                  <TopicViewer key={t.id} embedded topic={t} activeTab={activeTab} setActiveTab={setActiveTab}
                    liveSimConfig={liveSimConfig} userId={user.id} onOpenCourse={openCourse} {...classNav(t)} />
                )} />
            </Suspense>
          )}
        </main>

        <AgyBridgeDrawer open={panelOpen} onClose={() => setPanelOpen(false)} activeTopicId={viewedTopic?.id} agyCli={agyCli}
          courseId={mode === 'course' ? courseId : viewedTopic?.source?.courseId} />
      </div>

      {!panelOpen && (
        <button type="button" className={`assistant-fab${mode === 'code' || mode === 'class' ? ' fab-left' : ''}`} onClick={() => setPanelOpen(true)} aria-label={agyCli ? 'Ask AGY' : 'Open the assistant'}>
          <MessageSquare size={20} aria-hidden="true" /><span>{agyCli ? 'Ask AGY' : 'Assistant'}</span>
        </button>
      )}
      <RewardLayer focusMode={progress?.focusMode} onReward={loadProgress} />
      <div className="toast-region" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className="toast">{t.text}</div>)}
      </div>
    </div>
  );
}
