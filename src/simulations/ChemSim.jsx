import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Play, Pause, RotateCcw, Activity, FlaskConical, Sliders, Info, Zap, Gauge } from 'lucide-react';
import { theme, canvasPalette } from '../theme';

// ---------------------------------------------------------------------------
// Chemistry Simulation Kit (SimSpec kind "chem")
// High-fidelity benchtop apparatus and molecular kinetics engine.
// Implements: titration, gas_law, kinetics, equilibrium, energy_diagram, decay.
// ---------------------------------------------------------------------------

function solvePh(pKa, Va, Ca, Cb, Vb, isStrong = false) {
  const Kw = 1.0e-14;
  const Vtot = Va + Vb;
  if (Vtot <= 0) return 7.0;
  const cNa = (Cb * Vb) / Vtot;
  const cATot = (Ca * Va) / Vtot;

  let pkas = [];
  if (Array.isArray(pKa)) {
    pkas = pKa.map(Number);
  } else if (typeof pKa === 'number') {
    pkas = [pKa];
  } else {
    pkas = [Number(pKa) || 4.75];
  }

  const f = (logH) => {
    const h = Math.pow(10, logH);
    const oh = Kw / h;
    if (isStrong) {
      return h - oh + cNa - cATot * pkas.length;
    }
    const n = pkas.length;
    const Kas = pkas.map((pk) => Math.pow(10, -pk));
    const terms = new Array(n + 1).fill(1.0);
    let prodKa = 1.0;
    for (let k = 1; k <= n; k++) {
      prodKa *= Kas[k - 1];
      terms[k] = Math.pow(h, n - k) * prodKa;
    }
    terms[0] = Math.pow(h, n);
    const d = terms.reduce((acc, v) => acc + v, 0);
    let sumCharge = 0;
    for (let k = 1; k <= n; k++) {
      sumCharge += k * terms[k];
    }
    const aCharge = d > 0 ? (cATot * sumCharge) / d : 0;
    return h - oh + cNa - aCharge;
  };

  let lo = -14.0, hi = 1.0;
  for (let i = 0; i < 70; i++) {
    const mid = (lo + hi) / 2;
    if (f(mid) < 0) lo = mid;
    else hi = mid;
  }
  return -((lo + hi) / 2);
}

// 2D Maxwell-Boltzmann thermal velocity sampler via Box-Muller transform
function sampleMaxwellBoltzmann(T, mass = 1) {
  const sigma = Math.sqrt((8.314 * Math.max(50, T)) / (mass * 1000)) * 26;
  const u1 = Math.max(1e-7, Math.random());
  const u2 = Math.random();
  const mag = Math.sqrt(-2.0 * Math.log(u1));
  const z0 = mag * Math.cos(2.0 * Math.PI * u2);
  const z1 = mag * Math.sin(2.0 * Math.PI * u2);
  return { vx: z0 * sigma, vy: z1 * sigma };
}

export default function ChemSim({ spec }) {
  if (!spec || !spec.widget) {
    return (
      <div className="panel" style={{ padding: 24, textAlign: 'center', color: theme.textMuted }}>
        No chemistry simulation widget specified.
      </div>
    );
  }
  return <ChemWidget key={JSON.stringify([spec.widget, spec.params])} spec={spec} />;
}

