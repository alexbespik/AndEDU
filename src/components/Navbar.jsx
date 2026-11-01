import React from 'react';
import { 
  BookOpen, Compass, Award, Cpu, Zap, Search, 
  Terminal, Sparkles, CheckCircle2 
} from 'lucide-react';
import { theme } from '../theme';

// Official Linux Tux Vector Silhouette Path from &EDU
const TuxMini = ({ size = 20, color = theme.accentGreen }) => {
  const tuxPath = "M12.504 0c-.155 0-.315.008-.48.021-4.226.333-3.105 4.807-3.17 6.298-.076 1.092-.3 1.953-1.05 3.02-.885 1.051-2.127 2.75-2.716 4.521-.278.832-.41 1.684-.287 2.489a.424.424 0 00-.11.135c-.26.268-.45.6-.663.839-.199.199-.485.267-.797.4-.313.136-.658.269-.864.68-.09.189-.136.394-.132.602 0 .199.027.4.055.536.058.399.116.728.04.97-.249.68-.28 1.145-.106 1.484.174.334.535.47.94.601.81.2 1.91.135 2.774.6.926.466 1.866.67 2.616.47.526-.116.97-.464 1.208-.946.587-.003 1.23-.269 2.26-.334.699-.058 1.574.267 2.577.2.025.134.063.198.114.333l.003.003c.391.778 1.113 1.132 1.884 1.071.771-.06 1.592-.536 2.257-1.306.631-.765 1.683-1.084 2.378-1.503.348-.199.629-.469.649-.853.023-.4-.2-.811-.714-1.376v-.097l-.003-.003c-.17-.2-.25-.535-.338-.926-.085-.401-.182-.786-.492-1.046h-.003c-.059-.054-.123-.067-.188-.135a.357.357 0 00-.19-.064c.431-1.278.264-2.55-.173-3.694-.533-1.41-1.465-2.638-2.175-3.483-.796-1.005-1.576-1.957-1.56-3.368.026-2.152.236-6.133-3.544-6.139z";
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} style={{ flexShrink: 0 }}>
      <path d={tuxPath} />
    </svg>
  );
};

