import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import TopicViewer from './components/TopicViewer';
import AgyBridgeDrawer from './components/AgyBridgeDrawer';
import rollingTopic from '../content/topics/rolling-without-slipping.json';
import lagrangianTopic from '../content/topics/lagrangian-mechanics.json';
import { theme } from './theme';

export default function App() {
  const initialTopics = [rollingTopic, lagrangianTopic];
  const [topics, setTopics] = useState(initialTopics);
  const [selectedTopicId, setSelectedTopicId] = useState('rolling-without-slipping');
  const [activeTab, setActiveTab] = useState('theory');
  const [agentSyncStatus, setAgentSyncStatus] = useState('Live Connected');

  // Fetch topics from backend API if available, with continuous polling for agent hot-updates
  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const res = await fetch('/api/topics');
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setTopics(data);
          }
        }
      } catch (err) {
        // Fallback to local bundled topics
      }
    };

    fetchTopics();
    const interval = setInterval(fetchTopics, 3000); // Polling every 3s for live agent changes
    return () => clearInterval(interval);
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
      <Navbar 
        activeTopic={activeTopic}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        hasSimulation={Boolean(activeTopic?.simulationType)}
        quizCount={activeTopic?.quiz?.length || 0}
        agentStatus={agentSyncStatus}
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

      {/* Floating AGY Live Companion Bridge */}
      <AgyBridgeDrawer 
        activeTopicId={selectedTopicId}
        onSwitchTab={setActiveTab}
      />
    </div>
  );
}
