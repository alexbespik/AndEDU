import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import { MousePointer2, Pencil, Minus, MoveUpRight, Square, Circle, Type, Eraser, Undo2, Redo2, Trash2 } from 'lucide-react';

// A small whiteboard (Excalidraw-like): shapes are data, rendered as SVG, so undo, moving and a crisp PNG export
// are simple. The board is always "paper" (white) so drawings read the same in both themes and for the checker.
const W = 1000, H = 620;
const COLORS = [['#1b1f1d', 'Black'], ['#0e4a37', 'Green'], ['#b8860b', 'Gold'], ['#c0392b', 'Red'], ['#2563a0', 'Blue']];
const WIDTHS = [2, 4, 7];
const TOOLS = [
  ['select', MousePointer2, 'Select and move (V)'], ['pen', Pencil, 'Pen (P)'], ['line', Minus, 'Line (L)'], ['arrow', MoveUpRight, 'Arrow (A)'],
  ['rect', Square, 'Box (R)'], ['ellipse', Circle, 'Circle (O)'], ['text', Type, 'Text (T)'], ['eraser', Eraser, 'Eraser (E)'],
];
const KEYS = { v: 'select', p: 'pen', l: 'line', a: 'arrow', r: 'rect', o: 'ellipse', t: 'text', e: 'eraser' };
let nextId = 1;

function bbox(s) {
  if (s.type === 'pen') {
    const xs = s.pts.map((p) => p[0]), ys = s.pts.map((p) => p[1]);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  if (s.type === 'text') return [s.x1, s.y1 - s.size, s.x1 + s.text.length * s.size * 0.55, s.y1 + 4];
  return [Math.min(s.x1, s.x2), Math.min(s.y1, s.y2), Math.max(s.x1, s.x2), Math.max(s.y1, s.y2)];
}
const hit = (s, x, y, pad = 10) => { const [a, b, c, d] = bbox(s); return x >= a - pad && x <= c + pad && y >= b - pad && y <= d + pad; };
const moved = (s, dx, dy) => (s.type === 'pen'
  ? { ...s, pts: s.pts.map(([x, y]) => [x + dx, y + dy]) }
  : { ...s, x1: s.x1 + dx, y1: s.y1 + dy, x2: (s.x2 ?? s.x1) + dx, y2: (s.y2 ?? s.y1) + dy });

function Shape({ s, selected }) {
  const common = { stroke: s.color, strokeWidth: s.w, fill: 'none', strokeLinecap: 'round', strokeLinejoin: 'round' };
  let el;
  if (s.type === 'pen') el = <polyline points={s.pts.map((p) => p.join(',')).join(' ')} {...common} />;
  else if (s.type === 'line') el = <line x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} {...common} />;
  else if (s.type === 'arrow') el = <line x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} {...common} markerEnd={`url(#ah-${s.color.slice(1)})`} />;
  else if (s.type === 'rect') el = <rect x={Math.min(s.x1, s.x2)} y={Math.min(s.y1, s.y2)} width={Math.abs(s.x2 - s.x1)} height={Math.abs(s.y2 - s.y1)} rx="6" {...common} />;
  else if (s.type === 'ellipse') el = <ellipse cx={(s.x1 + s.x2) / 2} cy={(s.y1 + s.y2) / 2} rx={Math.abs(s.x2 - s.x1) / 2} ry={Math.abs(s.y2 - s.y1) / 2} {...common} />;
  else if (s.type === 'text') el = <text x={s.x1} y={s.y1} fill={s.color} fontSize={s.size} fontFamily="'IBM Plex Sans', Arial, sans-serif">{s.text}</text>;
  if (!selected) return el;
  const [a, b, c, d] = bbox(s);
  return <g>{el}<rect x={a - 6} y={b - 6} width={c - a + 12} height={d - b + 12} fill="none" stroke="#2563a0" strokeDasharray="5 4" strokeWidth="1.5" /></g>;
}

