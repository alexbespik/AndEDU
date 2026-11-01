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

export default function App() {
  const initialTopics = [rollingTopic, billiardTopic, lagrangianTopic];
  const [topics, setTopics] = useState(initialTopics);
  const [selectedTopicId, setSelectedTopicId] = useState('billiard-ball-collisions');
  const [activeTab, setActiveTab] = useState('simulation');
  const [studioMode, setStudioMode] = useState('physics'); // 'physics' | 'code' | 'math'
  const [agentSyncStatus, setAgentSyncStatus] = useState('Live Connected');
  const lastEventIdRef = useRef(null);

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

  // 2. Poll for AGY Real-time Control Events (Page Switching, Tab Switching, Topic Navigation)
  useEffect(() => {
    const pollControlEvents = async () => {
      try {
        const res = await fetch('/api/agy/events');
        if (res.ok) {
          const data = await res.json();
          const events = data.events || [];
          if (events.length > 0) {
            const latest = events[events.length - 1];
            if (latest.id !== lastEventIdRef.current) {
              lastEventIdRef.current = latest.id;
              
              // Handle AGY page/topic switching events
              if (latest.type === 'SWITCH_TOPIC') {
                if (latest.payload?.topicId) {
                  setSelectedTopicId(latest.payload.topicId);
                  setStudioMode('physics');
                }
                if (latest.payload?.tab) {
                  setActiveTab(latest.payload.tab);
                }
                if (latest.payload?.mode) {
                  setStudioMode(latest.payload.mode);
                }
              } else if (latest.type === 'SWITCH_TAB') {
                if (latest.payload?.tab) {
                  setActiveTab(latest.payload.tab);
                }
              } else if (latest.type === 'SWITCH_STUDIO_MODE') {
                if (latest.payload?.mode) {
                  setStudioMode(latest.payload.mode);
                }
              } else if (latest.type === 'TOPIC_UPDATED' || latest.type === 'TOPIC_CREATED') {
                fetchTopics();
                if (latest.payload?.topicId && latest.payload?.autoSelect !== false) {
                  setSelectedTopicId(latest.payload.topicId);
                }
              }
            }
          }
        }
      } catch (err) {}
    };

    const evtInterval = setInterval(pollControlEvents, 1200);
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
