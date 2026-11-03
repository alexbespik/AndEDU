import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, RotateCcw, Eye, Compass, Zap, Activity, Info } from 'lucide-react';
import { theme, canvasPalette } from '../theme';

export default function RollingWithoutSlippingSim() {
  const canvasRef = useRef(null);
  const [isRunning, setIsRunning] = useState(true);
  const [vCm, setVCm] = useState(60); // pixels per sec
  const [radius, setRadius] = useState(55); // pixels
  const [omegaRatio, setOmegaRatio] = useState(1.0); // ratio: omega / (vCm / radius)
  const [lockNoSlip, setLockNoSlip] = useState(true);
  const [showVectors, setShowVectors] = useState(true);
  const [showCycloid, setShowCycloid] = useState(true);
  const [showForces, setShowForces] = useState(false);
  const [objectType, setObjectType] = useState('cylinder'); // sphere (2/5), cylinder (1/2), hoop (1)

  // Simulation state
  const stateRef = useRef({
    x: 100,
    theta: 0,
    cycloidPoints: [],
    lastTime: null,
  });

  const getInertiaFactor = () => {
    if (objectType === 'hoop') return 1.0;
    if (objectType === 'cylinder') return 0.5;
    if (objectType === 'sphere') return 0.4; // 2/5
    return 0.5;
  };

  const handleReset = () => {
    stateRef.current.x = 80;
    stateRef.current.theta = 0;
    stateRef.current.cycloidPoints = [];
  };

  useEffect(() => {
    let animationFrameId;

    const render = (currentTime) => {
      if (!stateRef.current.lastTime) {
        stateRef.current.lastTime = currentTime;
      }
      const dt = Math.min((currentTime - stateRef.current.lastTime) / 1000, 0.1);
      stateRef.current.lastTime = currentTime;

      const canvas = canvasRef.current;
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== 860 * dpr) { canvas.width = 860 * dpr; canvas.height = 320 * dpr; }
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const P = canvasPalette();
      const width = 860;
      const height = 320;
      const groundY = height - 70;

      // Effective omega
      const effectiveOmega = lockNoSlip 
        ? vCm / radius 
        : (vCm / radius) * omegaRatio;

      // Update positions if running
      if (isRunning) {
        stateRef.current.x += vCm * dt;
        stateRef.current.theta += effectiveOmega * dt;

        // Wrap around canvas smoothly
        if (stateRef.current.x > width + radius + 20) {
          stateRef.current.x = -radius;
          stateRef.current.cycloidPoints = [];
        }

        // Trace cycloid point (red marker on rim)
        // Note: Rim marker rotated by theta has canvas position x - R*sin(theta), y - R + R*cos(theta)
        const rimX = stateRef.current.x - radius * Math.sin(stateRef.current.theta);
        const rimY = (groundY - radius) + radius * Math.cos(stateRef.current.theta);
        stateRef.current.cycloidPoints.push({ x: rimX, y: rimY });
        if (stateRef.current.cycloidPoints.length > 280) {
          stateRef.current.cycloidPoints.shift();
        }
      }

      // Clear background
      ctx.fillStyle = P.surface;
      ctx.fillRect(0, 0, width, height);

      // Draw Grid lines
      ctx.strokeStyle = P.sunk;
      ctx.lineWidth = 1;
      for (let gx = 0; gx < width; gx += 40) {
        ctx.beginPath();
        ctx.moveTo(gx, 0);
        ctx.lineTo(gx, height);
        ctx.stroke();
      }
      for (let gy = 0; gy < height; gy += 40) {
        ctx.beginPath();
        ctx.moveTo(0, gy);
        ctx.lineTo(width, gy);
        ctx.stroke();
      }

      // Draw Ground
      ctx.strokeStyle = P.accent;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(0, groundY);
      ctx.lineTo(width, groundY);
      ctx.stroke();

      // Ground hatching
      ctx.strokeStyle = P['rule-strong'];
      ctx.lineWidth = 1.5;
      for (let hx = 0; hx < width; hx += 16) {
        ctx.beginPath();
        ctx.moveTo(hx, groundY);
        ctx.lineTo(hx - 10, groundY + 12);
        ctx.stroke();
      }

      // Draw Cycloid Trail
      if (showCycloid && stateRef.current.cycloidPoints.length > 1) {
        ctx.strokeStyle = P['gold-text'];
        ctx.lineWidth = 2.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        for (let i = 0; i < stateRef.current.cycloidPoints.length; i++) {
          const pt = stateRef.current.cycloidPoints[i];
          if (i === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.stroke();
        ctx.setLineDash([]);
      }

      const wheelX = stateRef.current.x;
      const wheelY = groundY - radius;
      const currentTheta = stateRef.current.theta;

      // Draw Wheel Rim Body
      ctx.save();
      ctx.translate(wheelX, wheelY);

      // Wheel shadow / outer glow
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, Math.PI * 2);
      ctx.fillStyle = P.sunk;
      ctx.fill();
      ctx.lineWidth = 4;
      ctx.strokeStyle = P['gold-text'];
      ctx.stroke();

      // Inner disc fill depending on inertia
      ctx.beginPath();
      ctx.arc(0, 0, radius - 4, 0, Math.PI * 2);
      ctx.fillStyle = objectType === 'hoop' ? P.surface : P.rule;
      ctx.fill();

      // Draw Rotating Spokes
      ctx.rotate(currentTheta);
      ctx.lineWidth = 2;
      ctx.strokeStyle = P.muted;
      for (let i = 0; i < 8; i++) {
        ctx.beginPath();
        ctx.moveTo(0, 0);
        const spokeAngle = (i * Math.PI) / 4;
        ctx.lineTo(radius * Math.cos(spokeAngle), radius * Math.sin(spokeAngle));
        ctx.stroke();
      }

      // Traced Rim Marker (Red/Gold Dot)
      ctx.beginPath();
      ctx.arc(0, radius, 6, 0, Math.PI * 2);
      ctx.fillStyle = P.bad;
      ctx.fill();
      ctx.strokeStyle = P.surface;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Hub center
      ctx.beginPath();
      ctx.arc(0, 0, 8, 0, Math.PI * 2);
      ctx.fillStyle = P.accent;
      ctx.fill();
      ctx.strokeStyle = P.surface;
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.restore();

      // Draw Velocity Vectors
      if (showVectors) {
        const drawArrow = (fromX, fromY, toX, toY, color, label) => {
          const headLen = 8;
          const angle = Math.atan2(toY - fromY, toX - fromX);
          ctx.strokeStyle = color;
          ctx.fillStyle = color;
          ctx.lineWidth = 2.5;

          // Main line
          ctx.beginPath();
          ctx.moveTo(fromX, fromY);
          ctx.lineTo(toX, toY);
          ctx.stroke();

          // Arrow head
          ctx.beginPath();
          ctx.moveTo(toX, toY);
          ctx.lineTo(toX - headLen * Math.cos(angle - Math.PI / 6), toY - headLen * Math.sin(angle - Math.PI / 6));
          ctx.lineTo(toX - headLen * Math.cos(angle + Math.PI / 6), toY - headLen * Math.sin(angle + Math.PI / 6));
          ctx.closePath();
          ctx.fill();

          if (label) {
            ctx.font = '11px "JetBrains Mono", monospace';
            ctx.fillStyle = color;
            ctx.fillText(label, toX + 6, toY - 4);
          }
        };

        const vScale = 0.8;
        const vCenter = vCm * vScale;
        const vTop = (vCm + effectiveOmega * radius) * vScale;
        const vBottom = (vCm - effectiveOmega * radius) * vScale;

        // Center vector
        drawArrow(wheelX, wheelY, wheelX + vCenter, wheelY, P.accent, `v_cm = ${Math.round(vCm)}`);

        // Top of wheel vector (2 * v_cm)
        drawArrow(wheelX, wheelY - radius, wheelX + vTop, wheelY - radius, P['gold-text'], `v_top = ${Math.round(vCm + effectiveOmega * radius)}`);

        // Bottom Contact Point Vector
        if (Math.abs(vBottom) < 0.8) {
          // Exactly at rest
          ctx.beginPath();
          ctx.arc(wheelX, groundY, 4, 0, Math.PI * 2);
          ctx.fillStyle = P.accent;
          ctx.fill();
          ctx.font = '11px "JetBrains Mono", monospace';
          ctx.fillStyle = P.accent;
          ctx.fillText('v_contact = 0 (Instantaneous Rest)', wheelX + 12, groundY + 16);
        } else {
          drawArrow(wheelX, groundY, wheelX + vBottom, groundY, P.bad, `v_slip = ${Math.round(vBottom)}`);
        }
      }

      // Draw Free Body Diagram Forces
      if (showForces) {
        // Gravity
        ctx.strokeStyle = P.info;
        ctx.fillStyle = P.info;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(wheelX, wheelY);
        ctx.lineTo(wheelX, wheelY + 45);
        ctx.stroke();
        ctx.fillText('Mg', wheelX + 6, wheelY + 40);

        // Normal Force
        ctx.strokeStyle = P.plum;
        ctx.fillStyle = P.plum;
        ctx.beginPath();
        ctx.moveTo(wheelX, groundY);
        ctx.lineTo(wheelX, groundY - 45);
        ctx.stroke();
        ctx.fillText('N', wheelX + 6, groundY - 35);
      }

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animationFrameId);
  }, [isRunning, vCm, radius, omegaRatio, lockNoSlip, showVectors, showCycloid, showForces, objectType]);

  // Derived quantities
  const currentOmega = lockNoSlip ? (vCm / radius) : (vCm / radius) * omegaRatio;
  const slipVelocity = vCm - currentOmega * radius;
  const cFactor = getInertiaFactor();
  const kTransRatio = 1 / (1 + cFactor);
  const kRotRatio = cFactor / (1 + cFactor);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Toolbar sits above the canvas so controls never cover the simulation or each other */}
      <div className="btn-row" style={{ justifyContent: 'space-between', gap: 'var(--space-3)' }}>
        <div className="readouts" role="status">
          <span>State: <strong style={{ color: Math.abs(slipVelocity) < 0.1 ? theme.success : theme.error }}>
            {Math.abs(slipVelocity) < 0.1 ? 'Rolling without slipping' : slipVelocity > 0 ? 'Skidding forward' : 'Spinning backward'}
          </strong></span>
          <span>v<sub>cm</sub> <b>{Math.round(vCm)} px/s</b></span>
          <span>ωR <b>{Math.round(currentOmega * radius)} px/s</b></span>
        </div>
        <div className="btn-row">
          <button type="button" className={`btn btn-sm ${isRunning ? 'btn-secondary' : 'btn-primary'}`} onClick={() => setIsRunning(!isRunning)}>
            {isRunning ? <><Pause size={14} aria-hidden="true" /> Pause</> : <><Play size={14} aria-hidden="true" /> Play</>}
          </button>
          <button type="button" className="btn btn-quiet btn-sm" onClick={handleReset}>
            <RotateCcw size={14} aria-hidden="true" /> Reset
          </button>
        </div>
      </div>

      <div className="sim-canvas">
        <canvas ref={canvasRef} width={860} height={320}
          role="img" aria-label="Wheel rolling along the ground with its rim point tracing a cycloid" />
      </div>

      {/* Control Panel Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: 14,
        background: theme.bgPanel,
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        padding: 16
      }}>
        {/* Sliders */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: 4, fontFamily: theme.fontSans }}>
              <span>Linear Velocity (v_cm):</span>
              <span style={{ color: theme.accentGreen }}>{vCm} px/s</span>
            </div>
            <input 
              type="range" 
              min={10} 
              max={150} 
              value={vCm} 
              onChange={(e) => setVCm(Number(e.target.value))}
              style={{ width: '100%', accentColor: theme.accentGreen }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: 4, fontFamily: theme.fontSans }}>
              <span>Radius (R):</span>
              <span style={{ color: theme.accentGold }}>{radius} px</span>
            </div>
            <input 
              type="range" 
              min={35} 
              max={85} 
              value={radius} 
              onChange={(e) => setRadius(Number(e.target.value))}
              style={{ width: '100%', accentColor: theme.accentGold }}
            />
          </div>

          {!lockNoSlip && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: 4, fontFamily: theme.fontSans }}>
                <span>Spin Multiplier (ω / (v/R)):</span>
                <span style={{ color: theme.accentCyan }}>{omegaRatio.toFixed(2)}x</span>
              </div>
              <input 
                type="range" 
                min={0.1} 
                max={2.5} 
                step={0.05}
                value={omegaRatio} 
                onChange={(e) => setOmegaRatio(Number(e.target.value))}
                style={{ width: '100%', accentColor: theme.accentCyan }}
              />
            </div>
          )}
        </div>

        {/* Toggles & Options */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.84rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={lockNoSlip} 
              onChange={(e) => setLockNoSlip(e.target.checked)}
              style={{ accentColor: theme.accentGreen }}
            />
            <span style={{ fontWeight: lockNoSlip ? 600 : 400, color: lockNoSlip ? theme.accentGreen : theme.textDim }}>
              Lock No-Slip Condition (v_cm = ω·R)
            </span>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={showVectors} 
              onChange={(e) => setShowVectors(e.target.checked)}
              style={{ accentColor: theme.accentGold }}
            />
            <span>Show Velocity Vectors (Top: 2v, Center: v, Bottom: 0)</span>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={showCycloid} 
              onChange={(e) => setShowCycloid(e.target.checked)}
              style={{ accentColor: theme.accentPink }}
            />
            <span>Trace Cycloid Path (Point on Rim)</span>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={showForces} 
              onChange={(e) => setShowForces(e.target.checked)}
              style={{ accentColor: theme.accentCyan }}
            />
            <span>Display Normal & Gravitational Forces</span>
          </label>
        </div>

        {/* Kinetic Energy Partition Monitor */}
        <div style={{
          background: theme.bgCard,
          border: `1px solid ${theme.border}`,
          borderRadius: 6,
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 8
        }}>
          <div style={{ fontSize: '0.78rem', color: theme.accentGold, fontWeight: 700, fontFamily: theme.fontSans }}>
            Share of kinetic energy
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <select 
              value={objectType} 
              onChange={(e) => setObjectType(e.target.value)}
              style={{
                background: theme.bgInput,
                border: `1px solid ${theme.border}`,
                color: theme.textMain,
                padding: '4px 8px',
                borderRadius: 4,
                fontFamily: theme.fontSans,
                fontSize: '0.78rem',
                width: '100%'
              }}
            >
              <option value="sphere">Solid Sphere (I = 0.40 MR²)</option>
              <option value="cylinder">Solid Cylinder / Disc (I = 0.50 MR²)</option>
              <option value="hoop">Thin Hoop / Ring (I = 1.00 MR²)</option>
            </select>
          </div>

          <div style={{ fontSize: '0.74rem', color: theme.textDim, lineHeight: 1.4 }}>
            <div>Translational: <strong style={{ color: theme.accentGreen }}>{(kTransRatio * 100).toFixed(1)}%</strong></div>
            <div>Rotational: <strong style={{ color: theme.accentCyan }}>{(kRotRatio * 100).toFixed(1)}%</strong></div>
          </div>

          {/* Energy split bar */}
          <div style={{ height: 10, background: theme.bgCardAlt, borderRadius: 5, overflow: 'hidden', display: 'flex' }}>
            <div style={{ width: `${kTransRatio * 100}%`, background: theme.accentGreen }} title="Translational" />
            <div style={{ width: `${kRotRatio * 100}%`, background: theme.accentCyan }} title="Rotational" />
          </div>
        </div>
      </div>
    </div>
  );
}
