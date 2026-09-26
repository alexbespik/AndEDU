import React, { useState, useEffect } from 'react';
import { Terminal, Send, Play, CheckCircle2, AlertTriangle, RefreshCw, Loader2, Sparkles, Upload, BookOpen, Code2, Plus, ArrowDown } from 'lucide-react';

const EduIDE = () => {
  const [topicInput, setTopicInput] = useState("Python loops: create a loop that sums numbers safely");
  const [documentText, setDocumentText] = useState("");
  const [uploadedFileName, setUploadedFileName] = useState(null);
  const [puzzle, setPuzzle] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // gamified state
  const [activeTab, setActiveTab] = useState("editor"); // 'editor' | 'docs'
  const [availableBank, setAvailableBank] = useState([]); // Blocks in the bank
  const [assembledBlocks, setAssembledBlocks] = useState([]); // Blocks placed in assembly zone
  const [evaluation, setEvaluation] = useState(null);
  const [terminalOutput, setTerminalOutput] = useState([
    "[SYSTEM] Environment ready (Gemini 3.1 Flash-Lite Engine).",
    "[STATUS] Tap blocks from the bank below to construct code block by block."
  ]);

  const [chatHistory, setChatHistory] = useState([]);
  const [userInput, setUserInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // Initialize Puzzle into CODE BLOCKS
  const loadPuzzle = (data) => {
    setPuzzle(data);
    setAvailableBank(data.blocks_pool || []);
    setAssembledBlocks([]);
    setEvaluation(null);
    setChatHistory([
      { role: 'model', content: `I've prepared **${data.title}** (${data.domain}). Read the **Concept Docs** tab first, or start snapping code blocks into place!` }
    ]);
    setTerminalOutput([
      `[LOADED] Unit: ${data.title} [${data.domain}]`,
      `[CHALLENGE] ${data.guiding_question}`
    ]);
  };

  // Generate Puzzle
  const handleGenerate = async () => {
    setLoading(true);
    setEvaluation(null);
    setTerminalOutput([`[MCP_DISPATCH] Gemini 3.1 Flash-Lite generating CODE BLOCKS for: "${uploadedFileName || topicInput}"...`]);

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
      loadPuzzle(data);
    } catch (err) {
      setTerminalOutput(["[ERROR] Backend unreachable at http://localhost:8000. Is server.py running?"]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleGenerate();
  }, []);

  // File Upload (Images & Docs)
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadedFileName(file.name);
    setLoading(true);
    setTerminalOutput([`[INGESTION] Reading ${file.name}...`]);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/upload-multimodal", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.blocks_pool) {
        loadPuzzle(data);
      } else {
        setDocumentText(data.extracted_text || "");
        setTerminalOutput([
          `[PARSED] ${file.name}`,
          `[READY] Click 'Generate Puzzle' to build block challenges from this file.`
        ]);
      }
    } catch (err) {
      setTerminalOutput([`[ERROR] Failed to process ${file.name}`]);
    } finally {
      setLoading(false);
    }
  };

  // --- Code BLOCK INTERACTION ---
  const pushBlockToAssembly = (block, indexInBank) => {
    setAssembledBlocks(prev => [...prev, block]);
    setAvailableBank(prev => prev.filter((_, idx) => idx !== indexInBank));
  };

  const removeBlockFromAssembly = (block, indexInAssembly) => {
    setAssembledBlocks(prev => prev.filter((_, idx) => idx !== indexInAssembly));
    setAvailableBank(prev => [...prev, block]);
  };

  const resetAllBlocks = () => {
    if (!puzzle) return;
    setAvailableBank(puzzle.blocks_pool || []);
    setAssembledBlocks([]);
    setEvaluation(null);
  };

  // Check assembly correctness
  useEffect(() => {
    if (!puzzle || assembledBlocks.length === 0) {
      setEvaluation(null);
      return;
    }

    const currentSeq = assembledBlocks.join("\n").trim();
    const correctSeq = puzzle.correct_blocks.join("\n").trim();

    if (currentSeq === correctSeq) {
      setEvaluation('correct');
      setTerminalOutput([
        `[EXECUTING ASSEMBLED CODE]:`,
        ...assembledBlocks,
        "------------------------------------",
        ...(puzzle.test_cases || []),
        "[SUCCESS] Code constructed cleanly!"
      ]);
    } else if (assembledBlocks.length >= puzzle.correct_blocks.length) {
      setEvaluation('wrong');
      setTerminalOutput([
        `[ASSEMBLY MUTANT ERROR]: Order or block selection is incorrect.`,
        "[HINT] Check indentation, logic sequence, or consult your Socratic Tutor."
      ]);
    }
  }, [assembledBlocks]);

  // Tutor Dialogue (With Assignment Change Handler)
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

      // Tutor changed the assignment!
      if (data.mutated_puzzle) {
        loadPuzzle(data.mutated_puzzle);
      }
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'model', content: "[Connection Error]" }]);
    } finally {
      setChatLoading(false);
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
      
      {/* 1. LEFT PANEL */}
      <aside style={{ width: '290px', backgroundColor: theme.bgSidebar, borderRight: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column', padding: '16px' }}>
        <div style={{ fontSize: '11px', fontWeight: 'bold', color: theme.textDim, marginBottom: '8px', textTransform: 'uppercase' }}>
          Educational Ingestion
        </div>

        <label style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '10px',
          backgroundColor: '#2d2d30', border: '1px dashed #4ec9b0', borderRadius: '4px', cursor: 'pointer',
          fontSize: '11px', color: '#4ec9b0', marginBottom: '12px'
        }}>
          <Upload size={14} />
          <span>{uploadedFileName || "Upload Doc or Image"}</span>
          <input type="file" accept=".pdf,.docx,.ipynb,.txt,.png,.jpg,.jpeg,.webp" onChange={handleFileUpload} style={{ display: 'none' }} />
        </label>

        <textarea
          value={topicInput}
          onChange={(e) => setTopicInput(e.target.value)}
          placeholder="Topic or task instructions..."
          rows={2}
          style={{ width: '100%', backgroundColor: theme.bgApp, color: theme.textMain, border: `1px solid ${theme.border}`, padding: '8px', borderRadius: '4px', fontSize: '11px', fontFamily: 'inherit', resize: 'none', marginBottom: '10px' }}
        />

        <button
          onClick={handleGenerate}
          disabled={loading}
          style={{ backgroundColor: theme.accent, color: 'white', border: 'none', padding: '9px', borderRadius: '4px', cursor: loading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '12px', fontWeight: 'bold' }}
        >
          {loading ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
          {loading ? "Generating..." : "Generate Puzzle"}
        </button>

        {evaluation && (
          <div style={{ marginTop: 'auto', padding: '12px', borderRadius: '4px', backgroundColor: evaluation === 'correct' ? '#064e3b' : '#450a0a', border: `1px solid ${evaluation === 'correct' ? '#10b981' : '#f87171'}`, fontSize: '11px' }}>
            <div style={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              {evaluation === 'correct' ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
              {evaluation === 'correct' ? 'Perfect Code Assembly!' : 'Logic / Order Mismatch'}
            </div>
            <span>{puzzle.explanation}</span>
          </div>
        )}
      </aside>

      {/* 2. CENTER PANEL (Code Assembly & Docs) */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: `1px solid ${theme.border}` }}>
        {/* Tabs */}
        <div style={{ height: '36px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', borderBottom: `1px solid ${theme.border}` }}>
          <div 
            onClick={() => setActiveTab("editor")}
            style={{ 
              height: '100%', padding: '0 16px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer',
              backgroundColor: activeTab === 'editor' ? theme.bgEditor : 'transparent',
              borderTop: activeTab === 'editor' ? `2px solid ${theme.accent}` : 'none',
              color: activeTab === 'editor' ? '#fff' : theme.textDim
            }}
          >
            <Code2 size={14} color="#4ec9b0" /> Code Block Builder
          </div>
          <div 
            onClick={() => setActiveTab("docs")}
            style={{ 
              height: '100%', padding: '0 16px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer',
              backgroundColor: activeTab === 'docs' ? theme.bgEditor : 'transparent',
              borderTop: activeTab === 'docs' ? `2px solid #cca700` : 'none',
              color: activeTab === 'docs' ? '#fff' : theme.textDim
            }}
          >
            <BookOpen size={14} color="#cca700" /> Concept Docs & Briefing
          </div>
        </div>

        {/* View 1: Docs */}
        {activeTab === "docs" && (
          <div style={{ flex: 1, backgroundColor: theme.bgEditor, padding: '28px', overflowY: 'auto', lineHeight: '1.7', fontSize: '14px' }}>
            <h2 style={{ color: '#4ec9b0', marginTop: 0 }}>📖 Concept Briefing</h2>
            <div style={{ whiteSpace: 'pre-wrap', color: '#d4d4d4' }}>
              {puzzle ? puzzle.briefing_markdown : "No docs generated yet."}
            </div>
          </div>
        )}

        {/* View 2: Code Block Canvas */}
        {activeTab === "editor" && (
          <div style={{ flex: 1, backgroundColor: theme.bgEditor, padding: '20px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <p style={{ color: '#9cdcfe', fontSize: '13px', margin: 0 }}>
                {puzzle ? puzzle.guiding_question : "Loading puzzle..."}
              </p>
              {assembledBlocks.length > 0 && (
                <button onClick={resetAllBlocks} style={{ background: 'transparent', border: `1px solid ${theme.border}`, color: theme.textDim, padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <RefreshCw size={12} /> Reset Blocks
                </button>
              )}
            </div>

            {/* gamified CODE ASSEMBLY ZONE */}
            <div style={{
              flex: 1,
              backgroundColor: '#141414',
              border: `2px dashed ${evaluation === 'correct' ? '#10b981' : evaluation === 'wrong' ? '#f87171' : '#333333'}`,
              borderRadius: '6px',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              overflowY: 'auto'
            }}>
              {assembledBlocks.length === 0 ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#555', fontSize: '13px' }}>
                  <ArrowDown size={16} style={{ marginRight: '8px' }} /> Tap blocks below to construct your code
                </div>
              ) : (
                assembledBlocks.map((block, idx) => (
                  <div
                    key={idx}
                    onClick={() => removeBlockFromAssembly(block, idx)}
                    style={{
                      padding: '8px 14px',
                      backgroundColor: '#1f2430',
                      border: '1px solid #007acc',
                      borderRadius: '4px',
                      color: '#d4d4d4',
                      fontSize: '13px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
                    }}
                  >
                    <span style={{ whiteSpace: 'pre' }}>{block}</span>
                    <span style={{ fontSize: '10px', color: '#858585' }}>tap to remove ✕</span>
                  </div>
                ))
              )}
            </div>

            {/* Code BLOCK BANK */}
            <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: `1px solid ${theme.border}` }}>
              <div style={{ fontSize: '11px', fontWeight: 'bold', color: theme.textDim, marginBottom: '8px', textTransform: 'uppercase' }}>
                Block Bank (Tap to Assemble)
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', minHeight: '60px' }}>
                {availableBank.map((block, idx) => (
                  <div
                    key={idx}
                    onClick={() => pushBlockToAssembly(block, idx)}
                    style={{
                      padding: '8px 12px',
                      backgroundColor: '#2d2d30',
                      border: '1px solid #3e3e42',
                      borderRadius: '4px',
                      color: '#9cdcfe',
                      fontSize: '12px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    <Plus size={12} color="#4ec9b0" />
                    <span style={{ whiteSpace: 'pre' }}>{block}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Terminal */}
        <div style={{ height: '160px', backgroundColor: '#141414', borderTop: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ height: '26px', backgroundColor: theme.bgSidebar, display: 'flex', alignItems: 'center', padding: '0 12px', gap: '8px' }}>
            <Terminal size={12} color="#4ec9b0" />
            <span style={{ fontSize: '11px', color: theme.textDim, fontWeight: 'bold' }}>SANDBOX CONSOLE</span>
          </div>
          <div style={{ padding: '8px 14px', overflowY: 'auto', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {terminalOutput.map((l, i) => (
              <span key={i} style={{ color: l.includes('[ERROR]') || l.includes('FAIL') ? '#f87171' : l.includes('[SUCCESS]') ? '#4ade80' : '#cccccc' }}>
                {l}
              </span>
            ))}
          </div>
        </div>
      </main>

      {/* 3. RIGHT PANEL (Socratic Tutor with Assignment Changer) */}
      <section style={{ width: '340px', backgroundColor: theme.bgSidebar, display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: '36px', padding: '0 16px', borderBottom: `1px solid ${theme.border}`, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={14} color="#cca700" />
          <span style={{ fontSize: '12px', fontWeight: 'bold', color: theme.textMain }}>Socratic Mentor</span>
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
          {chatLoading && <div style={{ color: theme.textDim, fontSize: '11px', fontStyle: 'italic' }}>Tutor is evaluating...</div>}
        </div>

        <form onSubmit={handleSendMessage} style={{ padding: '12px', borderTop: `1px solid ${theme.border}`, display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            placeholder="E.g.: 'Make an easier assignment' or ask for hints..."
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