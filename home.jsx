import React, { useState, useEffect } from 'react';
import { Terminal, Cpu, Play, CheckCircle2, AlertTriangle, RefreshCw, Loader2 } from 'lucide-react';

const EduIDE = () => {
  const [puzzleData, setPuzzleData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [slottedAnswer, setSlottedAnswer] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [terminalOutput, setTerminalOutput] = useState([
    "[SYSTEM] Ready. Click 'Generate Puzzle with AI' to call Gemini via Python backend."
  ]);

  // Fetch puzzle from Python FastAPI Backend
  const fetchNewPuzzle = async () => {
    setLoading(true);
    setSlottedAnswer(null);
    setEvaluation(null);
    setTerminalOutput(["[MCP_DISPATCH] Sending notes to Gemini...", "[CALLING] create_code_puzzle tool..."]);

    try {
      const response = await fetch("http://localhost:8000/api/generate-puzzle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          notes: "Loops in Python: while loops repeat as long as a condition is True. If condition never becomes False (like while True or when i never increments), it results in an infinite loop that crashes or locks CPU memory. Safe loops require clear boundary conditions."
        })
      });

      const data = await response.json();
      setPuzzleData(data);
      setTerminalOutput([
        "[MCP_RECEIVED] Puzzle generated successfully by Gemini.",
        "[READY] Drop an answer into the condition slot."
      ]);
    } catch (err) {
      setTerminalOutput([
        `[ERROR] Could not connect to Python backend at http://localhost:8000`,
        `Make sure server.py is running!`
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNewPuzzle();
  }, []);

  const handleDragStart = (e, variant) => {
    e.dataTransfer.setData("text/plain", variant);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const token = e.dataTransfer.getData("text/plain");
    applySelection(token);
  };

  const applySelection = (token) => {
    if (!puzzleData) return;
    setSlottedAnswer(token);

    if (token === puzzleData.correct_answer) {
      setEvaluation('correct');
      setTerminalOutput([
        `[SIMULATION]: ${puzzleData.loop_statement} ${token}:`,
        ...(puzzleData.safe_terminal_output || ["Loop executed safely."]),
        "[SUCCESS] Test passed cleanly."
      ]);
    } else {
      setEvaluation('wrong');
      setTerminalOutput([
        `[SIMULATION]: ${puzzleData.loop_statement} ${token}:`,
        ...(puzzleData.unsafe_terminal_output || ["[CRITICAL] Memory limit exceeded. Safety break."])
      ]);
    }
  };

  const theme = {
    bgApp: '#181818',
    bgSidebar: '#252526',
    bgEditor: '#1e1e1e',
    border: '#2b2b2b',
    accent: '#007acc',
    textMain: '#cccccc',
    textDim: '#858585',
    font: '"JetBrains Mono", monospace'
  };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', backgroundColor: theme.bgApp, color: theme.textMain, fontFamily: theme.font }}>
      
      {/* Sidebar: AI Question & Drag Source */}
      <aside style={{ width: '320px', backgroundColor: theme.bgSidebar, borderRight: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column', padding: '20px' }}>
        <button 
          onClick={fetchNewPuzzle}
          disabled={loading}
          style={{
            backgroundColor: theme.accent,
            color: 'white',
            border: 'none',
            padding: '10px 14px',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '12px',
            fontWeight: 'bold',
            marginBottom: '20px'
          }}
        >
          {loading ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
          {loading ? "Calling Gemini..." : "Generate New Puzzle"}
        </button>

        <div style={{ fontSize: '11px', fontWeight: 'bold', color: theme.textDim, marginBottom: '8px', textTransform: 'uppercase' }}>
          AI Inquiry
        </div>
        <p style={{ fontSize: '13px', lineHeight: '1.5', color: '#e2e8f0', marginBottom: '20px' }}>
          {puzzleData ? puzzleData.question : "Loading puzzle from AI..."}
        </p>

        <div style={{ fontSize: '11px', fontWeight: 'bold', color: theme.textDim, marginBottom: '10px', textTransform: 'uppercase' }}>
          Variants (Gemini Generated)
        </div>

        {/* Draggable Chips */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {puzzleData && puzzleData.variants.map((v) => (
            <div
              key={v}
              draggable
              onDragStart={(e) => handleDragStart(e, v)}
              onClick={() => applySelection(v)}
              style={{
                padding: '10px 14px',
                backgroundColor: slottedAnswer === v ? '#1e293b' : '#2d2d2d',
                border: `1px solid ${slottedAnswer === v ? theme.accent : '#3e3e42'}`,
                borderRadius: '4px',
                cursor: 'grab',
                fontSize: '13px',
                color: '#9cdcfe',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
            >
              <span>{v}</span>
              <span style={{ fontSize: '10px', color: theme.textDim }}>⠿</span>
            </div>
          ))}
        </div>

        {evaluation && (
          <div style={{ 
            marginTop: 'auto', 
            padding: '12px', 
            borderRadius: '4px', 
            backgroundColor: evaluation === 'correct' ? '#064e3b' : '#7f1d1d',
            border: `1px solid ${evaluation === 'correct' ? '#10b981' : '#f87171'}` 
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: '12px', color: 'white', marginBottom: '4px' }}>
              {evaluation === 'correct' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              {evaluation === 'correct' ? 'Correct Logic' : 'Crash / Unsafe Code'}
            </div>
            <p style={{ fontSize: '11px', margin: 0, color: '#e2e8f0' }}>{puzzleData.explanation}</p>
          </div>
        )}
      </aside>

      {/* Editor Space */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: '35px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', padding: '0 16px', justifyContent: 'space-between', borderBottom: `1px solid ${theme.border}` }}>
          <span style={{ fontSize: '12px', color: '#9cdcfe' }}>problem_space.py</span>
          {slottedAnswer && (
            <button onClick={() => { setSlottedAnswer(null); setEvaluation(null); }} style={{ background: 'transparent', border: 'none', color: theme.textDim, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px' }}>
              <RefreshCw size={12} /> Reset Slot
            </button>
          )}
        </div>

        {/* Code Canvas */}
        <div style={{ flex: 1, backgroundColor: theme.bgEditor, padding: '24px', fontSize: '15px', lineHeight: '1.8' }}>
          {puzzleData && (
            <>
              <div><span style={{ color: '#858585', marginRight: '16px' }}>1</span>{puzzleData.code_line_1}</div>
              <div style={{ display: 'flex', alignItems: 'center', margin: '4px 0' }}>
                <span style={{ color: '#858585', marginRight: '16px' }}>2</span>
                <span style={{ color: '#c586c0', marginRight: '8px' }}>{puzzleData.loop_statement}</span>
                
                {/* Drop Zone */}
                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDrop}
                  style={{
                    minWidth: '120px',
                    height: '30px',
                    border: slottedAnswer ? `1px solid ${evaluation === 'correct' ? '#10b981' : '#f87171'}` : '2px dashed #555',
                    borderRadius: '4px',
                    backgroundColor: slottedAnswer ? '#1e293b' : '#262626',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '0 12px',
                    marginRight: '6px',
                    color: slottedAnswer ? '#9cdcfe' : '#858585',
                    fontSize: '13px'
                  }}
                >
                  {slottedAnswer || "DROP HERE"}
                </div>
                <span>:</span>
              </div>
              <div><span style={{ color: '#858585', marginRight: '16px' }}>3</span><pre style={{ display: 'inline', margin: 0, fontFamily: 'inherit' }}>{puzzleData.code_body}</pre></div>
            </>
          )}
        </div>

        {/* Terminal */}
        <div style={{ height: '180px', backgroundColor: '#141414', borderTop: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ height: '28px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', padding: '0 16px', gap: '8px' }}>
            <Terminal size={12} color="#10b981" />
            <span style={{ fontSize: '11px', color: theme.textDim, fontWeight: 'bold' }}>TERMINAL</span>
          </div>
          <div style={{ padding: '12px 16px', overflowY: 'auto', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {terminalOutput.map((l, i) => (
              <span key={i} style={{ color: l.includes('[CRITICAL]') || l.includes('[ERROR]') ? '#f87171' : l.includes('[SUCCESS]') ? '#4ade80' : '#cccccc' }}>
                {l}
              </span>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
};

export default EduIDE;