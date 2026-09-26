import React, { useState, useEffect } from 'react';
import { Terminal, Send, Play, CheckCircle2, AlertTriangle, RefreshCw, Loader2, Sparkles, Upload } from 'lucide-react';

const EduIDE = () => {
  const [topicInput, setTopicInput] = useState("Command line pipes, grep filters, and safe execution");
  const [documentText, setDocumentText] = useState("");
  const [uploadedFileName, setUploadedFileName] = useState(null);
  const [puzzle, setPuzzle] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const [slottedAnswer, setSlottedAnswer] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [terminalOutput, setTerminalOutput] = useState([
    "[SYSTEM] Environment ready.",
    "[STATUS] Upload any .pdf, .docx, .ipynb, or .txt to extract domain logic."
  ]);

  const [chatHistory, setChatHistory] = useState([]);
  const [userInput, setUserInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // 1. Handle Document Upload
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadedFileName(file.name);
    setLoading(true);
    setTerminalOutput([`[INGESTION_LAB] Reading ${file.name}...`, `[PARSER] Extracting text & logic...`]);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/upload-document", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setDocumentText(data.extracted_text || "");
      setTerminalOutput([
        `[SUCCESS] Document parsed: ${file.name}`,
        `[READY] Click 'Generate Puzzle' to build exercises from this document.`
      ]);
    } catch (err) {
      setTerminalOutput([`[ERROR] Failed to extract text from ${file.name}`]);
    } finally {
      setLoading(false);
    }
  };

  // 2. Generate Puzzle using Document + User Instruction
  const handleGenerate = async () => {
    setLoading(true);
    setSlottedAnswer(null);
    setEvaluation(null);
    setTerminalOutput([
      `[MCP_DISPATCH] Selecting tool for: "${uploadedFileName || topicInput}"...`,
      `[GEMINI] Synthesizing puzzle...`
    ]);

    try {
      const res = await fetch("http://localhost:8000/api/generate-puzzle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_instruction: topicInput,
          document_text: documentText
        })
      });
      const data = await res.json();
      setPuzzle(data);
      
      setChatHistory([
        { role: 'model', content: `We are analyzing **${data.title}** (${data.topic}). Before choosing an answer, what do you think the missing slot needs to achieve?` }
      ]);

      setTerminalOutput([
        `[LOADED] Puzzle: ${data.title} [${data.topic}]`,
        `[READY] Drag or click an answer token to test.`
      ]);
    } catch (err) {
      setTerminalOutput(["[ERROR] Backend unreachable at http://localhost:8000. Make sure server.py is running!"]);
    } finally {
      setLoading(false);
    }
  };

  // Auto-generate on first load so the screen isn't blank
  useEffect(() => {
    handleGenerate();
  }, []);

  // 3. Socratic Tutor Chat
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
      setChatHistory(prev => [...prev, { role: 'model', content: "[Connection Error to Tutor]" }]);
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
        `[EXECUTING]: ${puzzle.code_template.replace("{{SLOT}}", token)}`,
        ...(puzzle.test_cases || []),
        "[SUCCESS] Verification passed."
      ]);
    } else {
      setEvaluation('wrong');
      setTerminalOutput([
        `[MUTANT APPLIED]: ${puzzle.code_template.replace("{{SLOT}}", token)}`,
        "[ERROR / MISMATCH] The test failed with this variant.",
        "[HINT] Ask the Socratic Tutor on the right for guidance without spoilers."
      ]);
    }
  };

  const renderCodeWithSlot = (template) => {
    if (!template) return null;
    const parts = template.split("{{SLOT}}");

    return (
      <pre style={{ margin: 0, fontFamily: 'inherit', whiteSpace: 'pre-wrap', lineHeight: '1.9' }}>
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
      
      {/* 1. LEFT PANEL */}
      <aside style={{ width: '290px', backgroundColor: theme.bgSidebar, borderRight: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column', padding: '16px' }}>
        <div style={{ fontSize: '11px', fontWeight: 'bold', color: theme.textDim, marginBottom: '8px', textTransform: 'uppercase' }}>
          Educational Ingestion
        </div>

        {/* Multi-Format Upload */}
        <label style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          padding: '10px',
          backgroundColor: '#2d2d30',
          border: '1px dashed #4ec9b0',
          borderRadius: '4px',
          cursor: 'pointer',
          fontSize: '11px',
          color: '#4ec9b0',
          marginBottom: '12px'
        }}>
          <Upload size={14} />
          <span>{uploadedFileName ? uploadedFileName : "Upload .pdf, .docx, .ipynb, .txt"}</span>
          <input 
            type="file" 
            accept=".pdf,.docx,.ipynb,.txt,.py,.sh,.md" 
            onChange={handleFileUpload} 
            style={{ display: 'none' }} 
          />
        </label>

        <textarea
          value={topicInput}
          onChange={(e) => setTopicInput(e.target.value)}
          placeholder="E.g.: 'Make an exercise on piping and flags' or 'Focus on calculus derivatives'"
          rows={3}
          style={{ width: '100%', backgroundColor: theme.bgApp, color: theme.textMain, border: `1px solid ${theme.border}`, padding: '8px', borderRadius: '4px', fontSize: '11px', fontFamily: 'inherit', resize: 'none', marginBottom: '10px' }}
        />
        <button
          onClick={handleGenerate}
          disabled={loading}
          style={{ backgroundColor: theme.accent, color: 'white', border: 'none', padding: '9px', borderRadius: '4px', cursor: loading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '12px', fontWeight: 'bold' }}
        >
          {loading ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
          {loading ? "Synthesizing..." : "Generate Puzzle"}
        </button>

        <div style={{ margin: '20px 0 8px 0', fontSize: '11px', fontWeight: 'bold', color: theme.textDim, textTransform: 'uppercase' }}>
          Interactive Tokens
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1, overflowY: 'auto' }}>
          {puzzle && puzzle.variants && puzzle.variants.map((v) => (
            <div
              key={v}
              draggable
              onDragStart={(e) => e.dataTransfer.setData("text/plain", v)}
              onClick={() => handleSelectToken(v)}
              style={{
                padding: '9px 12px',
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
              {evaluation === 'correct' ? 'Logical Match' : 'Unstable / Incomplete'}
            </div>
            <span>{puzzle.explanation}</span>
          </div>
        )}
      </aside>

      {/* 2. CENTER PANEL */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: `1px solid ${theme.border}` }}>
        <div style={{ height: '35px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', borderBottom: `1px solid ${theme.border}` }}>
          <span style={{ fontSize: '12px', color: '#4ec9b0' }}>
            {puzzle ? `${puzzle.title} [${puzzle.topic}]` : 'workspace.sh'}
          </span>
          {slottedAnswer && (
            <button onClick={() => { setSlottedAnswer(null); setEvaluation(null); }} style={{ background: 'transparent', border: 'none', color: theme.textDim, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
              <RefreshCw size={12} /> Clear Slot
            </button>
          )}
        </div>

        <div style={{ flex: 1, backgroundColor: theme.bgEditor, padding: '24px', fontSize: '15px', overflowY: 'auto' }}>
          {puzzle ? renderCodeWithSlot(puzzle.code_template) : (
            <div style={{ color: theme.textDim, fontSize: '13px' }}>
              {loading ? "Generating puzzle from document..." : "Click 'Generate Puzzle' to start."}
            </div>
          )}
        </div>

        {/* Terminal */}
        <div style={{ height: '180px', backgroundColor: '#141414', borderTop: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ height: '26px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', padding: '0 12px', gap: '8px' }}>
            <Terminal size={12} color="#4ec9b0" />
            <span style={{ fontSize: '11px', color: theme.textDim, fontWeight: 'bold' }}>EXECUTION SANDBOX</span>
          </div>
          <div style={{ padding: '10px 14px', overflowY: 'auto', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {terminalOutput.map((l, i) => (
              <span key={i} style={{ color: l.includes('[ERROR]') || l.includes('[MUTANT') ? '#f87171' : l.includes('[SUCCESS]') ? '#4ade80' : '#cccccc' }}>
                {l}
              </span>
            ))}
          </div>
        </div>
      </main>

      {/* 3. RIGHT PANEL */}
      <section style={{ width: '340px', backgroundColor: theme.bgSidebar, display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: '35px', padding: '0 16px', borderBottom: `1px solid ${theme.border}`, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={14} color="#cca700" />
          <span style={{ fontSize: '12px', fontWeight: 'bold', color: theme.textMain }}>Socratic Tutor</span>
        </div>

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
          {chatLoading && <div style={{ color: theme.textDim, fontSize: '11px', fontStyle: 'italic' }}>Tutor is thinking...</div>}
        </div>

        <form onSubmit={handleSendMessage} style={{ padding: '12px', borderTop: `1px solid ${theme.border}`, display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            placeholder="Type answer or '!reveal'..."
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