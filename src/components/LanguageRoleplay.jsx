import React, { useEffect, useRef, useState } from 'react';
import {
  Coffee,
  Hotel,
  Compass,
  ShoppingBag,
  Car,
  Utensils,
  Volume2,
  Snail,
  Mic,
  MicOff,
  Square,
  Send,
  RotateCcw,
  Sparkles,
  ArrowLeft,
  Globe,
  Loader2,
  CheckCircle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import Md from './Md';
import { speak, canRecognize, recognize, LANGUAGES, languageName, RECOGNITION_NOTICE } from '../lib/speech';
import { api } from '../lib/api';

const SCENARIOS = [
  {
    id: 'cafe',
    title: 'At the Café',
    icon: Coffee,
    level: 'A1-A2',
    partner: 'Barista',
    goal: 'Order your drink and a pastry, specify milk or sugar, and pay the bill.',
  },
  {
    id: 'hotel',
    title: 'Hotel Check-in',
    icon: Hotel,
    level: 'A2',
    partner: 'Front Desk Receptionist',
    goal: 'Check in with your reservation, ask about breakfast hours and get your keycard.',
  },
  {
    id: 'directions',
    title: 'Asking for Directions',
    icon: Compass,
    level: 'A2-B1',
    partner: 'Local Resident',
    goal: 'Ask how to reach the central train station or museum on foot and confirm details.',
  },
  {
    id: 'market',
    title: 'Farmers Market',
    icon: ShoppingBag,
    level: 'A2',
    partner: 'Market Vendor',
    goal: 'Select fresh fruits and vegetables, ask about prices, and negotiate quantities.',
  },
  {
    id: 'taxi',
    title: 'Taking a Taxi',
    icon: Car,
    level: 'A1-A2',
    partner: 'Taxi Driver',
    goal: 'Give your destination, check travel time, and handle payment and luggage.',
  },
  {
    id: 'restaurant',
    title: 'Dinner at a Restaurant',
    icon: Utensils,
    level: 'B1',
    partner: 'Server',
    goal: 'Request a table, ask for recommendations, order dishes and ask for the check.',
  },
];

const UNAVAILABLE = () => ({
  id: `ai-${Date.now()}`,
  sender: 'ai',
  text: "Your conversation partner isn't available right now (no connection or the daily model limit was reached). Try again in a moment.",
  translation: null,
  feedback: null,
  showTranslation: false,
});

export default function LanguageRoleplay({ defaultLang = 'es' }) {
  const [lang, setLang] = useState(defaultLang);
  const [activeScenario, setActiveScenario] = useState(null);
  const [messages, setMessages] = useState([]); // [{id, sender: 'ai'|'user', text, translation, feedback, showTranslation}]
  const [suggestions, setSuggestions] = useState([]);
  const [latestFeedback, setLatestFeedback] = useState(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [listening, setListening] = useState(false);
  const [audioNote, setAudioNote] = useState(null);
  const [micError, setMicError] = useState(null);

  const logRef = useRef(null);
  const inputRef = useRef(null);
  const micHandle = useRef(null);
  const scenarioRun = useRef(0);  // the latest scenario wins when the student switches quickly

  // Auto-scroll when messages update
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages, sending]);

  // Clean up mic on unmount
  useEffect(() => {
    return () => {
      micHandle.current?.stop();
    };
  }, []);

  const selectScenario = async (sc) => {
    const run = ++scenarioRun.current;
    setActiveScenario(sc);
    setMessages([]);
    setSuggestions([]);
    setLatestFeedback(null);
    setFeedbackOpen(false);
    setInput('');
    setSending(true);

    try {
      const res = await api('/api/language/roleplay', {
        method: 'POST',
        body: {
          scenario: sc.title,
          target_lang: lang,
          user_message: '',
          history: [],
          level: sc.level,
        },
      });
      if (run !== scenarioRun.current) return;
      const opening = {
        id: `ai-${Date.now()}`,
        sender: 'ai',
        text: res.reply,
        translation: res.translation,
        feedback: res.feedback,
        showTranslation: false,
      };
      setMessages([opening]);
      setSuggestions(res.suggested_replies || []);
      if (res.feedback) {
        setLatestFeedback(res.feedback);
      }
    } catch {
      // no fake target-language reply: say plainly that the partner is unavailable
      if (run !== scenarioRun.current) return;
      setMessages([UNAVAILABLE()]);
    } finally {
      if (run === scenarioRun.current) setSending(false);
    }
  };

  const sendMessage = async (textToSend) => {
    const text = (textToSend ?? input).trim();
    if (!text || sending || !activeScenario) return;
    const run = scenarioRun.current;

    setInput('');
    setSending(true);
    setSuggestions([]);

    const userMsg = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text,
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const historyPayload = messages.map((m) => ({
        role: m.sender === 'user' ? 'user' : 'model',
        text: m.text,
      }));

      const res = await api('/api/language/roleplay', {
        method: 'POST',
        body: {
          scenario: activeScenario.title,
          target_lang: lang,
          user_message: text,
          history: historyPayload,
          level: activeScenario.level,
        },
      });

      if (run !== scenarioRun.current) return;  // the student switched scenarios meanwhile
      const aiMsg = {
        id: `ai-${Date.now()}`,
        sender: 'ai',
        text: res.reply,
        translation: res.translation,
        feedback: res.feedback,
        showTranslation: false,
      };
      setMessages((prev) => [...prev, aiMsg]);
      setSuggestions(res.suggested_replies || []);
      if (res.feedback) {
        setLatestFeedback(res.feedback);
        if (res.feedback.has_corrections) {
          setFeedbackOpen(true);
        }
      }
    } catch {
      if (run === scenarioRun.current) setMessages((prev) => [...prev, UNAVAILABLE()]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const toggleTranslation = (id) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, showTranslation: !m.showTranslation } : m))
    );
  };

  const playTTS = async (text, rate = 0.9) => {
    const res = await speak(text, lang, { rate });
    if (!res.ok) {
      setAudioNote(res.reason === 'no-voice' ? `No ${languageName(lang)} voice installed in browser.` : 'Speech audio unavailable.');
      setTimeout(() => setAudioNote(null), 4000);
    }
  };

  const toggleMic = async () => {
    if (listening) {
      micHandle.current?.stop();
      setListening(false);
      return;
    }
    setMicError(null);
    const h = recognize(lang);
    if (!h) {
      setMicError('Speech recognition is not supported in this browser (supported in Chrome/Edge/Safari).');
      return;
    }
    micHandle.current = h;
    setListening(true);
    const res = await h.result;
    setListening(false);
    if (res.ok && res.transcripts && res.transcripts.length) {
      setInput(res.transcripts[0]);
    } else if (res.reason && res.reason !== 'no-speech') {
      setMicError(res.reason === 'not-allowed' ? 'Microphone permission blocked.' : 'Could not hear clearly. Try again.');
    }
  };

  // Scenario Selector View
  if (!activeScenario) {
    return (
      <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 'var(--space-3)',
            padding: 'var(--space-4)',
            background: 'var(--surface)',
            border: '1px solid var(--rule)',
            borderRadius: 'var(--radius)',
          }}
        >
          <div>
            <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Roleplay Partner</h2>
            <p className="hint" style={{ marginTop: 2 }}>
              Practice real-world dialogues with intelligent AI characters, grammar feedback, and live voice conversation.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <label htmlFor="roleplay-lang" className="hint" style={{ fontWeight: 600 }}>
              Language:
            </label>
            <select
              id="roleplay-lang"
              className="input"
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              style={{ width: 'auto', padding: 'var(--space-1) var(--space-2)' }}
            >
              {LANGUAGES.map(([code, name]) => (
                <option key={code} value={code}>
                  {name} ({code})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: 'var(--space-4)',
          }}
        >
          {SCENARIOS.map((sc) => {
            const Icon = sc.icon;
            return (
              <div
                key={sc.id}
                className="panel"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: 'var(--space-3)',
                  transition: 'border-color 0.15s ease',
                  cursor: 'pointer',
                }}
                onClick={() => selectScenario(sc)}
              >
                <div className="stack-sm">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--accent-tint)',
                        color: 'var(--accent)',
                        display: 'grid',
                        placeItems: 'center',
                      }}
                    >
                      <Icon size={22} aria-hidden="true" />
                    </div>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.8rem',
                        fontWeight: 700,
                        color: 'var(--gold-text)',
                        background: 'var(--sunk)',
                        padding: '2px 8px',
                        borderRadius: '999px',
                        border: '1px solid var(--rule)',
                      }}
                    >
                      {sc.level}
                    </span>
                  </div>
                  <div>
                    <h3 style={{ margin: 'var(--space-1) 0 4px', fontSize: '1.05rem' }}>{sc.title}</h3>
                    <p className="hint" style={{ fontSize: '0.82rem', marginBottom: 6 }}>
                      Partner: <strong>{sc.partner}</strong>
                    </p>
                    <p style={{ fontSize: '0.88rem', lineHeight: 1.45, color: 'var(--ink-soft)' }}>{sc.goal}</p>
                  </div>
                </div>

                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  style={{ width: '100%', marginTop: 'var(--space-2)' }}
                >
                  Start Roleplay
                </button>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Active Roleplay Chat View
  const ScenarioIcon = activeScenario.icon;

  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      {/* Scenario header banner */}
      <div
        className="panel"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--space-3)',
          padding: 'var(--space-3) var(--space-4)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            onClick={() => setActiveScenario(null)}
            aria-label="Back to scenarios"
          >
            <ArrowLeft size={16} aria-hidden="true" />
            <span>Scenarios</span>
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <ScenarioIcon size={20} style={{ color: 'var(--accent)' }} aria-hidden="true" />
            <div>
              <strong style={{ fontSize: '1rem' }}>{activeScenario.title}</strong>
              <span className="hint" style={{ marginLeft: 8, fontSize: '0.82rem' }}>
                ({activeScenario.partner} · {activeScenario.level} · {languageName(lang)})
              </span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          {latestFeedback && (
            <button
              type="button"
              className={`btn btn-sm ${latestFeedback.has_corrections ? 'btn-secondary' : 'btn-quiet'}`}
              onClick={() => setFeedbackOpen(!feedbackOpen)}
            >
              <Sparkles size={14} aria-hidden="true" />
              <span>AI Feedback {latestFeedback.has_corrections ? '(!)' : ''}</span>
              {feedbackOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            onClick={() => selectScenario(activeScenario)}
            title="Restart dialogue"
          >
            <RotateCcw size={14} aria-hidden="true" />
            <span>Restart</span>
          </button>
        </div>
      </div>

      {/* Feedback Drawer / Card */}
      {feedbackOpen && latestFeedback && (
        <div
          className="panel"
          style={{
            background: latestFeedback.has_corrections ? 'var(--bad-tint)' : 'var(--sunk)',
            borderColor: latestFeedback.has_corrections ? 'var(--bad-rule)' : 'var(--rule)',
            padding: 'var(--space-3) var(--space-4)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 6 }}>
            {latestFeedback.has_corrections ? (
              <AlertCircle size={16} style={{ color: 'var(--bad)' }} aria-hidden="true" />
            ) : (
              <CheckCircle size={16} style={{ color: 'var(--ok)' }} aria-hidden="true" />
            )}
            <strong style={{ fontSize: '0.92rem' }}>
              {latestFeedback.has_corrections ? 'Grammar & Vocabulary Suggestions' : 'Excellent Phrasing!'}
            </strong>
          </div>
          {latestFeedback.corrections && latestFeedback.corrections.length > 0 && (
            <ul style={{ margin: '4px 0 8px 18px', padding: 0, fontSize: '0.88rem' }}>
              {latestFeedback.corrections.map((corr, idx) => (
                <li key={idx} style={{ marginBottom: 2 }}>
                  {corr}
                </li>
              ))}
            </ul>
          )}
          {latestFeedback.tip && (
            <p className="hint" style={{ fontSize: '0.86rem', fontStyle: 'italic' }}>
              💡 {latestFeedback.tip}
            </p>
          )}
        </div>
      )}

      {audioNote && <p className="notice notice-info">{audioNote}</p>}
      {micError && <p className="notice notice-bad">{micError}</p>}

      {/* Turn-by-turn chat conversation area */}
      <div
        ref={logRef}
        className="panel"
        style={{
          minHeight: '340px',
          maxHeight: '520px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-3)',
          padding: 'var(--space-4)',
        }}
        aria-live="polite"
      >
        {messages.map((msg) => {
          const isUser = msg.sender === 'user';
          return (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: isUser ? 'flex-end' : 'flex-start',
                maxWidth: '100%',
              }}
            >
              <div
                style={{
                  background: isUser ? 'var(--accent)' : 'var(--sunk)',
                  color: isUser ? 'var(--on-accent)' : 'var(--ink)',
                  border: isUser ? 'none' : '1px solid var(--rule)',
                  borderRadius: 'var(--radius)',
                  padding: 'var(--space-3) var(--space-4)',
                  maxWidth: '82%',
                  boxShadow: 'var(--shadow)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 'var(--space-3)',
                    marginBottom: 4,
                  }}
                >
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      opacity: 0.85,
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                    }}
                  >
                    {isUser ? 'You' : activeScenario.partner}
                  </span>
                  {!isUser && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <button
                        type="button"
                        className="btn btn-quiet btn-sm btn-icon"
                        onClick={() => playTTS(msg.text, 0.9)}
                        title="Listen at normal speed"
                        style={{ width: 26, height: 26, padding: 0 }}
                      >
                        <Volume2 size={14} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="btn btn-quiet btn-sm btn-icon"
                        onClick={() => playTTS(msg.text, 0.6)}
                        title="Listen slowly (turtle mode)"
                        style={{ width: 26, height: 26, padding: 0 }}
                      >
                        <Snail size={14} aria-hidden="true" />
                      </button>
                    </div>
                  )}
                </div>

                <div style={{ fontSize: '1.05rem', lineHeight: 1.5 }} lang={!isUser ? lang : undefined}>
                  {msg.text}
                </div>

                {!isUser && msg.translation && (
                  <div style={{ marginTop: 'var(--space-2)' }}>
                    <button
                      type="button"
                      className="btn btn-quiet btn-sm"
                      onClick={() => toggleTranslation(msg.id)}
                      style={{ fontSize: '0.78rem', height: 24, padding: '0 8px' }}
                    >
                      <Globe size={12} aria-hidden="true" />
                      <span>{msg.showTranslation ? 'Hide translation' : 'Translate'}</span>
                    </button>
                    {msg.showTranslation && (
                      <div
                        style={{
                          marginTop: 4,
                          fontSize: '0.88rem',
                          fontStyle: 'italic',
                          color: 'var(--muted)',
                          padding: '4px 8px',
                          background: 'var(--surface)',
                          borderRadius: 'var(--radius-sm)',
                        }}
                      >
                        {msg.translation}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {sending && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              color: 'var(--muted)',
              fontSize: '0.88rem',
            }}
          >
            <Loader2 size={16} className="spin" aria-hidden="true" />
            <span>{activeScenario.partner} is typing…</span>
          </div>
        )}
      </div>

      {/* Suggested quick replies chips */}
      {suggestions.length > 0 && !sending && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
          <span className="hint" style={{ fontSize: '0.8rem', alignSelf: 'center', marginRight: 4 }}>
            Suggestions:
          </span>
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              type="button"
              className="btn btn-quiet btn-sm"
              onClick={() => sendMessage(s)}
              style={{ borderRadius: '999px', fontSize: '0.84rem' }}
            >
              💬 {s}
            </button>
          ))}
        </div>
      )}

      {/* Input controls form */}
      <form
        className="panel"
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          alignItems: 'center',
          padding: 'var(--space-2) var(--space-3)',
        }}
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage();
        }}
      >
        {canRecognize() && (
          <button
            type="button"
            className={`btn btn-icon ${listening ? 'btn-danger' : 'btn-quiet'}`}
            onClick={toggleMic}
            title={listening ? 'Listening… tap to stop' : 'Tap to speak'}
            aria-label="Microphone voice input"
          >
            {listening ? <Square size={16} className="spin" /> : <Mic size={18} />}
          </button>
        )}

        <input
          ref={inputRef}
          className="input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={listening ? 'Listening… say your message' : `Reply to ${activeScenario.partner} in ${languageName(lang)}…`}
          disabled={sending}
          lang={lang}
          style={{ flex: 1 }}
        />

        <button
          type="submit"
          className="btn btn-primary btn-icon"
          disabled={sending || !input.trim()}
          aria-label="Send message"
        >
          <Send size={16} />
        </button>
      </form>

      {canRecognize() && (
        <p className="hint" style={{ fontSize: '0.78rem' }}>
          {RECOGNITION_NOTICE}
        </p>
      )}
    </div>
  );
}
