import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Play, Pause, RotateCcw, Activity, FlaskConical, Sliders, Info, Zap } from 'lucide-react';
import { theme, canvasPalette } from '../theme';

// ---------------------------------------------------------------------------
// Chemistry Simulation Kit (SimSpec kind "chem")
// Implements 6 interactive widgets: kinetics, equilibrium, titration, gas_law,
// energy_diagram, decay. Renders cleanly in both light and dark themes.
// ---------------------------------------------------------------------------

function solvePh(pKa, Va, Ca, Cb, Vb, isStrong = false) {
  const Kw = 1.0e-14;
  const Vtot = Va + Vb;
  if (Vtot <= 0) return 7.0;
  const cNa = (Cb * Vb) / Vtot;
  const cATot = (Ca * Va) / Vtot;
  const Ka = isStrong ? 1e9 : Math.pow(10, -pKa);

  const f = (logH) => {
    const h = Math.pow(10, logH);
    const aMinus = isStrong ? cATot : (cATot * Ka) / (h + Ka);
    return h - (Kw / h) + cNa - aMinus;
  };

  let lo = -14.0, hi = 1.0;
  for (let i = 0; i < 70; i++) {
    const mid = (lo + hi) / 2;
    if (f(mid) < 0) lo = mid;
    else hi = mid;
  }
  return -((lo + hi) / 2);
}