export default function Navbar({ 
  activeTopic, 
  activeTab, 
  setActiveTab, 
  hasSimulation,
  quizCount = 0,
  agentStatus = "Listening",
  studioMode = "physics",
  onSwitchStudioMode
}) {
  const tabs = [
    { id: 'theory', label: 'Theory & Derivations', icon: BookOpen },
    ...(hasSimulation ? [{ id: 'simulation', label: 'Physics Simulation', icon: Compass, badge: 'Interactive' }] : []),
    { id: 'quiz', label: 'Assessment Quiz', icon: Award, count: quizCount },
    { id: 'agent', label: 'Agent Hub', icon: Cpu, badge: 'Dynamic' }
  ];

  return (
    <header style={{
      height: 56,
      background: theme.bgHeader,
      borderBottom: `1px solid ${theme.border}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      zIndex: 100,
      flexShrink: 0
    }}>
      {/* Brand & Studio Mode Switcher */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <TuxMini size={22} color={theme.accentGreen} />
          <span style={{ 
            fontFamily: theme.fontMono, 
            fontWeight: 700, 
            fontSize: '1.05rem', 
            color: theme.textMain,
            letterSpacing: '-0.02em',
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}>
            <span style={{ color: theme.accentGreen }}>&gt;_</span> SciEdu<span style={{ color: theme.accentGold }}>.Studio</span>
          </span>
        </div>

        {/* Global Studio Mode Selector */}
        {onSwitchStudioMode && (
          <div style={{
            display: 'flex',
            background: theme.bgInput,
            border: `1px solid ${theme.border}`,
            borderRadius: 4,
            padding: 2,
            gap: 2
          }}>
            <button
              onClick={() => onSwitchStudioMode('physics')}
              style={{
                background: studioMode === 'physics' ? theme.accentGreen : 'transparent',
                color: studioMode === 'physics' ? '#ffffff' : theme.textDim,
                border: 'none',
                padding: '4px 9px',
                borderRadius: 3,
                fontSize: '11px',
                fontFamily: theme.fontMono,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 4
              }}
              title="Physics & Mechanics Simulation Mode"
            >
              🌌 Physics
            </button>
            <button
              onClick={() => onSwitchStudioMode('code')}
              style={{
                background: studioMode === 'code' ? theme.accentGreen : 'transparent',
                color: studioMode === 'code' ? '#ffffff' : theme.textDim,
                border: 'none',
                padding: '4px 9px',
                borderRadius: 3,
                fontSize: '11px',
                fontFamily: theme.fontMono,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 4
              }}
              title="&EDU Code & Algorithm IDE with Pyodide / Sandbox Execution"
            >
              ⚡ Code IDE
            </button>
            <button
              onClick={() => onSwitchStudioMode('math')}
              style={{
                background: studioMode === 'math' ? theme.accentGreen : 'transparent',
                color: studioMode === 'math' ? '#ffffff' : theme.textDim,
                border: 'none',
                padding: '4px 9px',
                borderRadius: 3,
                fontSize: '11px',
                fontFamily: theme.fontMono,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 4
              }}
              title="&EDU Mathematical Derivations & Proofs Mode"
            >
              ∑ Math
            </button>
          </div>
        )}

        {activeTopic && studioMode === 'physics' && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: theme.bgCard,
            border: `1px solid ${theme.border}`,
            padding: '3px 10px',
            borderRadius: 4,
            fontSize: '0.78rem',
            fontFamily: theme.fontMono,
            color: theme.accentCyan
          }}>
            <span>{activeTopic.category}</span>
            <span style={{ color: theme.textMuted }}>/</span>
            <span style={{ color: theme.textMain, fontWeight: 600 }}>{activeTopic.title}</span>
          </div>
        )}
      </div>

      {/* Center Navigation Tabs */}
      <div style={{ display: 'flex', gap: 6, background: '#0e0e0e', padding: 4, borderRadius: 6, border: `1px solid ${theme.border}` }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                background: isActive ? theme.bgPanel : 'transparent',
                border: isActive ? `1px solid ${theme.borderActive}` : '1px solid transparent',
                color: isActive ? theme.accentGold : theme.textDim,
                borderRadius: 4,
                padding: '6px 14px',
                fontSize: '0.82rem',
                fontFamily: theme.fontMono,
                fontWeight: isActive ? 600 : 400,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                transition: 'all 0.15s ease'
              }}
            >
              <Icon size={14} color={isActive ? theme.accentGold : theme.textMuted} />
              <span>{tab.label}</span>
              {tab.badge && (
                <span style={{
                  fontSize: '0.65rem',
                  background: 'rgba(35, 165, 90, 0.2)',
                  color: theme.accentGreen,
                  padding: '1px 5px',
                  borderRadius: 3,
                  fontWeight: 700
                }}>
                  {tab.badge}
                </span>
              )}
              {tab.count > 0 && (
                <span style={{
                  fontSize: '0.65rem',
                  background: 'rgba(229, 184, 92, 0.2)',
                  color: theme.accentGold,
                  padding: '1px 6px',
                  borderRadius: 10,
                  fontWeight: 700
                }}>
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Right Agent Sync Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          background: 'rgba(35, 165, 90, 0.08)',
          border: '1px solid rgba(35, 165, 90, 0.25)',
          padding: '4px 10px',
          borderRadius: 4,
          fontSize: '0.74rem',
          fontFamily: theme.fontMono,
          color: theme.accentGreen
        }}>
          <span style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: theme.accentGreen,
            boxShadow: `0 0 8px ${theme.accentGreen}`
          }} />
          <span>AGENT READY</span>
        </div>
      </div>
    </header>
  );
}
