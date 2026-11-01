import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, RotateCcw, Target, Zap, Activity, Info, Sparkles, Sliders } from 'lucide-react';
import { theme } from '../theme';

export default function BilliardSim({ config }) {
  const canvasRef = useRef(null);
  const [isRunning, setIsRunning] = useState(false);
  const [strikeH, setStrikeH] = useState(0.4); // h / R: -1.0 to +1.0 (0.4 is sweet spot)
  const [strikeSpeed, setStrikeSpeed] = useState(240); // px/s
  const [restitution, setRestitution] = useState(1.0); // e: 0.0 (inelastic) to 1.0 (elastic)
  const [impactOffset, setImpactOffset] = useState(0.0); // b / R: -1.7 to +1.7 (changes cos theta)
  const [aimAngleDeg, setAimAngleDeg] = useState(0); // degrees
  const [showVectors, setShowVectors] = useState(true);
  const [showFriction, setShowFriction] = useState(true);
  const [showSpinRing, setShowSpinRing] = useState(true);
  const [cueStriking, setCueStriking] = useState(false);
  const [collisionOccurred, setCollisionOccurred] = useState(false);
  const [energyLoss, setEnergyLoss] = useState(0);

  const R = 24; // Ball radius in px
  const baseTableY = 180;

  // React to dynamic config updates injected by AGY agent on site
  useEffect(() => {
    if (config) {
      if (typeof config.restitution === 'number') {
        setRestitution(Math.max(0, Math.min(1.0, config.restitution)));
      }
      if (typeof config.impact_offset === 'number') {
        setImpactOffset(Math.max(-1.7, Math.min(1.7, config.impact_offset)));
      }
      if (typeof config.strike_height === 'number') {
        setStrikeH(Math.max(-0.85, Math.min(0.85, config.strike_height)));
      }
      if (typeof config.strike_speed === 'number') {
        setStrikeSpeed(Math.max(100, Math.min(450, config.strike_speed)));
      }
      handleResetRack();
    }
  }, [config]);

  const [hudData, setHudData] = useState({
    b1_v: 0,
    b1_omega: 0,
    b1_state: 'Ready on Felt',
    b2_v: 0,
    b2_omega: 0,
    cos_theta: 1.0,
    theta_deg: 0,
    k_initial: 0,
    k_current: 0,
    k_loss: 0
  });

  const tableRef = useRef({
    b1: { x: 180, y: baseTableY, vx: 0, vy: 0, omega: 0, theta: 0, mass: 1.0, color: '#fdfbf7', name: 'Cue Ball' },
    b2: { x: 520, y: baseTableY + impactOffset * R, vx: 0, vy: 0, omega: 0, theta: 0, mass: 1.0, color: '#e5b85c', name: 'Object Ball (#1)' },
    cueAnim: 0,
    hasStruck: false,
    lastTime: null,
    k_before_impact: 0
  });

  const mu_k = 0.28; // Kinetic friction coefficient with cloth
  const g = 600; // Scaled gravity for responsive physics
  const I_factor = 0.4; // 2/5 for solid sphere

  // Calculate collision geometry
  const b_scaled = impactOffset * R;
  const sin_theta = Math.max(-0.95, Math.min(0.95, b_scaled / (2 * R)));
  const cos_theta = Math.sqrt(Math.max(0, 1 - sin_theta * sin_theta));
  const collisionAngleDeg = (Math.asin(sin_theta) * 180 / Math.PI).toFixed(1);

  const handleResetRack = () => {
    tableRef.current.b1 = { x: 180, y: baseTableY, vx: 0, vy: 0, omega: 0, theta: 0, mass: 1.0, color: '#fdfbf7', name: 'Cue Ball' };
    tableRef.current.b2 = { x: 520, y: baseTableY + impactOffset * R, vx: 0, vy: 0, omega: 0, theta: 0, mass: 1.0, color: '#e5b85c', name: 'Object Ball (#1)' };
    tableRef.current.cueAnim = 0;
    tableRef.current.hasStruck = false;
    tableRef.current.lastTime = null;
    tableRef.current.k_before_impact = 0;
    setIsRunning(false);
    setCueStriking(false);
    setCollisionOccurred(false);
    setEnergyLoss(0);
    setHudData(prev => ({
      ...prev,
      b1_v: 0,
      b1_omega: 0,
      b1_state: 'Ready on Felt',
      b2_v: 0,
      b2_omega: 0,
      cos_theta: cos_theta.toFixed(3),
      theta_deg: collisionAngleDeg,
      k_loss: 0
    }));
  };

  // Update object ball position when offset changes
  useEffect(() => {
    if (!isRunning && !tableRef.current.hasStruck) {
      tableRef.current.b2.y = baseTableY + impactOffset * R;
    }
  }, [impactOffset]);

  const handleStrike = () => {
    if (isRunning && tableRef.current.hasStruck) return;
    setCueStriking(true);
    let animProgress = 0;
    
    const cueInterval = setInterval(() => {
      animProgress += 0.15;
      if (animProgress >= 1.0) {
        clearInterval(cueInterval);
        setCueStriking(false);
        const rad = (aimAngleDeg * Math.PI) / 180;
        const v0 = strikeSpeed;
        const b1 = tableRef.current.b1;
        b1.vx = v0 * Math.cos(rad);
        b1.vy = v0 * Math.sin(rad);
        b1.omega = (2.5 * strikeH * v0) / R;
        tableRef.current.hasStruck = true;
        setIsRunning(true);
      }
    }, 20);
  };

  const applyRestitutionPreset = (eVal) => {
    setRestitution(eVal);
    handleResetRack();
  };

  const applyOffsetPreset = (offsetVal) => {
    setImpactOffset(offsetVal);
    handleResetRack();
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
          const v_contact = v - R * ball.omega;

          if (Math.abs(v_contact) > 1.5) {
            const fk_dir = v_contact > 0 ? -1 : 1;
            const dv = fk_dir * (mu_k * g) * dt;
            const newV = Math.max(0, v + dv);
            ball.vx = newV * dirX;
            ball.vy = newV * dirY;
            const d_omega = -fk_dir * (2.5 * mu_k * g / R) * dt;
            ball.omega += d_omega;
          } else {
            const rollDecel = 28 * dt;
            const newV = Math.max(0, v - rollDecel);
            ball.vx = newV * dirX;
            ball.vy = newV * dirY;
            ball.omega = newV / R;
          }

          ball.x += ball.vx * dt;
          ball.y += ball.vy * dt;
          ball.theta += ball.omega * dt;

          const pad = R + 18;
          if (ball.x < pad) { ball.x = pad; ball.vx = -ball.vx * 0.75; }
          if (ball.x > W - pad) { ball.x = W - pad; ball.vx = -ball.vx * 0.75; }
          if (ball.y < pad) { ball.y = pad; ball.vy = -ball.vy * 0.75; }
          if (ball.y > H - pad) { ball.y = H - pad; ball.vy = -ball.vy * 0.75; }
        });

        // -------------------------------------------------------------
        // 2. 2D COLLISION WITH DYNAMIC RESTITUTION (e) & ANGLE (cos theta)
        // -------------------------------------------------------------
        const dx = b2.x - b1.x;
        const dy = b2.y - b1.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist <= 2 * R && dist > 0.001) {
          const nx = dx / dist;
          const ny = dy / dist;
          const tx = -ny;
          const ty = nx;

          const v1n = b1.vx * nx + b1.vy * ny;
          const v1t = b1.vx * tx + b1.vy * ty;
          const v2n = b2.vx * nx + b2.vy * ny;
          const v2t = b2.vx * tx + b2.vy * ty;

          const v_rel_n = v1n - v2n;
          if (v_rel_n > 0) {
            // Compute Initial Kinetic Energy before impact
            const k1_before = 0.5 * b1.mass * (b1.vx * b1.vx + b1.vy * b1.vy);
            const k2_before = 0.5 * b2.mass * (b2.vx * b2.vx + b2.vy * b2.vy);
            const k_total_before = k1_before + k2_before;

            // 1D Normal Collision Formula with Restitution e:
            // v1n' = [(m1 - e*m2)v1n + (1+e)m2*v2n] / (m1 + m2)
            // v2n' = [(1+e)m1*v1n + (m2 - e*m1)v2n] / (m1 + m2)
            const m1 = b1.mass;
            const m2 = b2.mass;
            const m_sum = m1 + m2;

            const e = restitution;
            const v1n_after = ((m1 - e * m2) * v1n + (1 + e) * m2 * v2n) / m_sum;
            const v2n_after = ((1 + e) * m1 * v1n + (m2 - e * m1) * v2n) / m_sum;

            b1.vx = v1n_after * nx + v1t * tx;
            b1.vy = v1n_after * ny + v1t * ty;
            b2.vx = v2n_after * nx + v2t * tx;
            b2.vy = v2n_after * ny + v2t * ty;

            // Calculate Energy Dissipation
            const k1_after = 0.5 * b1.mass * (b1.vx * b1.vx + b1.vy * b1.vy);
            const k2_after = 0.5 * b2.mass * (b2.vx * b2.vx + b2.vy * b2.vy);
            const k_total_after = k1_after + k2_after;
            const dissipated = Math.max(0, k_total_before - k_total_after);
            setEnergyLoss(dissipated);

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
      // 3. RENDER FELT, CUSHIONS, POCKETS & IMPACT LINE
      // -------------------------------------------------------------
      ctx.clearRect(0, 0, W, H);

      // Wood Rail
      ctx.fillStyle = '#21150c';
      ctx.fillRect(0, 0, W, H);

      // Table Felt
      const railSize = 16;
      ctx.fillStyle = '#0f3e24';
      ctx.fillRect(railSize, railSize, W - 2 * railSize, H - 2 * railSize);

      // Table Cloth Grid
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

      // Pockets
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

      // Aim Line & Collision Impact Geometry Visualizer
      if (!tableRef.current.hasStruck) {
        // Aim Ray
        const rad = (aimAngleDeg * Math.PI) / 180;
        ctx.strokeStyle = 'rgba(229, 184, 92, 0.5)';
        ctx.setLineDash([5, 5]);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(b1.x, b1.y);
        ctx.lineTo(b2.x, b1.y);
        ctx.stroke();

        // Line of centers normal vector
        ctx.strokeStyle = 'rgba(102, 217, 239, 0.6)';
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(b1.x, b1.y);
        ctx.lineTo(b2.x, b2.y);
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

        ctx.strokeStyle = '#66d9ef';
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.moveTo(cueStartX, cueStartY);
        ctx.lineTo(cueStartX - Math.cos(rad) * 6, cueStartY - Math.sin(rad) * 6);
        ctx.stroke();
      }

      // -------------------------------------------------------------
      // 4. RENDER BALLS & ROTATIONAL SPIN
      // -------------------------------------------------------------
      [b2, b1].forEach((ball, idx) => {
        const isCue = idx === 1;

        ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
        ctx.beginPath();
        ctx.ellipse(ball.x + 3, ball.y + 4, R, R * 0.85, 0, 0, Math.PI * 2);
        ctx.fill();

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

        // Orientation Spin Dots
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

        ctx.fillStyle = '#000000';
        ctx.beginPath();
        ctx.arc(ball.x, ball.y, 2, 0, Math.PI * 2);
        ctx.fill();

        // Vectors
        const v = Math.sqrt(ball.vx * ball.vx + ball.vy * ball.vy);
        if (showVectors && v > 0.5) {
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

          const angle = Math.atan2(ball.vy, ball.vx);
          ctx.beginPath();
          ctx.moveTo(vxEnd, vyEnd);
          ctx.lineTo(vxEnd - 8 * Math.cos(angle - Math.PI / 6), vyEnd - 8 * Math.sin(angle - Math.PI / 6));
          ctx.lineTo(vxEnd - 8 * Math.cos(angle + Math.PI / 6), vyEnd - 8 * Math.sin(angle + Math.PI / 6));
          ctx.closePath();
          ctx.fill();
        }

        if (showSpinRing && Math.abs(ball.omega) > 0.05) {
          ctx.strokeStyle = ball.omega > 0 ? theme.accentGold : theme.accentPink;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(ball.x, ball.y, R + 6, 0, Math.PI * 2);
          ctx.stroke();
        }

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
        cos_theta: cos_theta.toFixed(3),
        theta_deg: collisionAngleDeg,
        k_loss: energyLoss.toFixed(0)
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [isRunning, strikeH, strikeSpeed, restitution, impactOffset, aimAngleDeg, showVectors, showFriction, showSpinRing, cueStriking, energyLoss]);

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
              Billiard Collisions & Restitution (e) Lab
            </h3>
            <p style={{ fontSize: '0.8rem', color: theme.textDim }}>
              Control restitution coefficient (e), collision normal geometry (cos θ), and impulsive spin.
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
            <span>COLLISION DYNAMICS TELEMETRY:</span>
          </div>
          <div>Restitution (e): <span style={{ color: theme.accentGreen, fontWeight: 700 }}>{restitution.toFixed(2)}</span> ({restitution === 1 ? 'Elastic' : restitution === 0 ? 'Totally Inelastic' : 'Inelastic'})</div>
          <div>Collision Angle (θ): <span style={{ color: theme.accentCyan, fontWeight: 700 }}>{hudData.theta_deg}°</span> (cos θ = <strong style={{ color: theme.accentGold }}>{hudData.cos_theta}</strong>)</div>
          <div>Cue Ball Speed (v1): <span style={{ color: theme.accentCyan, fontWeight: 700 }}>{hudData.b1_v} px/s</span></div>
          <div>Object Ball Speed (v2): <span style={{ color: theme.accentGold, fontWeight: 700 }}>{hudData.b2_v} px/s</span></div>
          {collisionOccurred && restitution < 1.0 && (
            <div style={{ marginTop: 2, borderTop: `1px solid ${theme.border}`, paddingTop: 3, color: theme.accentPink }}>
              Energy Dissipated (ΔK): <strong>{hudData.k_loss} J</strong>
            </div>
          )}
        </div>
      </div>

      {/* Preset Control Buttons Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Restitution (e) Presets */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: theme.bgCard,
          padding: '8px 12px',
          borderRadius: 6,
          border: `1px solid ${theme.border}`,
          flexWrap: 'wrap'
        }}>
          <span style={{ fontSize: '0.76rem', fontFamily: theme.fontMono, color: theme.accentGreen, fontWeight: 700 }}>
            RESTITUTION (e):
          </span>
          <button
            onClick={() => applyRestitutionPreset(1.0)}
            style={{
              background: restitution === 1.0 ? theme.accentGreen : theme.bgPanel,
              color: restitution === 1.0 ? '#000000' : theme.textMain,
              border: `1px solid ${theme.border}`,
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            e = 1.0 (Elastic)
          </button>
          <button
            onClick={() => applyRestitutionPreset(0.92)}
            style={{
              background: restitution === 0.92 ? theme.accentGold : theme.bgPanel,
              color: restitution === 0.92 ? '#000000' : theme.textMain,
              border: `1px solid ${theme.border}`,
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            e = 0.92 (Billiard Resin)
          </button>
          <button
            onClick={() => applyRestitutionPreset(0.50)}
            style={{
              background: restitution === 0.50 ? theme.accentPink : theme.bgPanel,
              color: restitution === 0.50 ? '#ffffff' : theme.textMain,
              border: `1px solid ${theme.border}`,
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            e = 0.50 (Soft Inelastic)
          </button>
          <button
            onClick={() => applyRestitutionPreset(0.0)}
            style={{
              background: restitution === 0.0 ? '#e06c75' : theme.bgPanel,
              color: restitution === 0.0 ? '#000000' : theme.textMain,
              border: `1px solid ${theme.border}`,
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            e = 0.0 (Stick Together)
          </button>
        </div>

        {/* Collision Angle / Impact Offset Presets */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: theme.bgCard,
          padding: '8px 12px',
          borderRadius: 6,
          border: `1px solid ${theme.border}`,
          flexWrap: 'wrap'
        }}>
          <span style={{ fontSize: '0.76rem', fontFamily: theme.fontMono, color: theme.accentGold, fontWeight: 700 }}>
            COLLISION COS(θ) PRESETS:
          </span>
          <button
            onClick={() => applyOffsetPreset(0.0)}
            style={{
              background: impactOffset === 0 ? theme.accentGold : theme.bgPanel,
              color: impactOffset === 0 ? '#000000' : theme.textMain,
              border: `1px solid ${theme.border}`,
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            cos θ = 1.00 (Head-on, 0°)
          </button>
          <button
            onClick={() => applyOffsetPreset(1.0)}
            style={{
              background: Math.abs(impactOffset - 1.0) < 0.1 ? theme.accentCyan : theme.bgPanel,
              color: Math.abs(impactOffset - 1.0) < 0.1 ? '#000000' : theme.textMain,
              border: `1px solid ${theme.border}`,
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            cos θ = 0.866 (30° Cut)
          </button>
          <button
            onClick={() => applyOffsetPreset(1.41)}
            style={{
              background: Math.abs(impactOffset - 1.41) < 0.1 ? theme.accentGreen : theme.bgPanel,
              color: Math.abs(impactOffset - 1.41) < 0.1 ? '#000000' : theme.textMain,
              border: `1px solid ${theme.border}`,
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            cos θ = 0.707 (45° Cut)
          </button>
          <button
            onClick={() => applyOffsetPreset(1.73)}
            style={{
              background: Math.abs(impactOffset - 1.73) < 0.1 ? theme.accentPink : theme.bgPanel,
              color: Math.abs(impactOffset - 1.73) < 0.1 ? '#ffffff' : theme.textMain,
              border: `1px solid ${theme.border}`,
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: '0.74rem',
              fontFamily: theme.fontMono,
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            cos θ = 0.500 (60° Thin Cut)
          </button>
        </div>
      </div>

      {/* Dynamic Sliders Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: 12
      }}>
        {/* Slider 1: Coefficient of Restitution e */}
        <div style={{ background: theme.bgCard, padding: 12, borderRadius: 6, border: `1px solid ${theme.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', fontFamily: theme.fontMono, marginBottom: 6 }}>
            <span>Restitution Coefficient (e):</span>
            <span style={{ color: theme.accentGreen, fontWeight: 700 }}>{restitution.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min="0.0"
            max="1.0"
            step="0.05"
            value={restitution}
            onChange={(e) => {
              setRestitution(parseFloat(e.target.value));
              handleResetRack();
            }}
            style={{ width: '100%', accentColor: theme.accentGreen }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: theme.textMuted, marginTop: 4 }}>
            <span>0.0 (Inelastic)</span>
            <span>0.5</span>
            <span>1.0 (Elastic)</span>
          </div>
        </div>

        {/* Slider 2: Impact Parameter / cos theta */}
        <div style={{ background: theme.bgCard, padding: 12, borderRadius: 6, border: `1px solid ${theme.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', fontFamily: theme.fontMono, marginBottom: 6 }}>
            <span>Collision Angle cos(θ):</span>
            <span style={{ color: theme.accentGold, fontWeight: 700 }}>{hudData.cos_theta} ({hudData.theta_deg}°)</span>
          </div>
          <input
            type="range"
            min="-1.7"
            max="1.7"
            step="0.05"
            value={impactOffset}
            onChange={(e) => {
              setImpactOffset(parseFloat(e.target.value));
              handleResetRack();
            }}
            style={{ width: '100%', accentColor: theme.accentGold }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: theme.textMuted, marginTop: 4 }}>
            <span>-60°</span>
            <span>Head-on (cos θ = 1)</span>
            <span>+60°</span>
          </div>
        </div>

        {/* Slider 3: Cue Strike Height h/R */}
        <div style={{ background: theme.bgCard, padding: 12, borderRadius: 6, border: `1px solid ${theme.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', fontFamily: theme.fontMono, marginBottom: 6 }}>
            <span>Cue Height (h / R):</span>
            <span style={{ color: strikeH === 0.4 ? theme.accentGreen : theme.accentCyan, fontWeight: 700 }}>
              {strikeH >= 0 ? `+${strikeH.toFixed(2)}R` : `${strikeH.toFixed(2)}R`}
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
            style={{ width: '100%', accentColor: theme.accentCyan }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: theme.textMuted, marginTop: 4 }}>
            <span>Draw (h &lt; 0)</span>
            <span>Center (0)</span>
            <span>Sweet (0.4R)</span>
            <span>Follow</span>
          </div>
        </div>
      </div>
    </div>
  );
}