export default function ChemSim({ spec }) {
  if (!spec || !spec.widget) {
    return (
      <div className="panel" style={{ padding: 24, textAlign: 'center', color: theme.textMuted }}>
        No chemistry simulation widget specified.
      </div>
    );
  }

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

  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const lastTimeRef = useRef(null);

  // Particles state for gas_law and decay
  const particlesRef = useRef([]);

  useEffect(() => {
    setParams(initialParams);
    simTimeRef.current = 0;
    setIsRunning(false);
  }, [initialParams]);

  const handleParamChange = (name, val) => {
    simTimeRef.current = 0;
    setParams(prev => ({ ...prev, [name]: Number(val) }));
  };

  const handleReset = () => {
    simTimeRef.current = 0;
    setIsRunning(false);
    lastTimeRef.current = null;
    initParticles();
  };

  // Initialize stochastic/physical particles for gas law and radioactive decay
  const initParticles = useCallback(() => {
    if (spec.widget === 'gas_law') {
      const count = Math.round((params.n || 1) * 35);
      const pts = [];
      const speed = Math.sqrt((params.T || 300) / 300) * 120;
      const boxX = 60, boxY = 50, boxH = 180;
      const V = params.V ?? 15.0;
      const curW = Math.max(80, (V / 30.0) * 300);
      for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2;
        pts.push({
          x: boxX + 10 + Math.random() * (curW - 20),
          y: boxY + 10 + Math.random() * (boxH - 20),
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          r: 3.5
        });
      }
      particlesRef.current = pts;
    } else if (spec.widget === 'decay') {
      const count = Math.round(params.N0 || 100);
      const pts = [];
      for (let i = 0; i < count; i++) {
        pts.push({ decayed: false, decayTime: null });
      }
      particlesRef.current = pts;
    }
  }, [spec.widget, params.n, params.T, params.V, params.N0, params.t_half]);

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
      // 1. KINETICS: A -> B or A <=> B
      // -------------------------------------------------------------
      if (widget === 'kinetics') {
        const k = params.k ?? 0.5;
        const kRev = params.k_rev ?? 0.1;
        const A0 = params.A0 ?? 2.0;
        const isRev = Boolean(spec.reversible);
        const order = Number(spec.order ?? 1);

        const margin = { top: 30, right: 30, bottom: 45, left: 55 };
        const gW = W - margin.left - margin.right;
        const gH = H - margin.top - margin.bottom;

        // Calculate half-life
        let tHalf = Infinity;
        if (order === 0) tHalf = A0 / (2 * k);
        else if (order === 1) tHalf = Math.LN2 / k;
        else if (order === 2) tHalf = 1 / (k * A0);

        const tMax = Math.max(10, tHalf * 3.5);
        const yMax = A0 * 1.15;

        const toX = (t) => margin.left + (t / tMax) * gW;
        const toY = (val) => margin.top + gH - (val / yMax) * gH;

        // Draw axes & grid
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
          ctx.fillText(yVal.toFixed(2), margin.left - 8, py + 3);
        }

        // Evaluate curves
        const steps = 200;
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
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        concA.forEach((pt, idx) => {
          if (idx === 0) ctx.moveTo(toX(pt.t), toY(pt.val));
          else ctx.lineTo(toX(pt.t), toY(pt.val));
        });
        ctx.stroke();

        // Draw [B] curve (gold)
        ctx.strokeStyle = '#e5b85c';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        concB.forEach((pt, idx) => {
          if (idx === 0) ctx.moveTo(toX(pt.t), toY(pt.val));
          else ctx.lineTo(toX(pt.t), toY(pt.val));
        });
        ctx.stroke();

        // Half-life vertical marker
        if (isFinite(tHalf) && tHalf < tMax) {
          ctx.strokeStyle = 'rgba(249, 38, 114, 0.7)';
          ctx.setLineDash([4, 4]);
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(toX(tHalf), margin.top);
          ctx.lineTo(toX(tHalf), margin.top + gH);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = '#f92672';
          ctx.textAlign = 'left';
          ctx.fillText(`t½ = ${tHalf.toFixed(2)}s`, toX(tHalf) + 6, margin.top + 20);
        }

        // Time progress marker if running
        const curT = simTimeRef.current % tMax;
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(toX(curT), margin.top);
        ctx.lineTo(toX(curT), margin.top + gH);
        ctx.stroke();

        // Legend
        ctx.textAlign = 'right';
        ctx.fillStyle = '#66d9ef';
        ctx.fillText('— [A] Reactant', margin.left + gW - 10, margin.top + 16);
        ctx.fillStyle = '#e5b85c';
        ctx.fillText('— [B] Product', margin.left + gW - 10, margin.top + 32);

      // -------------------------------------------------------------
      // 2. EQUILIBRIUM: aA + bB <=> cC + dD
      // -------------------------------------------------------------
      } else if (widget === 'equilibrium') {
        const K = params.K ?? spec.K ?? 4.0;
        const a = spec.a ?? 1, b = spec.b ?? 1, c = spec.c ?? 1, d = spec.d ?? 1;
        const A0 = params.A0 ?? 2.0;
        const B0 = params.B0 ?? 2.0;
        const C0 = params.C0 ?? 0.0;
        const D0 = params.D0 ?? 0.0;

        // Current Reaction Quotient Q
        const numQ = Math.pow(Math.max(1e-6, C0), c) * Math.pow(Math.max(1e-6, D0), d);
        const denQ = Math.pow(Math.max(1e-6, A0), a) * Math.pow(Math.max(1e-6, B0), b);
        const Q = denQ > 0 ? numQ / denQ : Infinity;

        // Solve equilibrium extent xi via bisection
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

        // Render Bar Chart: Initial vs Equilibrium
        const species = [
          { name: 'A', init: A0, eq: A_eq, color: '#66d9ef' },
          { name: 'B', init: B0, eq: B_eq, color: '#2ecc71' },
          { name: 'C', init: C0, eq: C_eq, color: '#e5b85c' },
          { name: 'D', init: D0, eq: D_eq, color: '#fd971f' }
        ];

        const chartX = 60, chartY = 40, chartW = W - 120, chartH = H - 100;
        const maxVal = Math.max(5, A0, B0, C0, D0, A_eq, B_eq, C_eq, D_eq) * 1.2;

        ctx.strokeStyle = pal.rule || '#282828';
        ctx.strokeRect(chartX, chartY, chartW, chartH);

        const groupW = chartW / 4;
        const barW = groupW * 0.32;

        species.forEach((sp, idx) => {
          const gx = chartX + idx * groupW + groupW * 0.18;

          // Initial bar
          const hInit = (sp.init / maxVal) * chartH;
          ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
          ctx.fillRect(gx, chartY + chartH - hInit, barW, hInit);

          // Eq bar
          const hEq = (sp.eq / maxVal) * chartH;
          ctx.fillStyle = sp.color;
          ctx.fillRect(gx + barW + 4, chartY + chartH - hEq, barW, hEq);

          // Labels
          ctx.font = '12px "JetBrains Mono", monospace';
          ctx.fillStyle = pal.ink || '#fff';
          ctx.textAlign = 'center';
          ctx.fillText(`[${sp.name}]`, gx + barW + 2, chartY + chartH + 20);

          ctx.font = '10px "JetBrains Mono", monospace';
          ctx.fillText(sp.eq.toFixed(2), gx + barW + 4 + barW / 2, chartY + chartH - hEq - 6);
        });

        // Direction badge
        let direction = 'At Equilibrium (Q ≈ K)';
        let dirColor = '#2ecc71';
        if (Q < K * 0.95) { direction = 'Shifts Forward (Right →)'; dirColor = '#66d9ef'; }
        else if (Q > K * 1.05) { direction = 'Shifts Reverse (Left ←)'; dirColor = '#f92672'; }

        ctx.font = '12px "JetBrains Mono", monospace';
        ctx.fillStyle = dirColor;
        ctx.textAlign = 'left';
        ctx.fillText(`Q = ${isFinite(Q) ? Q.toFixed(3) : '∞'} | K = ${K.toFixed(2)}  ➔  ${direction}`, chartX, chartY - 14);

      // -------------------------------------------------------------
      // 3. TITRATION: Strong/Weak Acid with Strong Base
      // -------------------------------------------------------------
      } else if (widget === 'titration') {
        const pKa = params.pKa ?? 4.75;
        const Va = params.Va ?? 25.0;
        const Ca = params.Ca ?? 0.1;
        const Cb = params.Cb ?? 0.1;
        const VbCur = params.Vb ?? 0.0;
        const isStrong = Boolean(spec.strong);

        const Veq = (Ca * Va) / Cb;
        const VbMax = Math.max(60, Veq * 2.2);

        const margin = { top: 30, right: 140, bottom: 45, left: 55 };
        const gW = W - margin.left - margin.right;
        const gH = H - margin.top - margin.bottom;

        const toX = (v) => margin.left + (v / VbMax) * gW;
        const toY = (ph) => margin.top + gH - (ph / 14.0) * gH;

        // Draw titration axes
        ctx.strokeStyle = pal.rule || '#282828';
        ctx.strokeRect(margin.left, margin.top, gW, gH);

        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillStyle = pal.muted || '#777';
        ctx.textAlign = 'center';

        for (let v = 0; v <= VbMax; v += 10) {
          const px = toX(v);
          ctx.fillText(`${v}`, px, margin.top + gH + 16);
        }
        ctx.fillText('Volume of Titrant Added (mL)', margin.left + gW / 2, margin.top + gH + 34);

        ctx.textAlign = 'right';
        for (let ph = 0; ph <= 14; ph += 2) {
          const py = toY(ph);
          ctx.fillText(`${ph}`, margin.left - 8, py + 3);
        }

        // Plot full titration curve
        ctx.strokeStyle = '#2ecc71';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        for (let v = 0; v <= VbMax; v += 0.5) {
          const ph = solvePh(pKa, Va, Ca, Cb, v, isStrong);
          const px = toX(v);
          const py = toY(ph);
          if (v === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.stroke();

        // Equivalence point & Half-equivalence markers
        const phEq = solvePh(pKa, Va, Ca, Cb, Veq, isStrong);
        ctx.fillStyle = '#f92672';
        ctx.beginPath();
        ctx.arc(toX(Veq), toY(phEq), 5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = pal.ink || '#fff';
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillText(`Equiv (pH ${phEq.toFixed(1)})`, toX(Veq) - 10, toY(phEq) - 10);

        if (!isStrong) {
          const Vhalf = Veq / 2;
          const phHalf = solvePh(pKa, Va, Ca, Cb, Vhalf, isStrong);
          ctx.fillStyle = '#e5b85c';
          ctx.beginPath();
          ctx.arc(toX(Vhalf), toY(phHalf), 4, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillText(`pH = pKa (${pKa.toFixed(2)})`, toX(Vhalf) - 8, toY(phHalf) - 8);
        }

        // Current point indicator
        const curPh = solvePh(pKa, Va, Ca, Cb, VbCur, isStrong);
        ctx.fillStyle = '#66d9ef';
        ctx.beginPath();
        ctx.arc(toX(VbCur), toY(curPh), 6, 0, Math.PI * 2);
        ctx.fill();

        // Right side: Beaker with indicator color
        const beakerX = W - 110, beakerY = margin.top + 20, beakerW = 75, beakerH = 100;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = 2;
        ctx.strokeRect(beakerX, beakerY, beakerW, beakerH);

        // Phenolphthalein color: colorless (clear blue) below pH 8.2, vibrant magenta/pink above
        const alpha = Math.min(1.0, Math.max(0.05, (curPh - 7.8) / 2.2));
        ctx.fillStyle = curPh < 8.2 ? 'rgba(102, 217, 239, 0.15)' : `rgba(249, 38, 114, ${0.2 + alpha * 0.7})`;
        ctx.fillRect(beakerX + 2, beakerY + 30, beakerW - 4, beakerH - 32);

        ctx.fillStyle = pal.ink || '#fff';
        ctx.textAlign = 'center';
        ctx.font = '11px "JetBrains Mono", monospace';
        ctx.fillText(`pH: ${curPh.toFixed(2)}`, beakerX + beakerW / 2, beakerY + beakerH + 18);

      // -------------------------------------------------------------
      // 4. GAS LAW: Piston Cylinder with Moving Particles
      // -------------------------------------------------------------
      } else if (widget === 'gas_law') {
        const n = params.n ?? 1.0;
        const T = params.T ?? 300.0;
        const V = params.V ?? 15.0; // 5 to 30

        const R = 8.314;
        const P_theo = (n * R * T) / V; // kPa

        const boxX = 60, boxY = 50, maxW = W - 180, boxH = H - 100;
        const curW = (V / 30.0) * maxW;

        // Cylinder walls
        ctx.strokeStyle = '#444a47';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(boxX, boxY);
        ctx.lineTo(boxX, boxY + boxH);
        ctx.lineTo(boxX + maxW, boxY + boxH);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(boxX, boxY);
        ctx.lineTo(boxX + maxW, boxY);
        ctx.stroke();

        // Piston (moves horizontally with V)
        const pistonX = boxX + curW;
        ctx.fillStyle = '#e5b85c';
        ctx.fillRect(pistonX - 8, boxY + 2, 16, boxH - 4);
        ctx.fillStyle = '#777';
        ctx.fillRect(pistonX + 8, boxY + boxH / 2 - 6, 40, 12);

        // Update & draw gas particles
        const speedScale = Math.sqrt(T / 300.0);
        const pts = particlesRef.current;

        ctx.fillStyle = '#66d9ef';
        for (const p of pts) {
          if (isRunning) {
            p.x += p.vx * speedScale * 0.016;
            p.y += p.vy * speedScale * 0.016;

            if (p.x - p.r < boxX) { p.x = boxX + p.r; p.vx = -p.vx; }
            if (p.x + p.r > pistonX - 8) { p.x = pistonX - 8 - p.r; p.vx = -p.vx; }
            if (p.y - p.r < boxY) { p.y = boxY + p.r; p.vy = -p.vy; }
            if (p.y + p.r > boxY + boxH) { p.y = boxY + boxH - p.r; p.vy = -p.vy; }
          }
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fill();
        }

        // Pressure readout
        ctx.font = '12px "JetBrains Mono", monospace';
        ctx.fillStyle = '#2ecc71';
        ctx.textAlign = 'left';
        ctx.fillText(`P = nRT/V = ${P_theo.toFixed(1)} kPa`, boxX, boxY - 14);

      // -------------------------------------------------------------
      // 5. ENERGY DIAGRAM: Reaction Coordinate & Activation Energy
      // -------------------------------------------------------------
      } else if (widget === 'energy_diagram') {
        const Ea = params.Ea ?? spec.Ea ?? 50.0;
        const deltaH = params.deltaH ?? spec.deltaH ?? -20.0;
        const EaCat = spec.Ea_cat ?? 25.0;
        const T = params.T ?? 298.0;

        const R_gas = 0.008314; // kJ/(mol*K)
        const fraction = Math.exp(-Ea / (R_gas * T));

        const margin = { top: 40, right: 40, bottom: 50, left: 70 };
        const gW = W - margin.left - margin.right;
        const gH = H - margin.top - margin.bottom;

        // Energy levels
        const E_react = 40;
        const E_ts = E_react + Ea;
        const E_prod = E_react + deltaH;
        const maxE = Math.max(E_ts, E_react, E_prod) + 15;

        const toY = (e) => margin.top + gH - (e / maxE) * gH;

        // Uncatalyzed profile (cyan)
        ctx.strokeStyle = '#66d9ef';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(margin.left, toY(E_react));
        ctx.bezierCurveTo(margin.left + gW * 0.35, toY(E_react), margin.left + gW * 0.45, toY(E_ts), margin.left + gW * 0.5, toY(E_ts));
        ctx.bezierCurveTo(margin.left + gW * 0.55, toY(E_ts), margin.left + gW * 0.65, toY(E_prod), margin.left + gW, toY(E_prod));
        ctx.stroke();

        // Catalyzed profile (dashed gold)
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

        // Labels
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

        // Draw particle lattice on left
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
            // Decay probability per frame
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

        // Continuous curve on right
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
      <div style={{ position: 'relative', width: '100%', height: 400, borderRadius: 6, overflow: 'hidden', border: `1px solid ${theme.border}` }}>
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