function ChemWidget({ spec }) {
  // Initialize parameters from spec.params
  const initialParams = useMemo(() => {
    const p = {};
    for (const item of (spec.params || [])) {
      p[item.name] = Number(item.value ?? item.default ?? item.min ?? 0);
    }
    return p;
  }, [spec]);

  const [params, setParams] = useState(initialParams);
  const [isRunning, setIsRunning] = useState(false);
  const simTimeRef = useRef(0);
  const titrantAnimRef = useRef(initialParams.Vb ?? 0);

  const canvasRef = useRef(null);
  const lastTimeRef = useRef(null);

  // Benchtop animation state refs
  const dropletsRef = useRef([]);
  const ripplesRef = useRef([]);
  const flashesRef = useRef([]);
  const stirAngleRef = useRef(0);
  const impulseRef = useRef({ accumulator: 0, windowTime: 0, smoothedP: 0 });
  const particlesRef = useRef([]);
  const kineticsParticlesRef = useRef([]);

  useEffect(() => {
    setParams(initialParams);
    titrantAnimRef.current = initialParams.Vb ?? 0;
    simTimeRef.current = 0;
    setIsRunning(false);
  }, [initialParams]);

  const handleParamChange = (name, val) => {
    const num = Number(val);
    if (name === 'Vb') {
      titrantAnimRef.current = num;
    }
    setParams(prev => ({ ...prev, [name]: num }));
  };

  const handleReset = () => {
    setParams(initialParams);
    titrantAnimRef.current = initialParams.Vb ?? 0;
    simTimeRef.current = 0;
    setIsRunning(false);
    lastTimeRef.current = null;
    dropletsRef.current = [];
    ripplesRef.current = [];
    flashesRef.current = [];
    stirAngleRef.current = 0;
    impulseRef.current = { accumulator: 0, windowTime: 0, smoothedP: 0 };
    initParticles();
  };

  // Initialize stochastic/physical particles
  const initParticles = useCallback(() => {
    if (spec.widget === 'gas_law') {
      const count = Math.round((params.n || 1) * 40);
      const pts = [];
      const T = params.T ?? 300;
      const boxX = 40, boxY = 60, boxH = 260;
      const V = params.V ?? 15.0;
      const curW = Math.max(90, (V / 30.0) * 360);
      for (let i = 0; i < count; i++) {
        const vel = sampleMaxwellBoltzmann(T, 1.0);
        pts.push({
          x: boxX + 12 + Math.random() * (curW - 24),
          y: boxY + 12 + Math.random() * (boxH - 24),
          vx: vel.vx,
          vy: vel.vy,
          r: 3.5,
          mass: 1.0
        });
      }
      particlesRef.current = pts;
    } else if (spec.widget === 'kinetics') {
      const count = 38;
      const pts = [];
      const T = 300;
      for (let i = 0; i < count; i++) {
        const vel = sampleMaxwellBoltzmann(T, 1.0);
        pts.push({
          relX: 0.08 + Math.random() * 0.84,
          relY: 0.10 + Math.random() * 0.80,
          initialized: false,
          x: 0,
          y: 0,
          vx: vel.vx * 0.7,
          vy: vel.vy * 0.7,
          species: i < 30 ? 'A' : 'B',
          r: 4.5
        });
      }
      kineticsParticlesRef.current = pts;
    } else if (spec.widget === 'decay') {
      const count = Math.round(params.N0 || 100);
      const pts = [];
      for (let i = 0; i < count; i++) {
        pts.push({ decayed: false, decayTime: null });
      }
      particlesRef.current = pts;
    }
  }, [spec.widget, params.n, params.T, params.V, params.N0, params.Ea]);

  useEffect(() => {
    initParticles();
  }, [initParticles]);

  // Main simulation render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId;

    const render = (now) => {
      if (!lastTimeRef.current) lastTimeRef.current = now;
      const dt = Math.min((now - lastTimeRef.current) / 1000, 0.05);
      lastTimeRef.current = now;

      if (isRunning) {
        simTimeRef.current += dt;
        stirAngleRef.current += dt * 14.0;
      }

      const pal = canvasPalette();
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const W = rect.width;
      const H = rect.height;

      if (canvas.width !== Math.floor(W * dpr) || canvas.height !== Math.floor(H * dpr)) {
        canvas.width = Math.floor(W * dpr);
        canvas.height = Math.floor(H * dpr);
      }

      ctx.save();
      ctx.scale(dpr, dpr);

      // Background
      ctx.fillStyle = pal.surface || '#121212';
      ctx.fillRect(0, 0, W, H);

      const widget = spec.widget;

      // -------------------------------------------------------------
      // 1. TITRATION: Full Benchtop Glassware Apparatus
      // -------------------------------------------------------------
      if (widget === 'titration') {
        const pKa = params.pKa ?? 4.75;
        const Va = params.Va ?? 25.0;
        const Ca = params.Ca ?? 0.1;
        const Cb = params.Cb ?? 0.1;
        let VbCur = titrantAnimRef.current;
        const isStrong = Boolean(spec.strong);

        const Veq = (Ca * Va) / Cb;
        const VbMax = Math.max(60, Veq * 2.2);

        // Advance titrant volume automatically while running
        if (isRunning && VbCur < VbMax) {
          VbCur = Math.min(VbMax, VbCur + dt * 2.0);
          titrantAnimRef.current = VbCur;
        }

        const curPh = solvePh(pKa, Va, Ca, Cb, VbCur, isStrong);

        // Layout: Split Left (Titration Strip Chart) vs Right (Benchtop Glassware)
        const splitX = Math.floor(W * 0.44);

        // --- LEFT PANE: Titration Curve Strip Chart ---
        const margin = { top: 32, right: 24, bottom: 45, left: 45 };
        const gW = splitX - margin.left - margin.right;
        const gH = H - margin.top - margin.bottom;

        const toX = (v) => margin.left + (v / VbMax) * gW;
        const toY = (ph) => margin.top + gH - (ph / 14.0) * gH;

        // Chart box & grid
        ctx.strokeStyle = pal.rule || '#282828';
        ctx.lineWidth = 1;
        ctx.strokeRect(margin.left, margin.top, gW, gH);

        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillStyle = pal.muted || '#777';
        ctx.textAlign = 'center';

        for (let v = 0; v <= VbMax; v += 10) {
          const px = toX(v);
          ctx.beginPath();
          ctx.moveTo(px, margin.top);
          ctx.lineTo(px, margin.top + gH);
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
          ctx.stroke();
          ctx.fillText(`${v}`, px, margin.top + gH + 16);
        }
        ctx.fillText('Titrant Added Vb (mL)', margin.left + gW / 2, margin.top + gH + 34);

        ctx.textAlign = 'right';
        for (let ph = 0; ph <= 14; ph += 2) {
          const py = toY(ph);
          ctx.beginPath();
          ctx.moveTo(margin.left, py);
          ctx.lineTo(margin.left + gW, py);
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
          ctx.stroke();
          ctx.fillText(`${ph}`, margin.left - 6, py + 3);
        }

        // Plot titration curve
        ctx.strokeStyle = '#2ecc71';
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        for (let v = 0; v <= VbMax; v += 0.5) {
          const ph = solvePh(pKa, Va, Ca, Cb, v, isStrong);
          const px = toX(v);
          const py = toY(ph);
          if (v === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.stroke();

        // Equivalence point & Half-equivalence
        const phEq = solvePh(pKa, Va, Ca, Cb, Veq, isStrong);
        ctx.fillStyle = '#f92672';
        ctx.beginPath();
        ctx.arc(toX(Veq), toY(phEq), 4.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = pal.ink || '#fff';
        ctx.font = '9px "JetBrains Mono", monospace';
        ctx.fillText(`Equiv (${phEq.toFixed(1)})`, toX(Veq) - 8, toY(phEq) - 8);

        if (!isStrong) {
          const Vhalf = Veq / 2;
          const phHalf = solvePh(pKa, Va, Ca, Cb, Vhalf, isStrong);
          ctx.fillStyle = '#e5b85c';
          ctx.beginPath();
          ctx.arc(toX(Vhalf), toY(phHalf), 3.5, 0, Math.PI * 2);
          ctx.fill();
        }

        // Current point indicator
        ctx.fillStyle = '#66d9ef';
        ctx.beginPath();
        ctx.arc(toX(VbCur), toY(curPh), 5.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // --- RIGHT PANE: Full Benchtop Glassware Apparatus ---
        const benchX = splitX + 16;
        const benchW = W - benchX - 16;

        // Divider
        ctx.strokeStyle = pal.rule || '#282828';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(splitX, 10);
        ctx.lineTo(splitX, H - 10);
        ctx.stroke();

        // Retort Stand Setup
        const standBaseX = benchX + benchW * 0.46;
        const standBaseY = H - 36;
        const standRodX = standBaseX - 58;

        // Metal base plate
        ctx.fillStyle = '#2b3035';
        ctx.strokeStyle = '#4a5157';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.roundRect(standBaseX - 85, standBaseY, 170, 16, 3);
        ctx.fill();
        ctx.stroke();

        // Vertical support rod
        ctx.fillStyle = '#8a939b';
        ctx.fillRect(standRodX, 28, 7, standBaseY - 28);

        // Clamp arm holding burette
        const clampY = 90;
        ctx.fillStyle = '#5a626a';
        ctx.fillRect(standRodX + 4, clampY, 46, 6);
        ctx.fillStyle = '#adb5bd';
        ctx.fillRect(standRodX + 46, clampY - 4, 10, 14);

        // Graduated Burette
        const buretteX = standRodX + 54;
        const buretteTopY = 32;
        const buretteH = 150;
        const buretteW = 14;

        // Burette glass body
        ctx.fillStyle = 'rgba(255, 255, 255, 0.06)';
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.45)';
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.rect(buretteX - buretteW / 2, buretteTopY, buretteW, buretteH);
        ctx.fill();
        ctx.stroke();

        // Liquid remaining in burette (depletes as VbCur increases)
        const buretteFillRatio = Math.max(0.05, 1.0 - VbCur / 50.0);
        const liqH = buretteH * buretteFillRatio;
        const liqTopY = buretteTopY + (buretteH - liqH);

        ctx.fillStyle = 'rgba(102, 217, 239, 0.35)';
        ctx.fillRect(buretteX - buretteW / 2 + 1, liqTopY, buretteW - 2, liqH);

        // Curved Meniscus in burette
        ctx.strokeStyle = 'rgba(102, 217, 239, 0.85)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.ellipse(buretteX, liqTopY, buretteW / 2 - 1, 2.5, 0, 0, Math.PI);
        ctx.stroke();

        // Millimeter tick markings on burette
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = 0.8;
        for (let t = 0; t <= 10; t++) {
          const ty = buretteTopY + (buretteH / 10) * t;
          ctx.beginPath();
          ctx.moveTo(buretteX + buretteW / 2 - (t % 2 === 0 ? 5 : 3), ty);
          ctx.lineTo(buretteX + buretteW / 2, ty);
          ctx.stroke();
        }

        // Burette Stopcock Valve
        const stopcockY = buretteTopY + buretteH + 6;
        const isFlowing = isRunning && VbCur < VbMax;
        ctx.fillStyle = '#525a61';
        ctx.fillRect(buretteX - 5, stopcockY - 4, 10, 8);

        // Rotatable stopcock lever
        ctx.save();
        ctx.translate(buretteX, stopcockY);
        if (!isFlowing) ctx.rotate(Math.PI / 2); // Horizontal when stopped
        ctx.fillStyle = isFlowing ? '#2ecc71' : '#e5b85c';
        ctx.fillRect(-7, -2.5, 14, 5);
        ctx.restore();

        // Burette delivery nozzle
        const nozzleTipY = stopcockY + 16;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.55)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(buretteX - 3, stopcockY + 4);
        ctx.lineTo(buretteX - 1.2, nozzleTipY);
        ctx.lineTo(buretteX + 1.2, nozzleTipY);
        ctx.lineTo(buretteX + 3, stopcockY + 4);
        ctx.stroke();

        // Magnetic Stirrer Plate Base under Flask
        const plateX = buretteX - 45;
        const plateY = H - 52;
        const plateW = 90;
        const plateH = 16;

        ctx.fillStyle = '#e8edf0';
        ctx.strokeStyle = '#bdc3c7';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.roundRect(plateX, plateY, plateW, plateH, 3);
        ctx.fill();
        ctx.stroke();

        // Stirrer control knob & LED
        ctx.fillStyle = '#2c3e50';
        ctx.beginPath();
        ctx.arc(plateX + 18, plateY + plateH / 2, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = isRunning ? '#2ecc71' : '#7f8c8d';
        ctx.beginPath();
        ctx.arc(plateX + plateW - 16, plateY + plateH / 2, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Conical Erlenmeyer Reaction Flask
        const flaskBottomY = plateY;
        const flaskW = 76;
        const flaskNeckTopY = nozzleTipY + 28;
        const flaskNeckW = 20;

        // Flask fluid volume increases with Va + Vb
        const maxFlaskVol = 100;
        const curVol = Va + VbCur;
        const volFraction = Math.min(0.85, Math.max(0.18, curVol / maxFlaskVol));
        const fluidSurfaceY = flaskBottomY - volFraction * 68;

        // Phenolphthalein continuous color gradient calculation
        // Transition around pH 8.2 -> 10.0
        const transAlpha = Math.max(0, Math.min(1, (curPh - 8.2) / 1.8));
        // Pale cyan (180, 230, 255) to vibrant magenta (249, 38, 114)
        const rVal = Math.round((1 - transAlpha) * 160 + transAlpha * 249);
        const gVal = Math.round((1 - transAlpha) * 220 + transAlpha * 38);
        const bVal = Math.round((1 - transAlpha) * 245 + transAlpha * 114);
        const liquidOpacity = 0.22 + transAlpha * 0.58;

        // Draw Flask liquid fill with sloping conical bounds
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(buretteX - flaskW / 2 + 3, flaskBottomY - 1);
        ctx.lineTo(buretteX + flaskW / 2 - 3, flaskBottomY - 1);
        ctx.lineTo(buretteX + flaskNeckW / 2 + 10, fluidSurfaceY);

        // Liquid Parabolic Surface Vortex Depression (stirrer rotation effect)
        const vortexDepth = isRunning ? 5.5 : 0;
        ctx.quadraticCurveTo(buretteX, fluidSurfaceY + vortexDepth, buretteX - flaskNeckW / 2 - 10, fluidSurfaceY);
        ctx.closePath();
        ctx.fillStyle = `rgba(${rVal}, ${gVal}, ${bVal}, ${liquidOpacity})`;
        ctx.fill();

        // Swirl eddies inside the fluid
        if (isRunning && transAlpha > 0.05) {
          ctx.strokeStyle = `rgba(249, 38, 114, ${transAlpha * 0.4})`;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          const ang = stirAngleRef.current;
          ctx.ellipse(buretteX, (fluidSurfaceY + flaskBottomY) / 2, 14, 5, ang, 0, Math.PI * 1.5);
          ctx.stroke();
        }

        // Teflon Magnetic Stir Bar Capsule on bottom of flask
        ctx.save();
        ctx.translate(buretteX, flaskBottomY - 5);
        if (isRunning) {
          const barScaleX = Math.cos(stirAngleRef.current);
          ctx.scale(barScaleX, 1);
        }
        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = '#7f8c8d';
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.roundRect(-8, -2.5, 16, 5, 2.5);
        ctx.fill();
        ctx.stroke();
        ctx.restore();

        ctx.restore();

        // Flask Glass Outline
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.65)';
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        // Neck
        ctx.moveTo(buretteX - flaskNeckW / 2, flaskNeckTopY);
        ctx.lineTo(buretteX - flaskNeckW / 2, flaskNeckTopY + 16);
        // Left conical wall
        ctx.lineTo(buretteX - flaskW / 2, flaskBottomY);
        // Flat bottom
        ctx.lineTo(buretteX + flaskW / 2, flaskBottomY);
        // Right conical wall
        ctx.lineTo(buretteX + flaskNeckW / 2, flaskNeckTopY + 16);
        // Right neck
        ctx.lineTo(buretteX + flaskNeckW / 2, flaskNeckTopY);
        ctx.stroke();

        // Flask rim flange
        ctx.beginPath();
        ctx.ellipse(buretteX, flaskNeckTopY, flaskNeckW / 2 + 2, 2.5, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Animated Gravity Droplets & Impact Ripples
        if (isFlowing && Math.random() < 0.28) {
          dropletsRef.current.push({
            x: buretteX,
            y: nozzleTipY,
            vy: 20 + Math.random() * 15,
            radius: 2.2
          });
        }

        // Update droplets
        for (let i = dropletsRef.current.length - 1; i >= 0; i--) {
          const d = dropletsRef.current[i];
          d.vy += 280 * dt; // gravity
          d.y += d.vy * dt;

          // Droplet hits liquid surface
          if (d.y >= fluidSurfaceY) {
            ripplesRef.current.push({
              x: d.x,
              y: fluidSurfaceY,
              radius: 1.5,
              alpha: 0.85
            });
            dropletsRef.current.splice(i, 1);
            continue;
          }

          // Draw teardrop
          ctx.fillStyle = 'rgba(102, 217, 239, 0.85)';
          ctx.beginPath();
          ctx.arc(d.x, d.y, d.radius, 0, Math.PI * 2);
          ctx.fill();
        }

        // Draw and update concentric surface ripples
        for (let i = ripplesRef.current.length - 1; i >= 0; i--) {
          const rip = ripplesRef.current[i];
          rip.radius += 28 * dt;
          rip.alpha -= 1.4 * dt;
          if (rip.alpha <= 0) {
            ripplesRef.current.splice(i, 1);
            continue;
          }
          ctx.strokeStyle = `rgba(255, 255, 255, ${rip.alpha})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.ellipse(rip.x, rip.y, rip.radius, rip.radius * 0.35, 0, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Benchtop Digital pH Meter Console & Dip Electrode Probe
        const meterX = W - 118;
        const meterY = H - 90;
        const meterW = 96;
        const meterH = 54;

        // Meter body
        ctx.fillStyle = '#1e2429';
        ctx.strokeStyle = '#34495e';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.roundRect(meterX, meterY, meterW, meterH, 5);
        ctx.fill();
        ctx.stroke();

        // 7-segment style LCD display
        ctx.fillStyle = '#0f171c';
        ctx.fillRect(meterX + 8, meterY + 12, meterW - 16, 26);
        ctx.font = '13px "JetBrains Mono", monospace';
        ctx.fillStyle = curPh < 7.0 ? '#66d9ef' : (curPh > 8.2 ? '#f92672' : '#2ecc71');
        ctx.textAlign = 'center';
        ctx.fillText(`pH ${curPh.toFixed(2)}`, meterX + meterW / 2, meterY + 30);

        ctx.font = '8px "JetBrains Mono", monospace';
        ctx.fillStyle = '#7f8c8d';
        ctx.fillText('DIGITAL pH METER', meterX + meterW / 2, meterY + meterH - 4);

        // Electrode cable from meter to flask
        const probeStartX = meterX + 6;
        const probeStartY = meterY + 16;
        const probeTipX = buretteX + 16;
        const probeTipY = fluidSurfaceY + 18;

        ctx.strokeStyle = '#2c3e50';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(probeStartX, probeStartY);
        ctx.bezierCurveTo(meterX - 25, meterY - 30, probeTipX + 15, flaskNeckTopY - 20, probeTipX, flaskNeckTopY);
        ctx.lineTo(probeTipX, probeTipY);
        ctx.stroke();

        // Dip probe glass body & bulb
        ctx.fillStyle = '#7f8c8d';
        ctx.fillRect(probeTipX - 2, flaskNeckTopY + 4, 4, probeTipY - flaskNeckTopY - 4);
        ctx.fillStyle = '#3498db';
        ctx.beginPath();
        ctx.arc(probeTipX, probeTipY, 3, 0, Math.PI * 2);
        ctx.fill();

      // -------------------------------------------------------------
      // 2. GAS LAW: 2D Maxwell-Boltzmann Molecular Engine & Analog Gauge
      // -------------------------------------------------------------
      } else if (widget === 'gas_law') {
        const n = params.n ?? 1.0;
        const T = params.T ?? 300.0;
        const V = params.V ?? 15.0; // 5 to 30

        const R = 8.314;
        const P_theo = (n * R * T) / V; // kPa

        const boxX = 40;
        const boxY = 60;
        const maxW = W - 180;
        const boxH = H - 90;
        const curW = Math.max(90, (V / 30.0) * maxW);
        const pistonX = boxX + curW;

        // Cylinder walls
        ctx.strokeStyle = '#4a5568';
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.moveTo(boxX, boxY);
        ctx.lineTo(boxX, boxY + boxH);
        ctx.lineTo(boxX + maxW, boxY + boxH);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(boxX, boxY);
        ctx.lineTo(boxX + maxW, boxY);
        ctx.stroke();

        // Piston Head & Rod
        ctx.fillStyle = '#e5b85c';
        ctx.fillRect(pistonX - 9, boxY + 3, 18, boxH - 6);
        ctx.fillStyle = '#718096';
        ctx.fillRect(pistonX + 9, boxY + boxH / 2 - 7, 50, 14);

        // Update & draw gas particles with Maxwell-Boltzmann physics
        const pts = particlesRef.current;
        let frameImpulse = 0;

        ctx.fillStyle = '#66d9ef';
        for (const p of pts) {
          if (isRunning) {
            p.x += p.vx * dt;
            p.y += p.vy * dt;

            // Particle-wall collision momentum impulse calculations (2 * m * v_perp)
            if (p.x - p.r < boxX) {
              p.x = boxX + p.r;
              p.vx = Math.abs(p.vx);
              frameImpulse += 2 * p.mass * Math.abs(p.vx);
            }
            if (p.x + p.r > pistonX - 9) {
              p.x = pistonX - 9 - p.r;
              p.vx = -Math.abs(p.vx);
              frameImpulse += 2 * p.mass * Math.abs(p.vx);
            }
            if (p.y - p.r < boxY) {
              p.y = boxY + p.r;
              p.vy = Math.abs(p.vy);
              frameImpulse += 2 * p.mass * Math.abs(p.vy);
            }
            if (p.y + p.r > boxY + boxH) {
              p.y = boxY + boxH - p.r;
              p.vy = -Math.abs(p.vy);
              frameImpulse += 2 * p.mass * Math.abs(p.vy);
            }
          }

          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fill();
        }

        // Impulse smoothing & needle jitter
        const imp = impulseRef.current;
        imp.accumulator += frameImpulse;
        imp.windowTime += dt;
        if (imp.windowTime >= 0.12) {
          const rawP = (imp.accumulator / imp.windowTime) * 0.05;
          imp.smoothedP = imp.smoothedP * 0.7 + rawP * 0.3;
          imp.accumulator = 0;
          imp.windowTime = 0;
        }

        const needleJitter = isRunning ? (Math.random() - 0.5) * (T / 280) * 2.2 : 0;
        const P_display = isRunning && imp.smoothedP > 0 ? (imp.smoothedP * 0.4 + P_theo * 0.6 + needleJitter) : P_theo;

        // Analog Dial Pressure Gauge
        const gaugeCX = W - 78;
        const gaugeCY = boxY + 45;
        const gaugeR = 42;

        // Gauge bezel
        ctx.fillStyle = '#1a202c';
        ctx.strokeStyle = '#d69e2e';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(gaugeCX, gaugeCY, gaugeR, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Ticks on dial (0 to 600 kPa)
        const minAng = Math.PI * 0.75;
        const maxAng = Math.PI * 2.25;
        for (let k = 0; k <= 6; k++) {
          const ang = minAng + (k / 6) * (maxAng - minAng);
          const tx1 = gaugeCX + (gaugeR - 7) * Math.cos(ang);
          const ty1 = gaugeCY + (gaugeR - 7) * Math.sin(ang);
          const tx2 = gaugeCX + (gaugeR - 2) * Math.cos(ang);
          const ty2 = gaugeCY + (gaugeR - 2) * Math.sin(ang);
          ctx.strokeStyle = k >= 5 ? '#f92672' : '#cbd5e0';
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.moveTo(tx1, ty1);
          ctx.lineTo(tx2, ty2);
          ctx.stroke();
        }

        // Needle pointing to current pressure
        const pFraction = Math.min(1.0, Math.max(0, P_display / 500.0));
        const needleAng = minAng + pFraction * (maxAng - minAng);

        ctx.strokeStyle = '#f92672';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(gaugeCX, gaugeCY);
        ctx.lineTo(gaugeCX + (gaugeR - 10) * Math.cos(needleAng), gaugeCY + (gaugeR - 10) * Math.sin(needleAng));
        ctx.stroke();

        // Pivot center cap
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(gaugeCX, gaugeCY, 3.5, 0, Math.PI * 2);
        ctx.fill();

        // Gauge text readout
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillStyle = pal.ink || '#fff';
        ctx.textAlign = 'center';
        ctx.fillText('PRESSURE', gaugeCX, gaugeCY + gaugeR + 16);
        ctx.fillStyle = '#2ecc71';
        ctx.fillText(`${P_display.toFixed(1)} kPa`, gaugeCX, gaugeCY + gaugeR + 30);

        // Header Readout
        ctx.textAlign = 'left';
        ctx.font = '12px "JetBrains Mono", monospace';
        ctx.fillStyle = '#2ecc71';
        ctx.fillText(`P = nRT/V = ${P_theo.toFixed(1)} kPa | T = ${T.toFixed(0)} K | V = ${V.toFixed(1)} L`, boxX, boxY - 18);

      // -------------------------------------------------------------
      // 3. KINETICS: Concentration Curves & Molecular Collision Chamber
      // -------------------------------------------------------------
      } else if (widget === 'kinetics') {
        const k = params.k ?? 0.5;
        const kRev = params.k_rev ?? 0.1;
        const A0 = params.A0 ?? 2.0;
        const isRev = Boolean(spec.reversible);
        const order = Number(spec.order ?? 1);
        const Ea = params.Ea ?? 50.0;

        const splitX = Math.floor(W * 0.58);

        // --- LEFT PANE: Concentration Curves ---
        const margin = { top: 30, right: 20, bottom: 45, left: 50 };
        const gW = splitX - margin.left - margin.right;
        const gH = H - margin.top - margin.bottom;

        let tHalf = Infinity;
        if (order === 0) tHalf = A0 / (2 * k);
        else if (order === 1) tHalf = Math.LN2 / k;
        else if (order === 2) tHalf = 1 / (k * A0);

        const tMax = Math.max(10, tHalf * 3.5);
        const yMax = A0 * 1.15;

        const toX = (t) => margin.left + (t / tMax) * gW;
        const toY = (val) => margin.top + gH - (val / yMax) * gH;

        ctx.strokeStyle = pal.rule || '#282828';
        ctx.lineWidth = 1;
        ctx.strokeRect(margin.left, margin.top, gW, gH);

        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillStyle = pal.muted || '#777';
        ctx.textAlign = 'center';

        for (let i = 0; i <= 5; i++) {
          const tVal = (tMax / 5) * i;
          const px = toX(tVal);
          ctx.beginPath();
          ctx.moveTo(px, margin.top);
          ctx.lineTo(px, margin.top + gH);
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
          ctx.stroke();
          ctx.fillText(tVal.toFixed(1) + 's', px, margin.top + gH + 16);
        }

        ctx.textAlign = 'right';
        for (let i = 0; i <= 4; i++) {
          const yVal = (yMax / 4) * i;
          const py = toY(yVal);
          ctx.beginPath();
          ctx.moveTo(margin.left, py);
          ctx.lineTo(margin.left + gW, py);
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
          ctx.stroke();
          ctx.fillText(yVal.toFixed(2), margin.left - 6, py + 3);
        }

        // Curves calculation
        const steps = 180;
        const concA = [];
        const concB = [];

        for (let i = 0; i <= steps; i++) {
          const t = (tMax / steps) * i;
          let a = 0, b = 0;
          if (isRev) {
            const Keq = k / (kRev || 0.0001);
            const aEq = A0 / (1 + Keq);
            a = aEq + (A0 - aEq) * Math.exp(-(k + kRev) * t);
            b = A0 - a;
          } else if (order === 0) {
            a = Math.max(0, A0 - k * t);
            b = A0 - a;
          } else if (order === 1) {
            a = A0 * Math.exp(-k * t);
            b = A0 - a;
          } else if (order === 2) {
            a = A0 / (1 + k * A0 * t);
            b = A0 - a;
          }
          concA.push({ t, val: a });
          concB.push({ t, val: b });
        }

        // Draw [A] curve (cyan)
        ctx.strokeStyle = '#66d9ef';
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        concA.forEach((pt, idx) => {
          if (idx === 0) ctx.moveTo(toX(pt.t), toY(pt.val));
          else ctx.lineTo(toX(pt.t), toY(pt.val));
        });
        ctx.stroke();

        // Draw [B] curve (gold)
        ctx.strokeStyle = '#e5b85c';
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        concB.forEach((pt, idx) => {
          if (idx === 0) ctx.moveTo(toX(pt.t), toY(pt.val));
          else ctx.lineTo(toX(pt.t), toY(pt.val));
        });
        ctx.stroke();

        // Time progress marker
        const curT = simTimeRef.current % tMax;
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(toX(curT), margin.top);
        ctx.lineTo(toX(curT), margin.top + gH);
        ctx.stroke();

        // --- RIGHT PANE: Molecular Reaction Chamber with Flashes ---
        const chX = splitX + 16;
        const chY = margin.top;
        const chW = W - chX - 16;
        const chH = gH;

        ctx.fillStyle = '#161b22';
        ctx.strokeStyle = '#30363d';
        ctx.lineWidth = 1.5;
        ctx.fillRect(chX, chY, chW, chH);
        ctx.strokeRect(chX, chY, chW, chH);

        ctx.font = '11px "JetBrains Mono", monospace';
        ctx.fillStyle = pal.ink || '#fff';
        ctx.textAlign = 'left';
        ctx.fillText('Reactive Collision Cell', chX + 8, chY + 16);

        // Update kinetics particles
        const kPts = kineticsParticlesRef.current;
        for (let i = 0; i < kPts.length; i++) {
          const p1 = kPts[i];
          if (!p1.initialized) {
            p1.x = chX + p1.relX * chW;
            p1.y = chY + 22 + p1.relY * Math.max(10, chH - 26);
            p1.initialized = true;
          }
          if (isRunning) {
            p1.x += p1.vx * dt;
            p1.y += p1.vy * dt;

            // Boundaries
            if (p1.x - p1.r < chX) { p1.x = chX + p1.r; p1.vx = Math.abs(p1.vx); }
            if (p1.x + p1.r > chX + chW) { p1.x = chX + chW - p1.r; p1.vx = -Math.abs(p1.vx); }
            if (p1.y - p1.r < chY + 22) { p1.y = chY + 22 + p1.r; p1.vy = Math.abs(p1.vy); }
            if (p1.y + p1.r > chY + chH) { p1.y = chY + chH - p1.r; p1.vy = -Math.abs(p1.vy); }

            // Collisions between particles
            for (let j = i + 1; j < kPts.length; j++) {
              const p2 = kPts[j];
              const cdx = p2.x - p1.x;
              const cdy = p2.y - p1.y;
              const dist = Math.sqrt(cdx * cdx + cdy * cdy);
              if (dist < p1.r + p2.r && dist > 0.001) {
                // Elastic velocity exchange
                const nx = cdx / dist;
                const ny = cdy / dist;
                const relV = (p1.vx - p2.vx) * nx + (p1.vy - p2.vy) * ny;

                if (relV > 0) {
                  p1.vx -= relV * nx;
                  p1.vy -= relV * ny;
                  p2.vx += relV * nx;
                  p2.vy += relV * ny;

                  // Reactive threshold check: Ea threshold
                  const collKE = 0.5 * relV * relV * 0.08;
                  if (collKE >= Ea * 0.015 && (p1.species === 'A' || p2.species === 'A')) {
                    if (p1.species === 'A') p1.species = 'B';
                    else if (p2.species === 'A') p2.species = 'B';

                    // Spawn optical reaction flash burst!
                    flashesRef.current.push({
                      x: (p1.x + p2.x) / 2,
                      y: (p1.y + p2.y) / 2,
                      r: 2,
                      alpha: 0.95
                    });
                  }
                }
              }
            }
          }

          // Draw molecular particle
          ctx.fillStyle = p1.species === 'A' ? '#66d9ef' : '#e5b85c';
          ctx.beginPath();
          ctx.arc(p1.x, p1.y, p1.r, 0, Math.PI * 2);
          ctx.fill();
        }

        // Draw and update reaction flash bursts
        for (let i = flashesRef.current.length - 1; i >= 0; i--) {
          const fl = flashesRef.current[i];
          fl.r += 35 * dt;
          fl.alpha -= 2.2 * dt;
          if (fl.alpha <= 0) {
            flashesRef.current.splice(i, 1);
            continue;
          }
          ctx.strokeStyle = `rgba(255, 235, 59, ${fl.alpha})`;
          ctx.lineWidth = 1.8;
          ctx.beginPath();
          ctx.arc(fl.x, fl.y, fl.r, 0, Math.PI * 2);
          ctx.stroke();
        }

      // -------------------------------------------------------------
      // 4. EQUILIBRIUM: aA + bB <=> cC + dD
      // -------------------------------------------------------------
      } else if (widget === 'equilibrium') {
        const K = params.K ?? spec.K ?? 4.0;
        const a = spec.a ?? 1, b = spec.b ?? 1, c = spec.c ?? 1, d = spec.d ?? 1;
        const A0 = params.A0 ?? 2.0;
        const B0 = params.B0 ?? 2.0;
        const C0 = params.C0 ?? 0.0;
        const D0 = params.D0 ?? 0.0;

        const numQ = Math.pow(Math.max(1e-6, C0), c) * Math.pow(Math.max(1e-6, D0), d);
        const denQ = Math.pow(Math.max(1e-6, A0), a) * Math.pow(Math.max(1e-6, B0), b);
        const Q = denQ > 0 ? numQ / denQ : Infinity;

        const maxForward = Math.min(A0 / a, B0 / b);
        const maxBackward = Math.min(C0 / c, D0 / d);
        let lo = -maxBackward, hi = maxForward;

        for (let iter = 0; iter < 50; iter++) {
          const mid = (lo + hi) / 2;
          const aMid = A0 - a * mid;
          const bMid = B0 - b * mid;
          const cMid = C0 + c * mid;
          const dMid = D0 + d * mid;
          const qMid = (Math.pow(cMid, c) * Math.pow(dMid, d)) / (Math.pow(aMid, a) * Math.pow(bMid, b));
          if (qMid < K) lo = mid;
          else hi = mid;
        }

        const xi = (lo + hi) / 2;
        const A_eq = Math.max(0, A0 - a * xi);
        const B_eq = Math.max(0, B0 - b * xi);
        const C_eq = Math.max(0, C0 + c * xi);
        const D_eq = Math.max(0, D0 + d * xi);

        const species = [
          { name: 'A', init: A0, eq: A_eq, color: '#66d9ef' },
          { name: 'B', init: B0, eq: B_eq, color: '#2ecc71' },
          { name: 'C', init: C0, eq: C_eq, color: '#e5b85c' },
          { name: 'D', init: D0, eq: D_eq, color: '#fd971f' }
        ];

        const chartX = 60, chartY = 45, chartW = W - 120, chartH = H - 100;
        const maxVal = Math.max(5, A0, B0, C0, D0, A_eq, B_eq, C_eq, D_eq) * 1.2;

        ctx.strokeStyle = pal.rule || '#282828';
        ctx.strokeRect(chartX, chartY, chartW, chartH);

        const groupW = chartW / 4;
        const barW = groupW * 0.32;

        species.forEach((sp, idx) => {
          const gx = chartX + idx * groupW + groupW * 0.18;
          const hInit = (sp.init / maxVal) * chartH;
          ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
          ctx.fillRect(gx, chartY + chartH - hInit, barW, hInit);

          const hEq = (sp.eq / maxVal) * chartH;
          ctx.fillStyle = sp.color;
          ctx.fillRect(gx + barW + 4, chartY + chartH - hEq, barW, hEq);

          ctx.font = '12px "JetBrains Mono", monospace';
          ctx.fillStyle = pal.ink || '#fff';
          ctx.textAlign = 'center';
          ctx.fillText(`[${sp.name}]`, gx + barW + 2, chartY + chartH + 20);

          ctx.font = '10px "JetBrains Mono", monospace';
          ctx.fillText(sp.eq.toFixed(2), gx + barW + 4 + barW / 2, chartY + chartH - hEq - 6);
        });

        let direction = 'At Equilibrium (Q ≈ K)';
        let dirColor = '#2ecc71';
        if (Q < K * 0.95) { direction = 'Shifts Forward (Right →)'; dirColor = '#66d9ef'; }
        else if (Q > K * 1.05) { direction = 'Shifts Reverse (Left ←)'; dirColor = '#f92672'; }

        ctx.font = '12px "JetBrains Mono", monospace';
        ctx.fillStyle = dirColor;
        ctx.textAlign = 'left';
        ctx.fillText(`Q = ${isFinite(Q) ? Q.toFixed(3) : '∞'} | K = ${K.toFixed(2)}  ➔  ${direction}`, chartX, chartY - 14);

      // -------------------------------------------------------------
      // 5. ENERGY DIAGRAM: Reaction Coordinate & Activation Energy
      // -------------------------------------------------------------
      } else if (widget === 'energy_diagram') {
        const Ea = params.Ea ?? spec.Ea ?? 50.0;
        const deltaH = params.deltaH ?? spec.deltaH ?? -20.0;
        const EaCat = spec.Ea_cat ?? 25.0;
        const T = params.T ?? 298.0;

        const R_gas = 0.008314;
        const fraction = Math.exp(-Ea / (R_gas * T));

        const margin = { top: 40, right: 40, bottom: 50, left: 70 };
        const gW = W - margin.left - margin.right;
        const gH = H - margin.top - margin.bottom;

        const E_react = 40;
        const E_ts = E_react + Ea;
        const E_prod = E_react + deltaH;
        const maxE = Math.max(E_ts, E_react, E_prod) + 15;

        const toY = (e) => margin.top + gH - (e / maxE) * gH;

        ctx.strokeStyle = '#66d9ef';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(margin.left, toY(E_react));
        ctx.bezierCurveTo(margin.left + gW * 0.35, toY(E_react), margin.left + gW * 0.45, toY(E_ts), margin.left + gW * 0.5, toY(E_ts));
        ctx.bezierCurveTo(margin.left + gW * 0.55, toY(E_ts), margin.left + gW * 0.65, toY(E_prod), margin.left + gW, toY(E_prod));
        ctx.stroke();

        if (EaCat < Ea) {
          const E_ts_cat = E_react + EaCat;
          ctx.strokeStyle = '#e5b85c';
          ctx.setLineDash([5, 5]);
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(margin.left + gW * 0.25, toY(E_react));
          ctx.bezierCurveTo(margin.left + gW * 0.4, toY(E_react), margin.left + gW * 0.45, toY(E_ts_cat), margin.left + gW * 0.5, toY(E_ts_cat));
          ctx.bezierCurveTo(margin.left + gW * 0.55, toY(E_ts_cat), margin.left + gW * 0.6, toY(E_prod), margin.left + gW * 0.75, toY(E_prod));
          ctx.stroke();
          ctx.setLineDash([]);
        }

        ctx.font = '11px "JetBrains Mono", monospace';
        ctx.fillStyle = pal.ink || '#fff';
        ctx.textAlign = 'left';
        ctx.fillText(`Reactants`, margin.left + 5, toY(E_react) - 8);
        ctx.fillText(`Products`, margin.left + gW - 60, toY(E_prod) - 8);
        ctx.fillText(`Ea = ${Ea} kJ/mol`, margin.left + gW * 0.5 - 40, toY(E_ts) - 10);
        ctx.fillText(`ΔH = ${deltaH} kJ/mol`, margin.left + gW * 0.75, toY(E_prod) + 20);

        ctx.fillStyle = '#2ecc71';
        ctx.fillText(`Boltzmann Fraction e^(-Ea/RT) = ${fraction.toExponential(3)}`, margin.left, margin.top - 12);

      // -------------------------------------------------------------
      // 6. DECAY: Radioactive Decay Lattice & Law
      // -------------------------------------------------------------
      } else if (widget === 'decay') {
        const N0 = params.N0 ?? 100;
        const tHalf = params.t_half ?? 5.0;
        const lambda = Math.LN2 / tHalf;

        const leftW = W * 0.45;
        const rightW = W * 0.45;

        const pts = particlesRef.current;
        const cols = 10;
        const spacing = Math.min(22, (leftW - 30) / cols);

        ctx.font = '11px "JetBrains Mono", monospace';
        ctx.fillStyle = pal.ink || '#fff';
        ctx.textAlign = 'left';
        ctx.fillText('Nuclei Grid', 20, 25);

        let remaining = 0;
        pts.forEach((p, i) => {
          if (isRunning && !p.decayed) {
            const prob = 1 - Math.exp(-lambda * dt);
            if (Math.random() < prob) {
              p.decayed = true;
              p.decayTime = simTimeRef.current;
            }
          }
          if (!p.decayed) remaining++;

          const col = i % cols;
          const row = Math.floor(i / cols);
          const px = 25 + col * spacing;
          const py = 45 + row * spacing;

          ctx.fillStyle = p.decayed ? 'rgba(255, 255, 255, 0.12)' : '#66d9ef';
          ctx.beginPath();
          ctx.arc(px, py, 6, 0, Math.PI * 2);
          ctx.fill();
        });

        const chartX = W - rightW - 20, chartY = 40, chartH = H - 80;
        ctx.strokeStyle = pal.rule || '#282828';
        ctx.strokeRect(chartX, chartY, rightW, chartH);

        const tMax = tHalf * 4;
        ctx.strokeStyle = '#e5b85c';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        for (let i = 0; i <= 100; i++) {
          const t = (tMax / 100) * i;
          const nTheor = N0 * Math.exp(-lambda * t);
          const px = chartX + (t / tMax) * rightW;
          const py = chartY + chartH - (nTheor / N0) * chartH;
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.stroke();

        ctx.fillStyle = '#66d9ef';
        ctx.textAlign = 'right';
        ctx.fillText(`N(t) Live: ${remaining} / ${N0}`, W - 20, 25);
      }

      ctx.restore();
      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [spec, params, isRunning]);

  return (
    <div style={{
      background: theme.bgPanel,
      border: `1px solid ${theme.border}`,
      borderRadius: 8,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
      padding: 16
    }}>
      {/* Header with Title & Play/Reset */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: `1px solid ${theme.border}`, paddingBottom: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: theme.fontMono, fontSize: '0.92rem', fontWeight: 700, color: theme.accentGreen }}>
            <FlaskConical size={16} color={theme.accentGreen} />
            <span>{spec.title || 'Chemistry Simulation'}</span>
          </div>
          {spec.description && (
            <div style={{ fontSize: '0.80rem', color: theme.textDim, marginTop: 4, lineHeight: 1.45 }}>
              {spec.description}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => setIsRunning(!isRunning)}
            style={{
              background: isRunning ? theme.bgCard : theme.accentGreen,
              color: isRunning ? theme.textMain : '#000000',
              border: `1px solid ${theme.border}`,
              borderRadius: 4,
              padding: '6px 12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontFamily: theme.fontMono,
              fontSize: '0.78rem',
              fontWeight: 700
            }}
          >
            {isRunning ? <><Pause size={13} /> Pause</> : <><Play size={13} /> Animate</>}
          </button>
          <button
            onClick={handleReset}
            style={{
              background: theme.bgCard,
              border: `1px solid ${theme.border}`,
              color: theme.textDim,
              borderRadius: 4,
              padding: '6px 10px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontFamily: theme.fontMono,
              fontSize: '0.78rem'
            }}
            title="Reset Simulation"
          >
            <RotateCcw size={13} /> Reset
          </button>
        </div>
      </div>

      {/* Main Simulation Canvas */}
      <div style={{ position: 'relative', width: '100%', height: 420, borderRadius: 6, overflow: 'hidden', border: `1px solid ${theme.border}` }}>
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: '100%', display: 'block', background: '#101111' }}
        />
      </div>

      {/* Parameter Sliders */}
      {spec.params && spec.params.length > 0 && (
        <div style={{
          background: 'rgba(16, 17, 17, 0.7)',
          border: `1px solid ${theme.border}`,
          borderRadius: 6,
          padding: '14px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: theme.fontMono, fontSize: '0.75rem', fontWeight: 700, color: theme.textDim, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            <Sliders size={13} color={theme.accentGold} />
            <span>Chemistry Parameters & Sliders</span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 14
          }}>
            {spec.params.map(p => {
              const val = params[p.name] ?? p.value ?? p.min;
              return (
                <div key={p.name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', fontFamily: theme.fontMono }}>
                    <span style={{ color: theme.textMain }}>{p.label || p.name}</span>
                    <span style={{ color: theme.accentGold, fontWeight: 700 }}>
                      {Number(val).toFixed(p.step && p.step < 1 ? 2 : 1)} {p.unit || ''}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={p.min}
                    max={p.max}
                    step={p.step || (p.max - p.min) / 100}
                    value={val}
                    onChange={(e) => handleParamChange(p.name, e.target.value)}
                    style={{
                      width: '100%',
                      accentColor: theme.accentGreen,
                      cursor: 'pointer'
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
