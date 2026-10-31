import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { 
  Zap, Send, Bot, User, ChevronUp, ChevronDown, 
  Sparkles, CheckCircle2, AlertTriangle, Layers, Compass, Award
} from 'lucide-react';
import { theme } from '../theme';

export default function AgyBridgeDrawer({ 
  activeTopicId, 
  onTriggerEvent, 
  onSwitchTab 
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'agy',
      content: "👋 I'm your **AGY Physics Companion**. Ask me anything about this derivation, request custom simulations, or ask for tailored assessment problems. I update your workspace in real-time without wasting credits!",
      timestamp: Date.now()
    }
  ]);
  const [inputVal, setInputVal] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [latestToast, setLatestToast] = useState(null);
  const messagesEndRef = useRef(null);

  // Poll for messages and events every 2 seconds
  useEffect(() => {
    const pollEvents = async () => {
      try {
        const res = await fetch('/api/agy/events');
        if (res.ok) {
          const data = await res.json();
          if (data.events && data.events.length > 0) {
            const lastEvent = data.events[data.events.length - 1];
            if (lastEvent.type === 'QUIZ_SUBMITTED') {
              setLatestToast({
                text: lastEvent.payload.statusMessage,
                type: lastEvent.payload.isCorrect ? 'success' : 'warn'
              });
              setTimeout(() => setLatestToast(null), 4000);
            }
          }
        }
      } catch (e) {}
    };

    pollEvents();
    const interval = setInterval(pollEvents, 2500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  const handleSend = async (textToSend) => {
    const text = textToSend || inputVal;
    if (!text.trim() || isSending) return;

    const userMsg = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      content: text,
      timestamp: Date.now()
    };

    setMessages(prev => [...prev, userMsg]);
    setInputVal('');
    setIsSending(true);

    try {
      const res = await fetch('/api/agy/prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, topicId: activeTopicId })
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [
          ...prev,
          {
            id: `agy-${Date.now()}`,
            sender: 'agy',
            content: data.reply,
            timestamp: Date.now()
          }
        ]);
      }
    } catch (e) {
      setMessages(prev => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'agy',
          content: "*(AGY Event Recorded)* Your prompt has been logged in `content/agy_messages.json`.",
          timestamp: Date.now()
        }
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleQuickAction = (action) => {
    if (action === 'race') {
      if (onSwitchTab) onSwitchTab('simulation');
      handleSend("Show me the difference between a solid sphere and a hollow hoop rolling down an incline!");
    } else if (action === 'contact_proof') {
      handleSend("Can you mathematically prove why the contact point has instantaneous velocity zero ($v_{\\text{contact}} = 0$)?");
    } else if (action === 'quiz_hard') {
      if (onSwitchTab) onSwitchTab('quiz');
      handleSend("Generate an advanced rotational dynamics problem for me to solve!");
    }
  };

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      right: 24,
      width: isOpen ? 440 : 280,
      background: theme.bgPanel,
      border: `1px solid ${theme.borderActive}`,
      borderBottom: 'none',
      borderRadius: '8px 8px 0 0',
      boxShadow: '0 -8px 30px rgba(0, 0, 0, 0.7)',
      zIndex: 1000,
      transition: 'width 0.25s ease',
      display: 'flex',
      flexDirection: 'column',
      maxHeight: isOpen ? '75vh' : 42
    }}>
      {/* Drawer Header Bar */}
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{
          padding: '10px 14px',
          background: theme.bgHeader,
          borderBottom: isOpen ? `1px solid ${theme.border}` : 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          userSelect: 'none'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Zap size={15} color={theme.accentGold} />
          <span style={{ fontFamily: theme.fontMono, fontSize: '0.82rem', fontWeight: 700, color: theme.accentGold }}>
            AGY LIVE BRIDGE
          </span>
          <span style={{
            fontSize: '0.65rem',
            background: 'rgba(35, 165, 90, 0.2)',
            color: theme.accentGreen,
            padding: '1px 5px',
            borderRadius: 3,
            fontFamily: theme.fontMono,
            fontWeight: 700
          }}>
            REAL-TIME
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {latestToast && (
            <span style={{
              fontSize: '0.72rem',
              color: latestToast.type === 'success' ? theme.accentGreen : theme.accentGold,
              fontFamily: theme.fontMono
            }}>
              {latestToast.text}
            </span>
          )}
          {isOpen ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </div>
      </div>

      {/* Expanded Content */}
      {isOpen && (
        <div style={{ display: 'flex', flexDirection: 'column', height: 420 }}>
          {/* Quick Action Chips */}
          <div style={{
            padding: '8px 12px',
            borderBottom: `1px solid ${theme.border}`,
            background: '#121212',
            display: 'flex',
            gap: 6,
            overflowX: 'auto'
          }}>
            <button
              onClick={() => handleQuickAction('race')}
              style={{
                background: theme.bgCard,
                border: `1px solid ${theme.border}`,
                color: theme.accentCyan,
                borderRadius: 4,
                padding: '4px 8px',
                fontSize: '0.72rem',
                fontFamily: theme.fontMono,
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
            >
              🏎️ Incline Race Sim
            </button>
            <button
              onClick={() => handleQuickAction('contact_proof')}
              style={{
                background: theme.bgCard,
                border: `1px solid ${theme.border}`,
                color: theme.accentGold,
                borderRadius: 4,
                padding: '4px 8px',
                fontSize: '0.72rem',
                fontFamily: theme.fontMono,
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
            >
              📐 Prove v_contact = 0
            </button>
            <button
              onClick={() => handleQuickAction('quiz_hard')}
              style={{
                background: theme.bgCard,
                border: `1px solid ${theme.border}`,
                color: theme.accentGreen,
                borderRadius: 4,
                padding: '4px 8px',
                fontSize: '0.72rem',
                fontFamily: theme.fontMono,
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
            >
              🎯 Test Intuition
            </button>
          </div>

          {/* Messages Stream */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            background: '#141414'
          }}>
            {messages.map(msg => {
              const isAgy = msg.sender === 'agy';
              return (
                <div
                  key={msg.id}
                  style={{
                    alignSelf: isAgy ? 'flex-start' : 'flex-end',
                    maxWidth: '88%',
                    background: isAgy ? theme.bgCard : 'rgba(35, 165, 90, 0.2)',
                    border: `1px solid ${isAgy ? theme.border : theme.accentGreen}`,
                    borderRadius: 6,
                    padding: '8px 12px',
                    fontSize: '0.82rem',
                    lineHeight: 1.5,
                    color: theme.textMain
                  }}
                >
                  <div style={{
                    fontSize: '0.68rem',
                    fontFamily: theme.fontMono,
                    color: isAgy ? theme.accentGold : theme.accentGreen,
                    marginBottom: 3,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4
                  }}>
                    {isAgy ? <><Bot size={12} /> AGY Companion</> : <><User size={12} /> You</>}
                  </div>
                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
              );
            })}
            {isSending && (
              <div style={{ alignSelf: 'flex-start', color: theme.accentGold, fontSize: '0.75rem', fontFamily: theme.fontMono }}>
                Thinking & updating derivations...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Box */}
          <div style={{
            padding: 10,
            borderTop: `1px solid ${theme.border}`,
            background: theme.bgPanel,
            display: 'flex',
            gap: 8
          }}>
            <input
              type="text"
              placeholder="Ask AGY or request custom notation..."
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSend();
              }}
              style={{
                flex: 1,
                background: theme.bgInput,
                border: `1px solid ${theme.border}`,
                borderRadius: 4,
                padding: '8px 10px',
                color: theme.textMain,
                fontSize: '0.82rem',
                fontFamily: theme.fontMono,
                outline: 'none'
              }}
            />
            <button
              onClick={() => handleSend()}
              disabled={isSending || !inputVal.trim()}
              style={{
                background: theme.accentGreen,
                border: 'none',
                borderRadius: 4,
                padding: '0 12px',
                color: '#000',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
