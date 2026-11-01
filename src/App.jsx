import React, { useState, useEffect, useRef } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import TopicViewer from './components/TopicViewer';
import AgyBridgeDrawer from './components/AgyBridgeDrawer';
import EduStudioIDE from './components/EduStudioIDE';
import rollingTopic from '../content/topics/rolling-without-slipping.json';
import lagrangianTopic from '../content/topics/lagrangian-mechanics.json';
import billiardTopic from '../content/topics/billiard-ball-collisions.json';
import { theme } from './theme';
import { Sparkles } from 'lucide-react';

export default function App() {
  const initialTopics = [rollingTopic, billiardTopic, lagrangianTopic];
  const [topics, setTopics] = useState(initialTopics);
  const [selectedTopicId, setSelectedTopicId] = useState('billiard-ball-collisions');
  const [activeTab, setActiveTab] = useState('simulation');
  const [studioMode, setStudioMode] = useState('physics'); // 'physics' | 'code' | 'math'
  const [agentSyncStatus, setAgentSyncStatus] = useState('Live Connected');
  const [liveSimConfig, setLiveSimConfig] = useState(null);
  const [toastMsg, setToastMsg] = useState(null);
  
  const processedEventIdsRef = useRef(new Set());

  // 1. Fetch topics with hot-reload polling
  const fetchTopics = async () => {
    try {
      const res = await fetch('/api/topics');
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setTopics(data);
        }
      }
    } catch (err) {}
  };

  useEffect(() => {
    fetchTopics();
    const interval = setInterval(fetchTopics, 2500);
    return () => clearInterval(interval);
  }, []);

  // 2. Poll for AGY Real-time Control Events (Processes EVERY queued event, never misses any)
  useEffect(() => {
    const pollControlEvents = async () => {
      try {
        const res = await fetch('/api/agy/events');
        if (res.ok) {
          const data = await res.json();
          const events = data.events || [];
          
          for (const evt of events) {
            if (!evt || !evt.id || processedEventIdsRef.current.has(evt.id)) {
              continue;
            }
            processedEventIdsRef.current.add(evt.id);
            if (processedEventIdsRef.current.size > 200) {
              const firstId = processedEventIdsRef.current.values().next().value;
              processedEventIdsRef.current.delete(firstId);
            }

            // Execute Real-Time Event Actions
            if (evt.type === 'SWITCH_TOPIC') {
              if (evt.payload?.topicId) {
                setSelectedTopicId(evt.payload.topicId);
                setStudioMode('physics');
              }
              if (evt.payload?.tab) {
                setActiveTab(evt.payload.tab);
              }
              if (evt.payload?.mode) {
                setStudioMode(evt.payload.mode);
              }
              setToastMsg(`⚡ Navigated to ${evt.payload?.topicId || 'lesson'} (${evt.payload?.tab || 'active tab'})`);
              setTimeout(() => setToastMsg(null), 3500);
            } else if (evt.type === 'SWITCH_TAB') {
              if (evt.payload?.tab) {
                setActiveTab(evt.payload.tab);
              }
              setToastMsg(`⚡ Switched to tab: ${evt.payload.tab}`);
              setTimeout(() => setToastMsg(null), 3000);
            } else if (evt.type === 'SET_SIM_CONFIG') {
              if (evt.payload) {
                setLiveSimConfig(evt.payload);
                setActiveTab('simulation');
                setStudioMode('physics');
                setToastMsg(`🎛️ Simulation Parameters Updated: e=${evt.payload.restitution ?? 'dynamic'}, offset=${evt.payload.impact_offset ?? 'dynamic'}`);
                setTimeout(() => setToastMsg(null), 4000);
              }
            } else if (evt.type === 'SWITCH_STUDIO_MODE') {
              if (evt.payload?.mode) {
                setStudioMode(evt.payload.mode);
              }
            } else if (evt.type === 'TOPIC_UPDATED' || evt.type === 'TOPIC_CREATED') {
              fetchTopics();
              if (evt.payload?.topicId && evt.payload?.autoSelect !== false) {
                setSelectedTopicId(evt.payload.topicId);
                setToastMsg(`📖 Lesson Loaded: ${evt.payload.title || evt.payload.topicId}`);
                setTimeout(() => setToastMsg(null), 3500);
              }
            }
          }
        }
      } catch (err) {}
    };

    const evtInterval = setInterval(pollControlEvents, 800);
    return () => clearInterval(evtInterval);
  }, []);

  const activeTopic = topics.find(t => t.id === selectedTopicId) || topics[0];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      width: '100vw',
      background: theme.bgApp,
      color: theme.textMain,
      overflow: 'hidden',
      position: 'relative'
    }}>
      {/* Real-time Agent Action Toast Banner */}
      {toastMsg && (
        <div style={{
          position: 'fixed',
          top: 66,
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(20, 20, 20, 0.94)',
          border: `1px solid ${theme.borderActive}`,
          borderRadius: 8,
          padding: '8px 18px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.8), 0 0 15px rgba(229, 184, 92, 0.2)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontFamily: theme.fontMono,
          fontSize: '0.82rem',
          color: theme.accentGold,
          backdropFilter: 'blur(8px)',
          animation: 'fadeIn 0.2s ease-out'
        }}>
          <Sparkles size={15} color={theme.accentGold} />
          <span>{toastMsg}</span>
        </div>
      )}

      {studioMode === 'physics' ? (
        <>
          <Navbar 
            activeTopic={activeTopic}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            hasSimulation={Boolean(activeTopic?.simulationType)}
            quizCount={activeTopic?.quiz?.length || 0}
            agentStatus={agentSyncStatus}
            studioMode={studioMode}
            onSwitchStudioMode={setStudioMode}
          />

          <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
            <Sidebar 
              topics={topics}
              selectedTopicId={selectedTopicId}
              onSelectTopic={(id) => {
                setSelectedTopicId(id);
                setActiveTab('theory');
              }}
            />

            <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <TopicViewer 
                topic={activeTopic}
                activeTab={activeTab}
                setActiveTab={setActiveTab}
                liveSimConfig={liveSimConfig}
              />
            </main>
          </div>
        </>
      ) : (
        <EduStudioIDE 
          initialMode={studioMode}
          onSwitchToPhysics={() => setStudioMode('physics')}
        />
      )}

      {/* Floating AGY Live Companion Bridge */}
      <AgyBridgeDrawer 
        activeTopicId={selectedTopicId}
        onSwitchTab={(tab) => {
          setStudioMode('physics');
          setActiveTab(tab);
        }}
      />
    </div>
  );
}
