import React, { useState, useEffect } from 'react';
import { Terminal, Send, Play, CheckCircle2, AlertTriangle, RefreshCw, Loader2, Sparkles, HelpCircle } from 'lucide-react';

const EduIDE = () => {
  const [topicInput, setTopicInput] = useState("Python loops: prevention of endless loops and boundary invariants");
  const [puzzle, setPuzzle] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Slot selection state
  const [slottedAnswer, setSlottedAnswer] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [terminalOutput, setTerminalOutput] = useState([
    "[SYSTEM] Socratic Engine ready.",
    "[STATUS] Enter notes or topic above and click 'Generate Puzzle'."
  ]);

  // Socratic Chat state
  const [chatHistory, setChatHistory] = useState([]);
  const [userInput, setUserInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // Generate puzzle from backend
  const handleGenerate = async () => {
    setLoading(true);
    setSlottedAnswer(null);
    setEvaluation(null);
    setTerminalOutput([`[MCP_DISPATCH] Analyzing topic: "${topicInput}"...`, "[GEMINI] Executing create_universal_puzzle..."]);

    try {
      const res = await fetch("http://localhost:8000/api/generate-puzzle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes_or_topic: topicInput })
      });
      const data = await res.json();
      setPuzzle(data);
      
      // Initialize Socratic tutor dialogue
      setChatHistory([
        { role: 'model', content: `We are analyzing **${data.title}**. Before attempting the slot, what do you think the core invariant or goal of this code is?` }
      ]);

      setTerminalOutput([
        `[LOADED] Puzzle: ${data.title} (${data.topic})`,
        "[READY] Drag or click an answer block into the slot."
      ]);
    } catch (err) {
      setTerminalOutput(["[ERROR] Backend unreachable at http://localhost:8000. Is server.py running?"]);
    } finally {
      setLoading(false);
    }
  };

  // Chat with Socratic Tutor
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!userInput.trim() || chatLoading) return;

    const userMsg = userInput;
    setUserInput("");
    const newHistory = [...chatHistory, { role: 'user', content: userMsg }];
    setChatHistory(newHistory);
    setChatLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/tutor-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          puzzle_context: puzzle || {},
          history: newHistory,
          message: userMsg
        })
      });
      const data = await res.json();
      setChatHistory(prev => [...prev, { role: 'model', content: data.reply }]);
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'model', content: "[Tutor Connection Error: Failed to reach backend.]" }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleSelectToken = (token) => {
    if (!puzzle) return;
    setSlottedAnswer(token);

    if (token === puzzle.correct_answer) {
      setEvaluation('correct');
      setTerminalOutput([
        `[EVALUATING]: ${puzzle.code_template.replace("{{SLOT}}", token)}`,
        ...(puzzle.test_cases || []),
        "[SUCCESS] Logic confirmed valid."
      ]);
    } else {
      setEvaluation('wrong');
      setTerminalOutput([
        `[MUTANT DETECTED]: Applied variant '${token}'`,
        "[WARNING] Contradiction or unsafe execution encountered.",
        `[HINT] Ask the Socratic Tutor on the right for guidance without spoilers.`
      ]);
    }
  };

  // Helper to render code template with dynamic inline slot
  const renderCodeWithSlot = (template) => {
    if (!template) return null;
    const parts = template.split("{{SLOT}}");

    return (
      <pre style={{ margin: 0, fontFamily: 'inherit', whiteSpace: 'pre-wrap' }}>
        {parts[0]}
        <span
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleSelectToken(e.dataTransfer.getData("text/plain"));
          }}
          style={{
            minWidth: '100px',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2px 10px',
            margin: '0 4px',
            borderRadius: '4px',
            border: slottedAnswer ? `1px solid ${evaluation === 'correct' ? '#10b981' : '#f87171'}` : '2px dashed #4ec9b0',
            backgroundColor: slottedAnswer ? '#1e293b' : '#2d2d30',
            color: slottedAnswer ? '#9cdcfe' : '#858585',
            fontWeight: 'bold',
            verticalAlign: 'middle'
          }}
        >
          {slottedAnswer || "?? SLOT ??"}
        </span>
        {parts[1]}
      </pre>
    );
  };

  // VS Code styling
  const theme = {
    bgApp: '#181818',
    bgSidebar: '#252526',
    bgEditor: '#1e1e1e',
    border: '#2b2b2b',
    accent: '#007acc',
    textMain: '#cccccc',
    textDim: '#858585',
    font: '"JetBrains Mono", "Fira Code", monospace'
  };

  useEffect(() => {
    handleGenerate();
  }, []);

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', backgroundColor: theme.bgApp, color: theme.textMain, fontFamily: theme.font }}>
      
      {/* 1. LEFT PANEL: Controls & Variants */}
      <aside style={{ width: '280px', backgroundColor: theme.bgSidebar, borderRight: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column', padding: '16px' }}>
        <div style={{ fontSize: '11px', fontWeight: 'bold', color: theme.textDim, marginBottom: '8px', textTransform: 'uppercase' }}>
          Educational Ingestion
        </div>
        <textarea
          value={topicInput}
          onChange={(e) => setTopicInput(e.target.value)}
          placeholder="Enter any code, topic, or notes..."
          rows={3}
          style={{ width: '100%', backgroundColor: theme.bgApp, color: theme.textMain, border: `1px solid ${theme.border}`, padding: '8px', borderRadius: '4px', fontSize: '11px', fontFamily: 'inherit', resize: 'none', marginBottom: '10px' }}
        />
        <button
          onClick={handleGenerate}
          disabled={loading}
          style={{ backgroundColor: theme.accent, color: 'white', border: 'none', padding: '8px', borderRadius: '4px', cursor: loading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '12px', fontWeight: 'bold' }}
        >
          {loading ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
          {loading ? "Synthesizing..." : "Generate Puzzle"}
        </button>

        <div style={{ margin: '20px 0 8px 0', fontSize: '11px', fontWeight: 'bold', color: theme.textDim, textTransform: 'uppercase' }}>
          Interactive Tokens (Drag / Click)
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1, overflowY: 'auto' }}>
          {puzzle && puzzle.variants.map((v) => (
            <div
              key={v}
              draggable
              onDragStart={(e) => e.dataTransfer.setData("text/plain", v)}
              onClick={() => handleSelectToken(v)}
              style={{
                padding: '10px',
                backgroundColor: slottedAnswer === v ? '#1e293b' : '#2d2d30',
                border: `1px solid ${slottedAnswer === v ? theme.accent : '#3e3e42'}`,
                borderRadius: '4px',
                cursor: 'grab',
                fontSize: '12px',
                color: '#9cdcfe',
                display: 'flex',
                justifyContent: 'space-between'
              }}
            >
              <span>{v}</span>
              <span style={{ color: theme.textDim, fontSize: '10px' }}>⠿</span>
            </div>
          ))}
        </div>

        {evaluation && (
          <div style={{ padding: '10px', borderRadius: '4px', backgroundColor: evaluation === 'correct' ? '#064e3b' : '#450a0a', border: `1px solid ${evaluation === 'correct' ? '#10b981' : '#f87171'}`, fontSize: '11px' }}>
            <div style={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              {evaluation === 'correct' ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
              {evaluation === 'correct' ? 'Logical Match' : 'Unstable Code / Mutant'}
            </div>
            <span>{puzzle.explanation}</span>
          </div>
        )}
      </aside>

      {/* 2. CENTER PANEL: Code Editor & Terminal */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: `1px solid ${theme.border}` }}>
        <div style={{ height: '35px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', borderBottom: `1px solid ${theme.border}` }}>
          <span style={{ fontSize: '12px', color: '#4ec9b0' }}>{puzzle ? `${puzzle.title} (${puzzle.topic})` : 'workspace.py'}</span>
          {slottedAnswer && (
            <button onClick={() => { setSlottedAnswer(null); setEvaluation(null); }} style={{ background: 'transparent', border: 'none', color: theme.textDim, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
              <RefreshCw size={12} /> Clear Slot
            </button>
          )}
        </div>

        {/* Dynamic Code Canvas */}
        <div style={{ flex: 1, backgroundColor: theme.bgEditor, padding: '24px', fontSize: '15px', lineHeight: '1.7', overflowY: 'auto' }}>
          {puzzle ? renderCodeWithSlot(puzzle.code_template) : <span style={{ color: theme.textDim }}>Loading code space...</span>}
        </div>

        {/* Terminal */}
        <div style={{ height: '180px', backgroundColor: '#141414', borderTop: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ height: '26px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', padding: '0 12px', gap: '8px' }}>
            <Terminal size={12} color="#4ec9b0" />
            <span style={{ fontSize: '11px', color: theme.textDim, fontWeight: 'bold' }}>SAFE SANDBOX OUTPUT</span>
          </div>
          <div style={{ padding: '10px 14px', overflowY: 'auto', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {terminalOutput.map((l, i) => (
              <span key={i} style={{ color: l.includes('[ERROR]') || l.includes('[WARNING]') ? '#f87171' : l.includes('[SUCCESS]') ? '#4ade80' : '#cccccc' }}>
                {l}
              </span>
            ))}
          </div>
        </div>
      </main>

      {/* 3. RIGHT PANEL: Socratic Tutor Chat */}
      <section style={{ width: '340px', backgroundColor: theme.bgSidebar, display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: '35px', padding: '0 16px', borderBottom: `1px solid ${theme.border}`, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={14} color="#cca700" />
          <span style={{ fontSize: '12px', fontWeight: 'bold', color: theme.textMain }}>Socratic Tutor (No-Spoilers)</span>
        </div>

        {/* Message History */}
        <div style={{ flex: 1, padding: '16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
          {chatHistory.map((msg, i) => (
            <div 
              key={i} 
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                backgroundColor: msg.role === 'user' ? '#007acc' : '#1e1e1e',
                color: msg.role === 'user' ? 'white' : '#d4d4d4',
                padding: '10px 12px',
                borderRadius: '6px',
                maxWidth: '90%',
                lineHeight: '1.4',
                border: msg.role === 'model' ? `1px solid ${theme.border}` : 'none'
              }}
            >
              {msg.content}
            </div>
          ))}
          {chatLoading && <div style={{ color: theme.textDim, fontSize: '11px', fontStyle: 'italic' }}>Tutor is formulating guiding question...</div>}
        </div>

        {/* Chat Input */}
        <form onSubmit={handleSendMessage} style={{ padding: '12px', borderTop: `1px solid ${theme.border}`, display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            placeholder="Answer or ask a question (use '!reveal' to override)..."
            style={{ flex: 1, backgroundColor: theme.bgApp, border: `1px solid ${theme.border}`, color: 'white', padding: '8px', borderRadius: '4px', fontSize: '12px', fontFamily: 'inherit' }}
          />
          <button type="submit" style={{ backgroundColor: theme.accent, border: 'none', color: 'white', borderRadius: '4px', padding: '0 10px', cursor: 'pointer' }}>
            <Send size={14} />
          </button>
        </form>
      </section>

    </div>
  );
};

export default EduIDE;