import React, { useState } from 'react';
import { Terminal, Cpu, Play, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';

const EduIDE = () => {
  // Sample data received from your Python Gemini tool:
  const [puzzleData, setPuzzleData] = useState({
    question: "Hi! Endless loops in Python can crash your PC. Select a condition that lets it run safely without crashing:",
    code_prefix: "i = 1\nwhile ",
    code_suffix: ":\n    print(\"rush\")\n    i += 1",
    variants: ["i < 5", "True", "i == 1", "i > 1000000"],
    correct_answer: "i < 5",
    explanation: "Setting 'i < 5' allows 4 iterations and then cleanly terminates."
  });

  const [slottedAnswer, setSlottedAnswer] = useState(null);
  const [evaluation, setEvaluation] = useState(null); // 'correct' | 'wrong' | null
  const [terminalOutput, setTerminalOutput] = useState([
    "[SYSTEM] Ready. Drop a condition into the code slot."
  ]);

  // Handle Drag & Drop
  const handleDragStart = (e, variant) => {
    e.dataTransfer.setData("text/plain", variant);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedToken = e.dataTransfer.getData("text/plain");
    applySelection(droppedToken);
  };

  const applySelection = (token) => {
    setSlottedAnswer(token);
    
    // Evaluate answer
    if (token === puzzleData.correct_answer) {
      setEvaluation('correct');
      setTerminalOutput([
        `[SIMULATING]: while ${token}:`,
        "rush", "rush", "rush", "rush",
        "[SUCCESS]: Loop terminated safely at i=5. Memory stable."
      ]);
    } else if (token === "True" || token === "i == 1") {
      setEvaluation('wrong');
      setTerminalOutput([
        `[SIMULATING]: while ${token}:`,
        "rush", "rush", "rush", "rush", "rush", "rush...",
        "[CRITICAL]: Endless loop detected! Browser safety kill triggered."
      ]);
    } else {
      setEvaluation('wrong');
      setTerminalOutput([
        `[SIMULATING]: while ${token}:`,
        "[WARNING]: Condition evaluated to False immediately. Loop never ran."
      ]);
    }
  };

  const resetSlot = () => {
    setSlottedAnswer(null);
    setEvaluation(null);
    setTerminalOutput(["[SYSTEM] Reset. Choose an answer to place in the loop."]);
  };

  // VS Code Theme Styles
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
      
      {/* Left: AI Question & Drag Source */}
      <aside style={{ width: '320px', backgroundColor: theme.bgSidebar, borderRight: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column', padding: '20px' }}>
        <div style={{ fontSize: '11px', fontWeight: 'bold', color: theme.textDim, marginBottom: '12px', textTransform: 'uppercase' }}>
          AI Question
        </div>
        <p style={{ fontSize: '13px', lineHeight: '1.5', color: '#e2e8f0', marginBottom: '24px' }}>
          {puzzleData.question}
        </p>

        <div style={{ fontSize: '11px', fontWeight: 'bold', color: theme.textDim, marginBottom: '8px', textTransform: 'uppercase' }}>
          Draggable Variants
        </div>
        <p style={{ fontSize: '11px', color: theme.textDim, margin: '0 0 12px 0' }}>
          Drag a block or click to slot it in:
        </p>

        {/* Drag-and-Drop Chips */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {puzzleData.variants.map((v) => (
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
                alignItems: 'center',
                justifyContent: 'space-between',
                transition: 'all 0.15s ease'
              }}
            >
              <span>{v}</span>
              <span style={{ fontSize: '10px', color: theme.textDim }}>Drag ⠿</span>
            </div>
          ))}
        </div>

        {/* Feedback Area */}
        {evaluation && (
          <div style={{ 
            marginTop: 'auto', 
            padding: '12px', 
            borderRadius: '4px', 
            backgroundColor: evaluation === 'correct' ? '#064e3b' : '#7f1d1d',
            border: `1px solid ${evaluation === 'correct' ? '#10b981' : '#f87171'}` 
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: '12px', color: 'white', marginBottom: '6px' }}>
              {evaluation === 'correct' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              {evaluation === 'correct' ? 'Safe Code Created!' : 'Unsafe / Incorrect Logic'}
            </div>
            <p style={{ fontSize: '11px', margin: 0, color: '#e2e8f0', lineHeight: '1.4' }}>
              {puzzleData.explanation}
            </p>
          </div>
        )}
      </aside>

      {/* Center: Code Editor with Slot */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        
        {/* Editor Title Bar */}
        <div style={{ height: '35px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', padding: '0 15px', justifyContent: 'space-between', borderBottom: `1px solid ${theme.border}` }}>
          <span style={{ fontSize: '12px', color: '#9cdcfe' }}>loop_problem_space.py</span>
          {slottedAnswer && (
            <button onClick={resetSlot} style={{ background: 'transparent', border: 'none', color: theme.textDim, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px' }}>
              <RefreshCw size={12} /> Clear Slot
            </button>
          )}
        </div>

        {/* Code Canvas */}
        <div style={{ flex: 1, backgroundColor: theme.bgEditor, padding: '24px', fontSize: '15px', lineHeight: '1.8' }}>
          <div><span style={{ color: '#858585', marginRight: '16px' }}>1</span><span style={{ color: '#569cd6' }}>i</span> = 1</div>
          
          <div style={{ display: 'flex', alignItems: 'center', margin: '4px 0' }}>
            <span style={{ color: '#858585', marginRight: '16px' }}>2</span>
            <span style={{ color: '#c586c0', marginRight: '8px' }}>while</span>
            
            {/* THE DROP ZONE / SLOT */}
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              style={{
                minWidth: '120px',
                height: '32px',
                border: slottedAnswer ? `1px solid ${evaluation === 'correct' ? '#10b981' : '#f87171'}` : '2px dashed #4f4f56',
                borderRadius: '4px',
                backgroundColor: slottedAnswer ? '#1e293b' : '#262626',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0 12px',
                marginRight: '6px',
                color: slottedAnswer ? '#9cdcfe' : '#858585',
                fontSize: '13px',
                fontWeight: 'bold',
                transition: 'all 0.2s'
              }}
            >
              {slottedAnswer ? slottedAnswer : "DROP HERE"}
            </div>
            
            <span style={{ color: '#d4d4d4' }}>:</span>
          </div>

          <div><span style={{ color: '#858585', marginRight: '16px' }}>3</span><span style={{ paddingLeft: '24px', color: '#dcdcaa' }}>print</span>(<span style={{ color: '#ce9178' }}>"rush"</span>)</div>
          <div><span style={{ color: '#858585', marginRight: '16px' }}>4</span><span style={{ paddingLeft: '24px', color: '#569cd6' }}>i</span> += 1</div>
        </div>

        {/* Bottom: Simulated Terminal */}
        <div style={{ height: '180px', backgroundColor: '#141414', borderTop: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ height: '28px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', padding: '0 16px', gap: '8px' }}>
            <Terminal size={12} color="#10b981" />
            <span style={{ fontSize: '11px', color: theme.textDim, fontWeight: 'bold' }}>SAFE EXECUTION CONSOLE</span>
          </div>
          <div style={{ padding: '12px 16px', overflowY: 'auto', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {terminalOutput.map((line, i) => (
              <span key={i} style={{ 
                color: line.includes('[CRITICAL]') ? '#f87171' : line.includes('[SUCCESS]') ? '#4ade80' : '#cccccc' 
              }}>
                {line}
              </span>
            ))}
          </div>
        </div>

      </main>
    </div>
  );
};

export default EduIDE;