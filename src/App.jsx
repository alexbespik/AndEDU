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
import { api, useAgyEvents, loadProfile, saveProfile, setToken } from './lib/api';

// The IDE and the math workspace load on demand
const EduStudioIDE = lazy(() => import('./components/EduStudioIDE'));
const MathLab = lazy(() => import('./components/MathLab'));

const FALLBACK_TOPICS = [rollingTopic, billiardTopic, lagrangianTopic];

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
  const [progress, setProgress] = useState(null); // streak, daily goal, quests (engage.py)  // e.g. the IDE's "New practice set" opens the hub on Coding practice

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

  const openTopic = useCallback((id, tab = 'theory') => {
    setSelectedTopicId(id);
    setActiveTab(tab);
    setMode('physics');
  }, []);

  useAgyEvents((evt) => {
    const p = evt.payload || {};
    switch (evt.type) {
      case 'SWITCH_TOPIC':
        if (p.topicId) setSelectedTopicId(p.topicId);
        if (p.tab) setActiveTab(p.tab);
        setMode(p.mode && p.mode !== 'physics' ? p.mode : 'physics');
        break;
      case 'SWITCH_TAB':
        if (p.tab) { setActiveTab(p.tab); setMode('physics'); }
        break;
      case 'SWITCH_STUDIO_MODE':
        if (p.mode) setMode(p.mode);
        break;
      case 'SET_SIM_CONFIG':
        setLiveSimConfig({ ...p, _at: evt.seq });
        setActiveTab('simulation');
        setMode('physics');
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

  const activeTopic = topics.find((t) => t.id === selectedTopicId) || topics[0];
  const showSidebar = mode === 'physics';
  const ideMode = mode === 'code';
  const navMode = mode === 'course' ? 'home' : mode;

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
          <Sidebar topics={topics} selectedTopicId={activeTopic?.id} open={sidebarOpen}
            onClose={() => setSidebarOpen(false)} onSelectTopic={(id) => openTopic(id)} />
        )}

        <main className="main" id="main">
          {mode === 'home' && (
            <CoursesHome user={user} onOpenCourse={openCourse} initialPreset={homePreset}
              progress={progress} onProgress={setProgress} onOpenTopic={(id) => openTopic(id)} onReview={() => setMode('review')}
              onCodePractice={(req) => { setIdeRequest(req); setMode('code'); }} />
          )}
          {mode === 'review' && <ReviewSession userId={user.id} onDone={() => switchMode('home')} />}
          {mode === 'course' && courseId && (
            <CourseView key={courseId} courseId={courseId} onBack={() => switchMode('home')} onOpenTopic={(id) => openTopic(id)} />
          )}
          {mode === 'physics' && (
            <TopicViewer topic={activeTopic} activeTab={activeTab} setActiveTab={setActiveTab}
              liveSimConfig={liveSimConfig} userId={user.id} onOpenCourse={openCourse} />
          )}
          {ideMode && (
            <Suspense fallback={<div className="page"><p className="hint">Loading the IDE…</p></div>}>
              <EduStudioIDE initialMode="code" onSwitchToPhysics={() => setMode('physics')} request={ideRequest}
                onNewPracticeSet={() => { setHomePreset({ intent: 'code', at: Date.now() }); setMode('home'); }} />
            </Suspense>
          )}
          {mode === 'math' && (
            <Suspense fallback={<div className="page"><p className="hint">Loading Math…</p></div>}>
              <MathLab user={user} />
            </Suspense>
          )}
        </main>

        <AgyBridgeDrawer open={panelOpen} onClose={() => setPanelOpen(false)} activeTopicId={activeTopic?.id} agyCli={agyCli}
          courseId={mode === 'course' ? courseId : mode === 'physics' ? activeTopic?.source?.courseId : undefined} />
      </div>

      <RewardLayer focusMode={progress?.focusMode} onReward={loadProgress} />
      <div className="toast-region" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className="toast">{t.text}</div>)}
      </div>
    </div>
  );
}
