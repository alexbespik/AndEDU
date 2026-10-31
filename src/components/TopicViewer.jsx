import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import { 
  BookOpen, Compass, Award, Copy, Check, ExternalLink, 
  Sparkles, Terminal, FileCode, CheckCircle2, AlertTriangle,
  Lightbulb, RefreshCw
} from 'lucide-react';
import { theme } from '../theme';
import RollingWithoutSlippingSim from '../simulations/RollingWithoutSlippingSim';
import QuizEngine from './QuizEngine';
import MermaidViewer from './MermaidViewer';

export default function TopicViewer({ topic, activeTab, setActiveTab }) {
  const [copiedFormula, setCopiedFormula] = useState(null);

  if (!topic) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: theme.textMuted,
        fontFamily: theme.fontMono,
        fontSize: '0.9rem'
      }}>
        Select a topic from the sidebar to begin.
      </div>
    );
  }

  const copyFormula = (f, idx) => {
    navigator.clipboard.writeText(f);
    setCopiedFormula(idx);
    setTimeout(() => setCopiedFormula(null), 2000);
  };

  return (
    <div style={{ flex: 1, height: '100%', overflowY: 'auto', background: theme.bgApp, padding: '24px 32px' }}>
      <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
        
        {/* Header Title & Meta */}
        <div style={{ borderBottom: `1px solid ${theme.border}`, paddingBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{
              background: 'rgba(35, 165, 90, 0.15)',
              color: theme.accentGreen,
              border: `1px solid rgba(35, 165, 90, 0.35)`,
              borderRadius: 4,
              padding: '2px 8px',
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700
            }}>
              {topic.category}
            </span>
            <span style={{
              background: 'rgba(229, 184, 92, 0.15)',
              color: theme.accentGold,
              border: `1px solid rgba(229, 184, 92, 0.35)`,
              borderRadius: 4,
              padding: '2px 8px',
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700
            }}>
              {topic.difficulty || 'Undergraduate'}
            </span>
          </div>

          <h1 style={{
            fontSize: '2rem',
            fontWeight: 800,
            color: theme.textMain,
            fontFamily: theme.fontMono,
            letterSpacing: '-0.02em',
            marginBottom: 8
          }}>
            {topic.title}
          </h1>

          <p style={{ color: theme.textDim, fontSize: '0.95rem', lineHeight: 1.5 }}>
            {topic.summary}
          </p>
        </div>

        {/* Tab 1: Theory & Mathematical Derivations */}
        {activeTab === 'theory' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* Quick Notation & Formula Cheat Sheet */}
            {topic.cheatSheet && topic.cheatSheet.length > 0 && (
              <div style={{
                background: theme.bgPanel,
                border: `1px solid ${theme.border}`,
                borderRadius: 8,
                padding: 16
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 12,
                  fontFamily: theme.fontMono,
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  color: theme.accentGold
                }}>
                  <span>⚡ KEY SCIENTIFIC NOTATIONS & CONSTRAINTS</span>
                </div>

                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                  gap: 10
                }}>
                  {topic.cheatSheet.map((item, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: theme.bgCard,
                        border: `1px solid ${theme.border}`,
                        borderRadius: 6,
                        padding: '8px 12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 12
                      }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: '0.72rem', color: theme.textMuted, fontFamily: theme.fontMono }}>
                          {item.label}
                        </span>
                        <div style={{ fontSize: '0.95rem', color: theme.textMain }}>
                          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {`$${item.formula}$`}
                          </ReactMarkdown>
                        </div>
                      </div>

                      <button
                        onClick={() => copyFormula(item.formula, idx)}
                        title="Copy LaTeX Formula"
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: copiedFormula === idx ? theme.accentGreen : theme.textMuted,
                          cursor: 'pointer',
                          padding: 4
                        }}
                      >
                        {copiedFormula === idx ? <Check size={14} /> : <Copy size={14} />}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Mermaid Architecture Flowchart */}
            {topic.mermaid && (
              <div>
                <div style={{
                  fontSize: '0.8rem',
                  fontFamily: theme.fontMono,
                  fontWeight: 700,
                  color: theme.accentCyan,
                  marginBottom: 6
                }}>
                  STRUCTURED REASONING FLOW:
                </div>
                <MermaidViewer chart={topic.mermaid} />
              </div>
            )}

            {/* Main Markdown Body with KaTeX & Tables */}
            <article className="markdown-body">
              <ReactMarkdown
                remarkPlugins={[remarkMath, remarkGfm]}
                rehypePlugins={[rehypeKatex]}
              >
                {topic.markdownContent}
              </ReactMarkdown>
            </article>

            {/* Next Steps: Interactive Prompt */}
            <div style={{
              background: 'rgba(35, 165, 90, 0.08)',
              border: `1px solid rgba(35, 165, 90, 0.3)`,
              borderRadius: 8,
              padding: 20,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16
            }}>
              <div>
                <h4 style={{ color: theme.accentGreen, fontFamily: theme.fontMono, fontSize: '0.95rem', marginBottom: 4 }}>
                  Ready to test your intuition?
                </h4>
                <p style={{ color: theme.textDim, fontSize: '0.84rem' }}>
                  Open the real-time physics simulation to play with velocity vectors or take the assessment quiz.
                </p>
              </div>

              <div style={{ display: 'flex', gap: 10 }}>
                {topic.simulationType && (
                  <button
                    onClick={() => setActiveTab('simulation')}
                    style={{
                      background: theme.accentGreen,
                      color: '#000000',
                      border: 'none',
                      borderRadius: 4,
                      padding: '8px 16px',
                      fontSize: '0.82rem',
                      fontFamily: theme.fontMono,
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    Open Simulation
                  </button>
                )}
                {topic.quiz && (
                  <button
                    onClick={() => setActiveTab('quiz')}
                    style={{
                      background: theme.accentGold,
                      color: '#000000',
                      border: 'none',
                      borderRadius: 4,
                      padding: '8px 16px',
                      fontSize: '0.82rem',
                      fontFamily: theme.fontMono,
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    Take Quiz ({topic.quiz.length})
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Interactive Simulation */}
        {activeTab === 'simulation' && (
          <div>
            {topic.simulationType === 'rolling_without_slipping' ? (
              <RollingWithoutSlippingSim />
            ) : (
              <div style={{
                background: theme.bgPanel,
                border: `1px solid ${theme.border}`,
                borderRadius: 8,
                padding: 32,
                textAlign: 'center',
                color: theme.textMuted,
                fontFamily: theme.fontMono
              }}>
                No specialized simulation wired for this topic yet.
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Interactive Assessment Quiz */}
        {activeTab === 'quiz' && (
          <QuizEngine 
            quiz={topic.quiz} 
            topicId={topic.id}
          />
        )}

        {/* Tab 4: Agent Hub & Dynamic Protocol */}
        {activeTab === 'agent' && (
          <div style={{
            background: theme.bgPanel,
            border: `1px solid ${theme.border}`,
            borderRadius: 8,
            padding: 24,
            display: 'flex',
            flexDirection: 'column',
            gap: 20
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: theme.accentGreen, fontFamily: theme.fontMono, fontWeight: 700 }}>
              <Terminal size={18} />
              <span>AUTONOMOUS CODING AGENT PROTOCOL</span>
            </div>

            <p style={{ color: theme.textDim, fontSize: '0.88rem', lineHeight: 1.6 }}>
              This platform was built from the ground up to support continuous, autonomous AI coding agents (such as Google Antigravity, Claude Code, Cursor, or background loop agents). An agent can generate new scientific explanations, LaTeX derivations, and assessment quizzes simply by writing a JSON file or calling the local API.
            </p>

            {/* Agent Command Example */}
            <div style={{
              background: '#0d0d0d',
              border: `1px solid ${theme.border}`,
              borderRadius: 6,
              padding: 14,
              fontFamily: theme.fontMono,
              fontSize: '0.82rem'
            }}>
              <div style={{ color: theme.accentGold, marginBottom: 6 }}># Agent CLI Ingestion:</div>
              <code style={{ color: theme.accentGreen }}>
                python3 scripts/agent_add_topic.py --file my_topic.json
              </code>
            </div>

            {/* REST API Endpoints */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: '0.82rem', fontFamily: theme.fontMono, fontWeight: 700, color: theme.accentCyan }}>
                AVAILABLE AGENT ENDPOINTS:
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, fontSize: '0.8rem', fontFamily: theme.fontMono }}>
                <span style={{ color: theme.accentGreen }}>GET /api/topics</span>
                <span style={{ color: theme.textDim }}>List all topics & active metadata</span>
                <span style={{ color: theme.accentGold }}>POST /api/topics</span>
                <span style={{ color: theme.textDim }}>Dynamically ingest or update a topic</span>
                <span style={{ color: theme.accentPink }}>POST /api/quiz/submit</span>
                <span style={{ color: theme.textDim }}>Record user assessment answers & metrics</span>
                <span style={{ color: theme.accentCyan }}>GET /api/status</span>
                <span style={{ color: theme.textDim }}>Poll agent status & hot reload state</span>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
