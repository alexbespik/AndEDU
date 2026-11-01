import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, RotateCcw, Target, Zap, Activity, Info, Sparkles, Volume2 } from 'lucide-react';
import { theme } from '../theme';

export default function BilliardSim() {
  const canvasRef = useRef(null);
  const [isRunning, setIsRunning] = useState(false);
  const [strikeH, setStrikeH] = useState(0.4); // h / R: -1.0 to +1.0 (0.4 is sweet spot)
  const [strikeSpeed, setStrikeSpeed] = useState(240); // px/s
  const [aimAngleDeg, setAimAngleDeg] = useState(0); // degrees (0 is straight right)
  const [showVectors, setShowVectors] = useState(true);
  const [showFriction, setShowFriction] = useState(true);
  const [showSpinRing, setShowSpinRing] = useState(true);
  const [cueStriking, setCueStriking] = useState(false);
  const [collisionOccurred, setCollisionOccurred] = useState(false);
  const [hudData, setHudData] = useState({
    b1_v: 0,
    b1_omega: 0,
    b1_state: 'Ready on Felt',
    b2_v: 0,
    b2_omega: 0,
    k_trans: 0,
    k_rot: 0
  });

  const R = 24; // Ball radius in px
  const tableRef = useRef({
    b1: { x: 180, y: 180, vx: 0, vy: 0, omega: 0, theta: 0, mass: 1.0, color: '#fdfbf7', name: 'Cue Ball' },
    b2: { x: 520, y: 180, vx: 0, vy: 0, omega: 0, theta: 0, mass: 1.0, color: '#e5b85c', name: 'Object Ball (#1)' },
    cueAnim: 0,
    hasStruck: false,
    lastTime: null
  });

  const mu_k = 0.28; // Kinetic friction coefficient with cloth
  const g = 600; // Scaled gravity for responsive physics
  const I_factor = 0.4; // 2/5 for solid sphere

  const handleResetRack = () => {
    tableRef.current.b1 = { x: 180, y: 180, vx: 0, vy: 0, omega: 0, theta: 0, mass: 1.0, color: '#fdfbf7', name: 'Cue Ball' };
    tableRef.current.b2 = { x: 520, y: 180, vx: 0, vy: 0, omega: 0, theta: 0, mass: 1.0, color: '#e5b85c', name: 'Object Ball (#1)' };
    tableRef.current.cueAnim = 0;
    tableRef.current.hasStruck = false;
    tableRef.current.lastTime = null;
    setIsRunning(false);
    setCueStriking(false);
    setCollisionOccurred(false);
    setHudData({
      b1_v: 0,
      b1_omega: 0,
      b1_state: 'Ready on Felt',
      b2_v: 0,
      b2_omega: 0,
      k_trans: 0,
      k_rot: 0
    });
  };

  const handleStrike = () => {
    if (isRunning && tableRef.current.hasStruck) return;
    setCueStriking(true);
    let animProgress = 0;
    
    // Quick back-and-forth cue stick thrust animation
    const cueInterval = setInterval(() => {
      animProgress += 0.15;
      if (animProgress >= 1.0) {
        clearInterval(cueInterval);
        setCueStriking(false);
        // Execute physical impulse impact
        const rad = (aimAngleDeg * Math.PI) / 180;
        const v0 = strikeSpeed;
        const b1 = tableRef.current.b1;
        b1.vx = v0 * Math.cos(rad);
        b1.vy = v0 * Math.sin(rad);
        
        // Rotational impulse: omega = (5 * J * h) / (2 * M * R^2) = (5/2) * (h/R) * (v0 / R)
        b1.omega = (2.5 * strikeH * v0) / R;
        tableRef.current.hasStruck = true;
        setIsRunning(true);
      }
    }, 20);
  };

  const applyPreset = (hVal, label) => {
    handleResetRack();
    setStrikeH(hVal);
  };

  useEffect(() => {
    let animId;

    const render = (currentTime) => {
      if (!tableRef.current.lastTime) {
        tableRef.current.lastTime = currentTime;
      }
      const dt = Math.min((currentTime - tableRef.current.lastTime) / 1000, 0.05);
      tableRef.current.lastTime = currentTime;

      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const W = canvas.width;
      const H = canvas.height;

      const b1 = tableRef.current.b1;
      const b2 = tableRef.current.b2;

      // -------------------------------------------------------------
      // 1. PHYSICAL UPDATES (SKID-TO-ROLL TRANSITION & FRICTION)
      // -------------------------------------------------------------
      if (isRunning && tableRef.current.hasStruck) {
        [b1, b2].forEach((ball) => {
          const v = Math.sqrt(ball.vx * ball.vx + ball.vy * ball.vy);
          const dirX = v > 0.001 ? ball.vx / v : 1;
          const dirY = v > 0.001 ? ball.vy / v : 0;

          // Relative slip velocity along the travel direction
          // Contact point velocity = v_cm - R * omega
          const v_contact = v - R * ball.omega;

          if (Math.abs(v_contact) > 1.5) {
            // SLIPPING / SKIDDING PHASE
            // Friction force opposes relative motion of contact point
            // fk = mu_k * M * g
            const fk_mag = mu_k * g * ball.mass;
            const fk_dir = v_contact > 0 ? -1 : 1; // if contact moving forward, friction points backward

            // dv/dt = (fk_dir) * fk / M
            const dv = fk_dir * (mu_k * g) * dt;
            const newV = Math.max(0, v + dv);
            ball.vx = newV * dirX;
            ball.vy = newV * dirY;

            // d_omega/dt = tau / I = (fk * R) / (2/5 * M * R^2) = (5/2) * (mu_k * g / R) * (-fk_dir)
            const d_omega = -fk_dir * (2.5 * mu_k * g / R) * dt;
            ball.omega += d_omega;
          } else {
            // PURE ROLLING PHASE: v_contact = 0  => v = R * omega
            // Only gentle rolling resistance decelerates the ball
            const rollDecel = 28 * dt;
            const newV = Math.max(0, v - rollDecel);
            ball.vx = newV * dirX;
            ball.vy = newV * dirY;
            ball.omega = newV / R;
          }

          // Position updates
          ball.x += ball.vx * dt;
          ball.y += ball.vy * dt;
          ball.theta += ball.omega * dt;

          // Cushion boundaries with bounce
          const pad = R + 18;
          if (ball.x < pad) { ball.x = pad; ball.vx = -ball.vx * 0.75; }
          if (ball.x > W - pad) { ball.x = W - pad; ball.vx = -ball.vx * 0.75; }
          if (ball.y < pad) { ball.y = pad; ball.vy = -ball.vy * 0.75; }
          if (ball.y > H - pad) { ball.y = H - pad; ball.vy = -ball.vy * 0.75; }
        });

        // -------------------------------------------------------------
        // 2. ELASTIC 2-BALL COLLISION WITH ANGULAR MOMENTUM INVARIANCE
        // -------------------------------------------------------------
        const dx = b2.x - b1.x;
        const dy = b2.y - b1.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist <= 2 * R && dist > 0.001) {
          // Collision Normal & Tangent
          const nx = dx / dist;
          const ny = dy / dist;
          const tx = -ny;
          const ty = nx;

          // Project velocities onto Normal and Tangent
          const v1n = b1.vx * nx + b1.vy * ny;
          const v1t = b1.vx * tx + b1.vy * ty;
          const v2n = b2.vx * nx + b2.vy * ny;
          const v2t = b2.vx * tx + b2.vy * ty;

          // Elastic collision along line of centers (equal masses exchange normal velocity)
          if (v1n - v2n > 0) {
            const v1n_after = v2n;
            const v2n_after = v1n;

            // Reconstruct velocity vectors
            b1.vx = v1n_after * nx + v1t * tx;
            b1.vy = v1n_after * ny + v1t * ty;
            b2.vx = v2n_after * nx + v2t * tx;
            b2.vy = v2n_after * ny + v2t * ty;

            // CRITICAL RIGID BODY PROPERTY:
            // The impulsive contact force is normal (friction during infinitesimal impact is negligible).
            // Therefore, NO torque is exerted about the center of mass during impact!
            // omega1 and omega2 are CONSERVED across the collision:
            // omega1 remains omega1; omega2 remains whatever it was (0 if stationary).

            // Separate overlapping spheres
            const overlap = 2 * R - dist;
            b1.x -= nx * (overlap / 2 + 0.5);
            b1.y -= ny * (overlap / 2 + 0.5);
            b2.x += nx * (overlap / 2 + 0.5);
            b2.y += ny * (overlap / 2 + 0.5);

            setCollisionOccurred(true);
          }
        }
      }

      // -------------------------------------------------------------
      // 3. RENDER BILLIARD TABLE FELT, CUSHIONS & POCKETS
      // -------------------------------------------------------------
      ctx.clearRect(0, 0, W, H);

      // Outer Wood Rails
      ctx.fillStyle = '#21150c';
      ctx.fillRect(0, 0, W, H);

      // Inner Slate Table Felt
      const railSize = 16;
      ctx.fillStyle = '#0f3e24'; // Lush Championship Green Felt
      ctx.fillRect(railSize, railSize, W - 2 * railSize, H - 2 * railSize);

      // Subtle table cloth texture grid
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = railSize; x < W - railSize; x += 40) {
        ctx.moveTo(x, railSize);
        ctx.lineTo(x, H - railSize);
      }
      for (let y = railSize; y < H - railSize; y += 40) {
        ctx.moveTo(railSize, y);
        ctx.lineTo(W - railSize, y);
      }
      ctx.stroke();

      // Table Pockets (6 pockets)
      const pocketR = 18;
      const pockets = [
        { x: railSize, y: railSize },
        { x: W / 2, y: railSize },
        { x: W - railSize, y: railSize },
        { x: railSize, y: H - railSize },
        { x: W / 2, y: H - railSize },
        { x: W - railSize, y: H - railSize },
      ];
      ctx.fillStyle = '#080808';
      pockets.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, pocketR, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#3a2717';
        ctx.lineWidth = 3;
        ctx.stroke();
      });

      // Aim Line (Before Strike)
      if (!tableRef.current.hasStruck) {
        const rad = (aimAngleDeg * Math.PI) / 180;
        const lineLen = 320;
        ctx.strokeStyle = 'rgba(229, 184, 92, 0.5)';
        ctx.setLineDash([6, 6]);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(b1.x, b1.y);
        ctx.lineTo(b1.x + Math.cos(rad) * lineLen, b1.y + Math.sin(rad) * lineLen);
        ctx.stroke();
        ctx.setLineDash([]);

        // Cue Stick Graphic
        const cueOffset = cueStriking ? 10 : 38;
        const cueStartX = b1.x - Math.cos(rad) * cueOffset;
        const cueStartY = b1.y - Math.sin(rad) * cueOffset;
        const cueEndX = b1.x - Math.cos(rad) * (cueOffset + 140);
        const cueEndY = b1.y - Math.sin(rad) * (cueOffset + 140);

        ctx.strokeStyle = '#d79b64';
        ctx.lineWidth = 5;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(cueStartX, cueStartY);
        ctx.lineTo(cueEndX, cueEndY);
        ctx.stroke();

        // Chalk Tip
        ctx.strokeStyle = '#66d9ef';
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.moveTo(cueStartX, cueStartY);
        ctx.lineTo(cueStartX - Math.cos(rad) * 6, cueStartY - Math.sin(rad) * 6);
        ctx.stroke();
      }

      // -------------------------------------------------------------
      // 4. RENDER BALLS, VECTORS & ROTATIONAL SPIN
      // -------------------------------------------------------------
      [b2, b1].forEach((ball, idx) => {
        const isCue = idx === 1;

        // Ball Shadow
        ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
        ctx.beginPath();
        ctx.ellipse(ball.x + 3, ball.y + 4, R, R * 0.85, 0, 0, Math.PI * 2);
        ctx.fill();

        // Ball Body
        const grad = ctx.createRadialGradient(
          ball.x - R * 0.35, ball.y - R * 0.35, R * 0.1,
          ball.x, ball.y, R
        );
        if (isCue) {
          grad.addColorStop(0, '#ffffff');
          grad.addColorStop(0.75, '#e5e3db');
          grad.addColorStop(1, '#9b998f');
        } else {
          grad.addColorStop(0, '#ffe885');
          grad.addColorStop(0.75, '#e5b85c');
          grad.addColorStop(1, '#8f6515');
        }

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(ball.x, ball.y, R, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'rgba(0,0,0,0.4)';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Internal Orientation Markers (Spin Dots rotating with theta)
        const dotR = 3.5;
        const distFromCenter = R * 0.55;
        ctx.fillStyle = isCue ? '#f92672' : '#141414';
        for (let a = 0; a < 4; a++) {
          const dotAngle = ball.theta + (a * Math.PI) / 2;
          const dxDot = ball.x + Math.cos(dotAngle) * distFromCenter;
          const dyDot = ball.y + Math.sin(dotAngle) * distFromCenter;
          ctx.beginPath();
          ctx.arc(dxDot, dyDot, dotR, 0, Math.PI * 2);
          ctx.fill();
        }

        // Center Indicator
        ctx.fillStyle = '#000000';
        ctx.beginPath();
        ctx.arc(ball.x, ball.y, 2, 0, Math.PI * 2);
        ctx.fill();

        // -----------------------------------------------------------
        // VECTORS OVERLAY
        // -----------------------------------------------------------
        const v = Math.sqrt(ball.vx * ball.vx + ball.vy * ball.vy);

        if (showVectors && v > 0.5) {
          // 1. Linear Velocity Vector (Cyan)
          const scaleV = 0.35;
          const vxEnd = ball.x + ball.vx * scaleV;
          const vyEnd = ball.y + ball.vy * scaleV;
          
          ctx.strokeStyle = theme.accentCyan;
          ctx.fillStyle = theme.accentCyan;
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.moveTo(ball.x, ball.y);
          ctx.lineTo(vxEnd, vyEnd);
          ctx.stroke();

          // Arrowhead
          const angle = Math.atan2(ball.vy, ball.vx);
          ctx.beginPath();
          ctx.moveTo(vxEnd, vyEnd);
          ctx.lineTo(vxEnd - 8 * Math.cos(angle - Math.PI / 6), vyEnd - 8 * Math.sin(angle - Math.PI / 6));
          ctx.lineTo(vxEnd - 8 * Math.cos(angle + Math.PI / 6), vyEnd - 8 * Math.sin(angle + Math.PI / 6));
          ctx.closePath();
          ctx.fill();
        }

        // 2. Spin Rate Ring Overlay (Gold)
        if (showSpinRing && Math.abs(ball.omega) > 0.05) {
          ctx.strokeStyle = ball.omega > 0 ? theme.accentGold : theme.accentPink;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(ball.x, ball.y, R + 6, 0, Math.PI * 2);
          ctx.stroke();

          // Spin Direction Arc
          const spinArrowAngle = ball.theta + Math.PI / 4;
          const ax = ball.x + Math.cos(spinArrowAngle) * (R + 6);
          const ay = ball.y + Math.sin(spinArrowAngle) * (R + 6);
          ctx.fillStyle = ball.omega > 0 ? theme.accentGold : theme.accentPink;
          ctx.beginPath();
          ctx.arc(ax, ay, 3.5, 0, Math.PI * 2);
          ctx.fill();
        }

        // 3. Dynamic Friction Vector (Crimson/Pink)
        if (showFriction && isRunning) {
          const v_contact = v - R * ball.omega;
          if (Math.abs(v_contact) > 1.5 && v > 0.5) {
            const dirX = ball.vx / v;
            const dirY = ball.vy / v;
            const fk_dir = v_contact > 0 ? -1 : 1;
            const fEndX = ball.x + dirX * fk_dir * 35;
            const fEndY = ball.y + dirY * fk_dir * 35;

            ctx.strokeStyle = theme.accentPink;
            ctx.fillStyle = theme.accentPink;
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.moveTo(ball.x, ball.y + R);
            ctx.lineTo(fEndX, fEndY + R);
            ctx.stroke();

            // Label
            ctx.font = '10px "JetBrains Mono", monospace';
            ctx.fillText(fk_dir > 0 ? 'f_k (forward)' : 'f_k (backward)', fEndX - 20, fEndY + R + 14);
          }
        }
      });

      // Update HUD telemetry
      const b1_speed = Math.sqrt(b1.vx * b1.vx + b1.vy * b1.vy);
      const b2_speed = Math.sqrt(b2.vx * b2.vx + b2.vy * b2.vy);
      const b1_v_contact = b1_speed - R * b1.omega;
      let stateBadge = 'At Rest';
      if (b1_speed > 0.5) {
        if (Math.abs(b1_v_contact) <= 1.5) {
          stateBadge = 'PURE ROLLING (v = Rω)';
        } else if (b1.omega < 0 || b1_v_contact > 0) {
          stateBadge = 'SLIPPING (Backspin / Draw)';
        } else {
          stateBadge = 'SLIPPING (Topspin / Follow)';
        }
      }

      setHudData({
        b1_v: b1_speed.toFixed(1),
        b1_omega: b1.omega.toFixed(1),
        b1_state: stateBadge,
        b2_v: b2_speed.toFixed(1),
        b2_omega: b2.omega.toFixed(1),
        k_trans: (0.5 * b1.mass * b1_speed * b1_speed).toFixed(0),
        k_rot: (0.5 * (I_factor * b1.mass * R * R) * b1.omega * b1.omega).toFixed(0)
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [isRunning, strikeH, strikeSpeed, aimAngleDeg, showVectors, showFriction, showSpinRing, cueStriking]);

  return (
    <div style={{
      background: theme.bgPanel,
      border: `1px solid ${theme.border}`,
      borderRadius: 8,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      padding: 20
    }}>
      {/* Simulation Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${theme.border}`, paddingBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Target size={20} color={theme.accentGold} />
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: theme.textMain, fontFamily: theme.fontMono }}>
              Billiard Ball Collision & Rolling-Without-Slipping Virtual Lab
            </h3>
            <p style={{ fontSize: '0.8rem', color: theme.textDim }}>
              Observe cue impact height (h), skid-to-roll transition, and elastic impact angular momentum conservation.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={handleStrike}
            disabled={cueStriking || (isRunning && tableRef.current.hasStruck)}
            style={{
              background: cueStriking || (isRunning && tableRef.current.hasStruck) ? theme.bgCard : theme.accentGreen,
              color: cueStriking || (isRunning && tableRef.current.hasStruck) ? theme.textDim : '#000000',
              border: 'none',
              borderRadius: 4,
              padding: '6px 14px',
              fontFamily: theme.fontMono,
              fontSize: '0.82rem',
              fontWeight: 700,
              cursor: cueStriking || (isRunning && tableRef.current.hasStruck) ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Zap size={14} />
            <span>{cueStriking ? 'Striking...' : 'Strike Cue Ball'}</span>
          </button>
          <button
            onClick={handleResetRack}
            style={{
              background: theme.bgCard,
              border: `1px solid ${theme.border}`,
              color: theme.textDim,
              borderRadius: 4,
              padding: '6px 12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontFamily: theme.fontMono,
              fontSize: '0.82rem'
            }}
          >
            <RotateCcw size={14} />
            <span>Reset Rack</span>
          </button>
        </div>
      </div>

      {/* Canvas Viewport */}
      <div style={{
        position: 'relative',
        borderRadius: 8,
        overflow: 'hidden',
        border: `2px solid ${theme.borderContrast}`,
        boxShadow: 'inset 0 4px 20px rgba(0,0,0,0.8)'
      }}>
        <canvas
          ref={canvasRef}
          width={860}
          height={340}
          style={{ width: '100%', height: 'auto', display: 'block' }}
        />

        {/* Live HUD Overlay */}
        <div style={{
          position: 'absolute',
          top: 14,
          left: 20,
          background: 'rgba(18, 18, 18, 0.88)',
          border: `1px solid ${theme.borderActive}`,
          borderRadius: 6,
          padding: '8px 14px',
          backdropFilter: 'blur(6px)',
          fontFamily: theme.fontMono,
          fontSize: '0.74rem',
          display: 'flex',
          flexDirection: 'column',
          gap: 4
        }}>
          <div style={{ color: theme.accentGold, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Activity size={12} />
            <span>CUE BALL (M=0.165kg, R=0.0285m):</span>
          </div>
          <div>Linear Speed (v): <span style={{ color: theme.accentCyan, fontWeight: 700 }}>{hudData.b1_v} px/s</span></div>
          <div>Angular Velocity (ω): <span style={{ color: theme.accentGold, fontWeight: 700 }}>{hudData.b1_omega} rad/s</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>Motion State:</span>
            <span style={{
              color: hudData.b1_state.includes('PURE ROLLING') ? theme.accentGreen : theme.accentPink,
              fontWeight: 700,
              background: 'rgba(0,0,0,0.4)',
              padding: '1px 6px',
              borderRadius: 3
            }}>
              {hudData.b1_state}
            </span>
          </div>
          {collisionOccurred && (
            <div style={{ marginTop: 4, borderTop: `1px solid ${theme.border}`, paddingTop: 4, color: theme.accentGreen }}>
              Object Ball Speed: <strong>{hudData.b2_v} px/s</strong> (Skid-to-Roll Active)
            </div>
          )}
        </div>
      </div>

      {/* Preset Buttons Bar (The 4 Classic Pool Impacts) */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        background: theme.bgCard,
        padding: '10px 14px',
        borderRadius: 6,
        border: `1px solid ${theme.border}`
      }}>
        <span style={{ fontSize: '0.78rem', fontFamily: theme.fontMono, color: theme.accentGold, fontWeight: 700 }}>
          CLASSIC PRESETS:
        </span>
        <button
          onClick={() => applyPreset(0.4, 'sweet_spot')}
          style={{
            background: Math.abs(strikeH - 0.4) < 0.05 ? theme.accentGreen : theme.bgPanel,
            color: Math.abs(strikeH - 0.4) < 0.05 ? '#000000' : theme.textMain,
            border: `1px solid ${theme.border}`,
            padding: '4px 10px',
            borderRadius: 4,
            fontSize: '0.76rem',
            fontFamily: theme.fontMono,
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          🎯 Sweet Spot (h = +0.4R = 2/5 R) [Pure Roll Instantly]
        </button>
        <button
          onClick={() => applyPreset(0.0, 'stun')}
          style={{
            background: Math.abs(strikeH) < 0.05 ? theme.accentGold : theme.bgPanel,
            color: Math.abs(strikeH) < 0.05 ? '#000000' : theme.textMain,
            border: `1px solid ${theme.border}`,
            padding: '4px 10px',
            borderRadius: 4,
            fontSize: '0.76rem',
            fontFamily: theme.fontMono,
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          ⏹️ Stun Shot (h = 0) [No Spin, Dead Stop on Impact]
        </button>
        <button
          onClick={() => applyPreset(-0.55, 'draw')}
          style={{
            background: strikeH < -0.3 ? theme.accentPink : theme.bgPanel,
            color: strikeH < -0.3 ? '#ffffff' : theme.textMain,
            border: `1px solid ${theme.border}`,
            padding: '4px 10px',
            borderRadius: 4,
            fontSize: '0.76rem',
            fontFamily: theme.fontMono,
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          ↩️ Draw / Backspin (h = -0.55R) [Rolls Backward Post-Collision]
        </button>
        <button
          onClick={() => applyPreset(0.75, 'follow')}
          style={{
            background: strikeH > 0.6 ? theme.accentCyan : theme.bgPanel,
            color: strikeH > 0.6 ? '#000000' : theme.textMain,
            border: `1px solid ${theme.border}`,
            padding: '4px 10px',
            borderRadius: 4,
            fontSize: '0.76rem',
            fontFamily: theme.fontMono,
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          ⏩ Follow / Topspin (h = +0.75R) [Accelerates Forward]
        </button>
      </div>

      {/* Physics Controls Sliders Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: 14
      }}>
        {/* Slider 1: Impact Height h/R */}
        <div style={{ background: theme.bgCard, padding: 12, borderRadius: 6, border: `1px solid ${theme.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', fontFamily: theme.fontMono, marginBottom: 6 }}>
            <span>Strike Height (h / R):</span>
            <span style={{ color: strikeH === 0.4 ? theme.accentGreen : theme.accentGold, fontWeight: 700 }}>
              {strikeH >= 0 ? `+${strikeH.toFixed(2)} R` : `${strikeH.toFixed(2)} R`}
            </span>
          </div>
          <input
            type="range"
            min="-0.85"
            max="0.85"
            step="0.05"
            value={strikeH}
            onChange={(e) => {
              setStrikeH(parseFloat(e.target.value));
              handleResetRack();
            }}
            style={{ width: '100%', accentColor: theme.accentGold }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: theme.textMuted, marginTop: 4 }}>
            <span>-0.85R (Max Draw)</span>
            <span>0 (Center)</span>
            <span>+0.4R (Sweet Spot)</span>
            <span>+0.85R (Max Follow)</span>
          </div>
        </div>

        {/* Slider 2: Impact Velocity */}
        <div style={{ background: theme.bgCard, padding: 12, borderRadius: 6, border: `1px solid ${theme.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', fontFamily: theme.fontMono, marginBottom: 6 }}>
            <span>Cue Strike Speed (v0):</span>
            <span style={{ color: theme.accentCyan, fontWeight: 700 }}>{strikeSpeed} px/s</span>
          </div>
          <input
            type="range"
            min="100"
            max="450"
            step="10"
            value={strikeSpeed}
            onChange={(e) => setStrikeSpeed(parseInt(e.target.value))}
            style={{ width: '100%', accentColor: theme.accentCyan }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: theme.textMuted, marginTop: 4 }}>
            <span>100 (Touch)</span>
            <span>240 (Medium Break)</span>
            <span>450 (Hard Strike)</span>
          </div>
        </div>

        {/* Toggle Switches */}
        <div style={{ background: theme.bgCard, padding: 12, borderRadius: 6, border: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontSize: '0.78rem', fontFamily: theme.fontMono, color: theme.textDim, fontWeight: 700 }}>
            PHYSICAL VECTOR OVERLAYS:
          </span>
          <div style={{ display: 'flex', gap: 12, fontSize: '0.75rem', fontFamily: theme.fontMono }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: theme.accentCyan }}>
              <input type="checkbox" checked={showVectors} onChange={(e) => setShowVectors(e.target.checked)} />
              <span>Velocity (v)</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: theme.accentPink }}>
              <input type="checkbox" checked={showFriction} onChange={(e) => setShowFriction(e.target.checked)} />
              <span>Friction (fk)</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: theme.accentGold }}>
              <input type="checkbox" checked={showSpinRing} onChange={(e) => setShowSpinRing(e.target.checked)} />
              <span>Spin Rate (ω)</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