/** Whiteboard with pen, shapes, arrows, text, eraser, move, undo/redo. Ref exposes toPNG() and isEmpty(). */
const DrawingBoard = forwardRef(function DrawingBoard({ background = 'grid', onChange }, ref) {
  const [shapes, setShapes] = useState([]);
  const [future, setFuture] = useState([]);
  const [tool, setTool] = useState('pen');
  const [color, setColor] = useState(COLORS[0][0]);
  const [width, setWidth] = useState(WIDTHS[1]);
  const [draft, setDraft] = useState(null);
  const [selected, setSelected] = useState(null);
  const [typing, setTypingState] = useState(null); // {x, y, text}
  const typingRef = useRef(null);
  const textInput = useRef(null);  // read by finishText, so Enter right after typing never sees stale text
  const setTyping = (v) => { const next = typeof v === 'function' ? v(typingRef.current) : v; typingRef.current = next; setTypingState(next); };
  const svgRef = useRef(null);
  const drag = useRef(null);
  const history = useRef([]);

  const commit = (next) => { history.current.push(shapes); setFuture([]); setShapes(next); onChange?.(next); };
  const undo = () => { if (!history.current.length) return; setFuture((f) => [shapes, ...f]); const prev = history.current.pop(); setShapes(prev); onChange?.(prev); };
  const redo = () => { if (!future.length) return; history.current.push(shapes); setShapes(future[0]); setFuture((f) => f.slice(1)); onChange?.(future[0]); };

  useImperativeHandle(ref, () => ({
    isEmpty: () => shapes.length === 0,
    getShapes: () => shapes,
    toPNG: () => new Promise((resolve, reject) => {
      const svg = svgRef.current.cloneNode(true);
      svg.querySelectorAll('[data-ui]').forEach((n) => n.remove());
      svg.setAttribute('width', W); svg.setAttribute('height', H);
      const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml' }));
      const img = new Image();
      img.onload = () => {
        const c = document.createElement('canvas'); c.width = W; c.height = H;
        const ctx = c.getContext('2d'); ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, W, H); ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url); resolve(c.toDataURL('image/png'));
      };
      img.onerror = reject; img.src = url;
    }),
  }), [shapes]);

  const pt = (e) => {
    const r = svgRef.current.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * W, ((e.clientY - r.top) / r.height) * H];
  };

  const down = (e) => {
    if (typing) { finishText(); return; }
    const [x, y] = pt(e);
    e.currentTarget.setPointerCapture(e.pointerId);
    if (tool === 'eraser') { const top = [...shapes].reverse().find((s) => hit(s, x, y)); if (top) commit(shapes.filter((s) => s !== top)); drag.current = { erase: true }; return; }
    if (tool === 'select') {
      const top = [...shapes].reverse().find((s) => hit(s, x, y));
      setSelected(top?.id ?? null);
      if (top) drag.current = { move: top.id, x, y, start: shapes };
      return;
    }
    if (tool === 'text') {
      e.preventDefault();  // keep the click from moving focus to the board, which would blur the new text box
      setTyping({ x, y, text: '' });
      requestAnimationFrame(() => textInput.current?.focus());
      return;
    }
    const base = { id: nextId++, type: tool, color, w: width };
    setDraft(tool === 'pen' ? { ...base, pts: [[x, y]] } : { ...base, x1: x, y1: y, x2: x, y2: y });
  };
  const move = (e) => {
    const [x, y] = pt(e);
    if (drag.current?.erase && e.buttons) { const top = [...shapes].reverse().find((s) => hit(s, x, y, 4)); if (top) setShapes((ss) => ss.filter((s) => s !== top)); return; }
    if (drag.current?.move) {
      const d = drag.current; const dx = x - d.x, dy = y - d.y;
      setShapes(d.start.map((s) => (s.id === d.move ? moved(s, dx, dy) : s)));
      return;
    }
    if (!draft) return;
    setDraft((d) => (d.type === 'pen' ? { ...d, pts: [...d.pts, [x, y]] } : { ...d, x2: e.shiftKey && d.type !== 'pen' ? x : x, y2: y }));
  };
  const up = () => {
    if (drag.current?.move) { history.current.push(drag.current.start); setFuture([]); onChange?.(shapes); }
    if (drag.current?.erase) onChange?.(shapes);
    drag.current = null;
    if (!draft) return;
    const tiny = draft.type === 'pen' ? draft.pts.length < 2 : Math.hypot(draft.x2 - draft.x1, draft.y2 - draft.y1) < 4;
    if (!tiny) commit([...shapes, draft]);
    setDraft(null);
  };
  const finishText = () => {
    const t = typingRef.current;
    if (!t) return;
    setTyping(null);
    if (t.text.trim()) commit([...shapes, { id: nextId++, type: 'text', color, w: 0, size: 18 + width * 2, x1: t.x, y1: t.y, text: t.text.trim() }]);
  };
  const onKey = (e) => {
    if (typing) return;
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return; }
    if ((e.key === 'Delete' || e.key === 'Backspace') && selected) { commit(shapes.filter((s) => s.id !== selected)); setSelected(null); return; }
    if (KEYS[e.key.toLowerCase()] && !e.metaKey && !e.ctrlKey) setTool(KEYS[e.key.toLowerCase()]);
  };

  const r = svgRef.current?.getBoundingClientRect();
  return (
    <div className="board" onKeyDown={onKey} tabIndex={0} aria-label="Drawing board">
      <div className="board-bar" role="toolbar" aria-label="Drawing tools">
        {TOOLS.map(([id, Icon, label]) => (
          <button key={id} type="button" className="board-tool" aria-pressed={tool === id} title={label} aria-label={label} onClick={() => { setTool(id); setSelected(null); }}><Icon size={17} /></button>
        ))}
        <span className="board-sep" />
        {COLORS.map(([c, n]) => <button key={c} type="button" className="board-swatch" aria-pressed={color === c} title={n} aria-label={n} style={{ '--sw': c }} onClick={() => setColor(c)} />)}
        <span className="board-sep" />
        {WIDTHS.map((w) => <button key={w} type="button" className="board-tool" aria-pressed={width === w} title={`Stroke ${w}`} aria-label={`Stroke ${w}`} onClick={() => setWidth(w)}><span className="board-dot" style={{ width: w + 3, height: w + 3 }} /></button>)}
        <span className="board-sep" />
        <button type="button" className="board-tool" title="Undo (Ctrl+Z)" aria-label="Undo" onClick={undo} disabled={!history.current.length}><Undo2 size={17} /></button>
        <button type="button" className="board-tool" title="Redo (Ctrl+Shift+Z)" aria-label="Redo" onClick={redo} disabled={!future.length}><Redo2 size={17} /></button>
        <button type="button" className="board-tool" title="Clear" aria-label="Clear the board" onClick={() => shapes.length && commit([])}><Trash2 size={17} /></button>
      </div>
      <div className="board-surface">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} xmlns="http://www.w3.org/2000/svg" data-tool={tool}
          onPointerDown={down} onPointerMove={move} onPointerUp={up} style={{ touchAction: 'none' }}>
          <defs>
            <pattern id="board-grid" width="25" height="25" patternUnits="userSpaceOnUse"><path d="M 25 0 L 0 0 0 25" fill="none" stroke="#e3e0d6" strokeWidth="1" /></pattern>
            {COLORS.map(([c]) => (
              <marker key={c} id={`ah-${c.slice(1)}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill={c} />
              </marker>
            ))}
          </defs>
          <rect width={W} height={H} fill="#ffffff" />
          {background !== 'blank' && <rect width={W} height={H} fill="url(#board-grid)" />}
          {background === 'axes' && (
            <g stroke="#9a9588" strokeWidth="1.5"><line x1="40" y1={H / 2} x2={W - 20} y2={H / 2} /><line x1={W / 2} y1="20" x2={W / 2} y2={H - 20} /></g>
          )}
          {shapes.map((s) => <Shape key={s.id} s={s} selected={tool === 'select' && s.id === selected} />)}
          {draft && <Shape s={draft} />}
        </svg>
        {typing && r && (
          <input ref={textInput} autoFocus className="board-text" value={typing.text} placeholder="Type, then Enter"
            style={{ left: (typing.x / W) * r.width, top: (typing.y / H) * r.height - 22, color }}
            onChange={(e) => setTyping((t) => ({ ...t, text: e.target.value }))}
            onKeyDown={(e) => { if (e.key === 'Enter') finishText(); if (e.key === 'Escape') setTyping(null); e.stopPropagation(); }}
            onBlur={finishText} />
        )}
      </div>
    </div>
  );
});

export default DrawingBoard;
