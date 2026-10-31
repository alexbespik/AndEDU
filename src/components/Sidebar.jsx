import React, { useState } from 'react';
import { 
  Search, BookOpen, RotateCcw, Cpu, Zap, Plus, 
  ChevronRight, Compass, HelpCircle, Layers, Folder,
  CheckCircle2
} from 'lucide-react';
import { theme } from '../theme';

export default function Sidebar({ 
  topics = [], 
  selectedTopicId, 
  onSelectTopic,
  onOpenAgentModal 
}) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredTopics = topics.filter(t => 
    t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (t.summary && t.summary.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // Group by category
  const categories = {};
  filteredTopics.forEach(t => {
    const cat = t.category || 'General Science';
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(t);
  });

  return (
    <aside style={{
      width: 290,
      background: theme.bgSidebar,
      borderRight: `1px solid ${theme.border}`,
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      height: '100%',
      overflow: 'hidden'
    }}>
      {/* Search Bar */}
      <div style={{ padding: '14px 16px', borderBottom: `1px solid ${theme.border}` }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: theme.bgInput,
          border: `1px solid ${theme.border}`,
          borderRadius: 6,
          padding: '7px 10px',
          color: theme.textDim
        }}>
          <Search size={14} color={theme.textMuted} />
          <input
            type="text"
            placeholder="Search topics, formulas..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              background: 'transparent',
              border: 'none',
              color: theme.textMain,
              fontSize: '0.82rem',
              fontFamily: theme.fontMono,
              outline: 'none',
              width: '100%'
            }}
          />
        </div>
      </div>

      {/* Topics List by Category */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 10px' }}>
        {Object.entries(categories).map(([catName, catTopics]) => (
          <div key={catName} style={{ marginBottom: 18 }}>
            <div style={{
              fontSize: '0.72rem',
              fontFamily: theme.fontMono,
              fontWeight: 700,
              color: theme.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              padding: '4px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}>
              <Folder size={12} color={theme.accentGold} />
              <span>{catName}</span>
              <span style={{ fontSize: '0.65rem', color: theme.textDim, marginLeft: 'auto' }}>
                {catTopics.length}
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
              {catTopics.map(topic => {
                const isSelected = topic.id === selectedTopicId;
                return (
                  <button
                    key={topic.id}
                    onClick={() => onSelectTopic(topic.id)}
                    style={{
                      background: isSelected ? 'rgba(229, 184, 92, 0.12)' : 'transparent',
                      border: isSelected ? `1px solid ${theme.borderActive}` : '1px solid transparent',
                      borderRadius: 6,
                      padding: '8px 10px',
                      textAlign: 'left',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 4,
                      transition: 'background 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                      <span style={{
                        fontSize: '0.84rem',
                        fontWeight: isSelected ? 700 : 500,
                        color: isSelected ? theme.accentGold : theme.textMain,
                        fontFamily: isSelected ? theme.fontMono : 'inherit'
                      }}>
                        {topic.title}
                      </span>
                      {topic.simulationType && (
                        <span title="Interactive Simulation Available" style={{ color: theme.accentGreen }}>
                          <Compass size={13} />
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.7rem' }}>
                      <span style={{ color: theme.accentCyan, fontFamily: theme.fontMono }}>
                        {topic.difficulty || 'Physics'}
                      </span>
                      {topic.quiz && (
                        <span style={{ color: theme.textMuted }}>
                          • {topic.quiz.length} Qs
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Autonomous Agent Integration Footer Card */}
      <div style={{
        padding: 12,
        borderTop: `1px solid ${theme.border}`,
        background: theme.bgActivity
      }}>
        <div style={{
          background: theme.bgCard,
          border: `1px dashed ${theme.borderContrast}`,
          borderRadius: 6,
          padding: 10,
          fontSize: '0.75rem',
          color: theme.textDim,
          display: 'flex',
          flexDirection: 'column',
          gap: 6
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: theme.accentGreen, fontWeight: 700, fontFamily: theme.fontMono }}>
            <Zap size={13} /> AGENT HOT INGESTION
          </div>
          <div>
            AI coding agents can stream or drop new JSON topics into <code>content/topics/</code> and they mount live without reloading.
          </div>
        </div>
      </div>
    </aside>
  );
}
