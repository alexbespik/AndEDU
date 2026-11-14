import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import MathSim from './MathSim';
import ChemSim from './ChemSim';
import GeometrySim from './GeometrySim';
import { Play, Pause, RotateCcw, AlertTriangle, Activity, Sliders, Info } from 'lucide-react';
import { theme, canvasPalette } from '../theme';
import { tryCompile } from '../lib/expr';

function resolveColor(c, palette) {
  if (!c) return palette['gold'] || '#e5b85c';
  if (c.startsWith('#') || c.startsWith('rgb')) return c;
  const named = {
    accent: palette['accent'] || '#23a55a',
    gold: palette['gold'] || '#e5b85c',
    green: palette['accent'] || '#2ecc71',
    cyan: palette['info'] || '#66d9ef',
    pink: palette['bad'] || '#f92672',
    orange: palette['gold-text'] || '#fd971f',
    purple: palette['plum'] || '#ae81ff',
    white: palette['ink'] || '#ffffff',
    bad: palette['bad'] || '#f92672',
    info: palette['info'] || '#66d9ef',
    muted: palette['muted'] || '#747c78'
  };
  return named[c.toLowerCase()] || c;
}

const SPEEDS = [0.25, 0.5, 1, 2, 4];

export default function SpecSim({ spec }) {
  if (!spec || !spec.kind) {
    return <div className="panel"><p className="hint">This topic has no simulation yet.</p></div>;
  }
  if (spec.kind === 'math') return <MathSim spec={spec} />;
  if (spec.kind === 'chem') return <ChemSim spec={spec} />;
  if (spec.kind === 'geometry' || spec.kind === 'fbd') return <GeometrySim spec={spec} />;
  return <SpecSimPlayer spec={spec} />;
}

function SpecSimPlayer({ spec }) {
  const [speed, setSpeed] = useState(1);

  // Initialize parameters from spec.params
  const initialParams = useMemo(() => {
    const p = {};
    for (const item of (spec.params || [])) {
      p[item.name] = Number(item.value ?? item.default ?? item.min ?? 0);
    }
    return p;
  }, [spec]);

  const [params, setParams] = useState(initialParams);
  const [isRunning, setIsRunning] = useState(true);
  // Teaching overlays: on/off per student, defaults from the spec's "overlays"
  const [overlays, setOverlays] = useState(() => ({
    fbd: Boolean(spec.overlays?.fbd), energy: Boolean(spec.overlays?.energy),
    momentum: Boolean(spec.overlays?.momentum), stress: Boolean(spec.overlays?.stress),
  }));
  const overlaysRef = useRef(overlays);
  overlaysRef.current = overlays;
  const [isUnstable, setIsUnstable] = useState(false);
  const [readoutsData, setReadoutsData] = useState([]);
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  // Sync params when spec changes
  useEffect(() => {
    setParams(initialParams);
    setIsUnstable(false);
  }, [initialParams]);

  const handleParamChange = (name, val) => {
    setParams(prev => ({ ...prev, [name]: Number(val) }));
  };

  // Compile expressions once or when spec changes; a bad expression evaluates to 0 and is reported
  const compileErrors = [];
  const compile = (expr, fallback = 0) => {
    const [fn, err] = tryCompile(expr ?? fallback, fallback);
    if (err) compileErrors.push(err);
    return fn;
  };
  const compiledSpec = useMemo(() => {
    const isParticles = spec.kind === 'particles';
    const compiled = { kind: spec.kind };

    if (isParticles) {
      const world = spec.world || {};
      compiled.world = {
        width: Number(world.width) || 10,
        height: Number(world.height) || 6,
        ground: Boolean(world.ground),
        walls: Boolean(world.walls),
        collisions: world.collisions !== false,
        gravity: world.gravity ? compile(world.gravity) : () => 0,
        restitution: world.restitution ? compile(world.restitution) : () => 0.8
      };

      compiled.bodies = (spec.bodies || []).map(b => ({
        id: b.id,
        label: b.label || b.id,
        color: b.color || 'gold',
        fixed: Boolean(b.fixed),
        trail: Boolean(b.trail),
        x: compile(b.x ?? 0),
        y: compile(b.y ?? 0),
        vx: compile(b.vx ?? 0),
        vy: compile(b.vy ?? 0),
        mass: compile(b.mass ?? 1),
        radius: compile(b.radius ?? 0.2)
      }));

      compiled.forces = (spec.forces || []).map(f => {
        const cf = { type: f.type, a: f.a, b: f.b, body: f.body, bodies: f.bodies };
        if (f.type === 'spring') {
          cf.k = compile(f.k ?? 10);
          cf.rest = compile(f.rest ?? 1);
          cf.damping = f.damping ? compile(f.damping) : () => 0;
        } else if (f.type === 'drag') {
          cf.coef = compile(f.coef ?? 0.1);
          cf.power = f.power !== undefined ? compile(f.power) : () => 1;
        } else if (f.type === 'gravitation') {
          cf.G = compile(f.G ?? 10);
          cf.soften = f.soften !== undefined ? compile(f.soften) : () => 0.05;
        } else if (f.type === 'custom' || f.type === 'uniform') {
          cf.fx = compile(f.fx ?? 0);
          cf.fy = compile(f.fy ?? 0);
        }
        return cf;
      });

      compiled.links = (spec.links || []).map(l => ({
        type: l.type,
        a: l.a,
        b: l.b,
        length: l.length !== undefined ? compile(l.length) : null
      }));

      compiled.vectors = (spec.vectors || []).map(v => ({
        body: v.body,
        x: compile(v.x ?? 0),
        y: compile(v.y ?? 0),
        scale: Number(v.scale) || 0.2,
        label: v.label || '',
        color: v.color || 'cyan'
      }));

      compiled.readouts = (spec.readouts || []).map(r => ({
        label: r.label,
        expr: compile(r.expr ?? 0),
        unit: r.unit || ''
      }));

      compiled.series = (spec.series || []).map(s => ({
        label: s.label,
        expr: compile(s.expr ?? 0),
        color: s.color || 'gold'
      }));
    } else if (spec.kind === 'graph') {
      const x = spec.x || {};
      compiled.x = {
        min: Number(x.min) || 0,
        max: Number(x.max) || 10,
        label: x.label || 'x'
      };
      const y = spec.y || {};
      compiled.y = {
        min: y.min !== undefined ? Number(y.min) : null,
        max: y.max !== undefined ? Number(y.max) : null,
        label: y.label || 'y'
      };
      compiled.animate = Boolean(spec.animate);
      // Generated specs sometimes plot "position vs time" with the curves written in t, not x.
      // If no curve uses x and the x-axis is time, plot t along the axis with a moving "now" marker.
      compiled.timeAxis = !(spec.curves || []).some((c) => /\bx\b/.test(String(c.expr)))
        && /\btime\b|\bt\b/i.test(compiled.x.label);
      compiled.curves = (spec.curves || []).map(c => ({
        expr: compile(c.expr ?? 0),
        label: c.label || '',
        color: c.color || 'gold'
      }));
    }

    compiled.errors = compileErrors.slice();
    return compiled;
  }, [spec]);

  // Simulation run state ref
  const simStateRef = useRef({
    t: 0,
    bodies: {},
    trails: {},
    seriesHistory: [],
    lastUiUpdate: 0,
    lastFrameTime: null
  });

  // Helper to initialize or reset particle bodies
  const initParticles = useCallback(() => {
    simStateRef.current.yRange = null;
    if (compiledSpec.kind !== 'particles') { simStateRef.current.t = 0; return; }
    const scope = { ...params, t: 0 };
    const bodies = {};
    const trails = {};

    for (const b of compiledSpec.bodies) {
      const m = Math.max(0.0001, b.mass(scope));
      const r = Math.max(0.02, b.radius(scope));
      const x = b.x(scope);
      const y = b.y(scope);
      const vx = b.fixed ? 0 : b.vx(scope);
      const vy = b.fixed ? 0 : b.vy(scope);
      bodies[b.id] = {
        id: b.id,
        label: b.label,
        color: b.color,
        fixed: b.fixed,
        trail: b.trail,
        m,
        r,
        x,
        y,
        vx,
        vy
      };
      if (b.trail) {
        trails[b.id] = [{ x, y }];
      }
    }

    simStateRef.current.t = 0;
    simStateRef.current.view = null;
    simStateRef.current.E0 = null;
    simStateRef.current.pMax = 0;
    simStateRef.current.forceLog = {};
    simStateRef.current.rodTension = [];
    simStateRef.current.yRange = null;
    simStateRef.current.bodies = bodies;
    simStateRef.current.trails = trails;
    simStateRef.current.seriesHistory = [];
    simStateRef.current.lastFrameTime = null;
    setIsUnstable(false);
  }, [compiledSpec, params]);

  // Reset when params or spec change
  useEffect(() => {
    initParticles();
  }, [initParticles]);

  const handleReset = () => {
    initParticles();
    setIsRunning(true);
  };

  // Main simulation & render loop
  useEffect(() => {
    let animId;

    const render = (currentTime) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const palette = canvasPalette();
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
      ctx.fillStyle = palette['surface'] || '#121212';
      ctx.fillRect(0, 0, W, H);

      // Compute frame delta
      if (!simStateRef.current.lastFrameTime) {
        simStateRef.current.lastFrameTime = currentTime;
      }
      const rawDt = (currentTime - simStateRef.current.lastFrameTime) / 1000;
      simStateRef.current.lastFrameTime = currentTime;
      const dt = Math.min(rawDt, 0.05) * speed;

      if (compiledSpec.kind === 'particles') {
        const state = simStateRef.current;
        const world = compiledSpec.world;

        // Physics substepping (240 Hz effective)
        if (isRunning && !isUnstable) {
          // ~1000 Hz: small scenes stay cheap, and rods/springs keep energy to well under 1%
          const substeps = Math.min(160, Math.max(1, Math.ceil(dt * 1000)));
          const subDt = dt / substeps;

          for (let step = 0; step < substeps; step++) {
            // Build current scope
            const scope = { ...params, t: state.t };
            for (const id in state.bodies) {
              const b = state.bodies[id];
              scope[id] = {
                x: b.x,
                y: b.y,
                vx: b.vx,
                vy: b.vy,
                m: b.m,
                r: b.r,
                speed: Math.hypot(b.vx, b.vy)
              };
            }

            const gVal = world.gravity(scope);
            const restVal = Math.min(1, Math.max(0, world.restitution(scope)));

            // 1. Accumulate forces (each one is also logged by source for the free-body diagram)
            const fx = {};
            const fy = {};
            const forceLog = {};
            const logF = (id, label, x, y) => { if (x || y) (forceLog[id] || (forceLog[id] = [])).push({ label, x, y }); };
            for (const id in state.bodies) {
              fx[id] = 0;
              fy[id] = 0;
              const b = state.bodies[id];
              if (!b.fixed) {
                fy[id] -= b.m * gVal;
                logF(id, 'W', 0, -b.m * gVal);
              }
            }

            for (const f of compiledSpec.forces) {
              if (f.type === 'spring') {
                const bA = state.bodies[f.a];
                const bB = state.bodies[f.b];
                if (bA && bB) {
                  const dx = bB.x - bA.x;
                  const dy = bB.y - bA.y;
                  const dist = Math.hypot(dx, dy);
                  if (dist > 1e-6) {
                    const nx = dx / dist;
                    const ny = dy / dist;
                    const k = f.k(scope);
                    const rest = f.rest(scope);
                    const damping = f.damping(scope);
                    const delta = dist - rest;
                    const Fs = -k * delta;
                    const dvx = bB.vx - bA.vx;
                    const dvy = bB.vy - bA.vy;
                    const vRelAxial = dvx * nx + dvy * ny;
                    const Fd = -damping * vRelAxial;
                    const Ftotal = Fs + Fd;
                    if (!bB.fixed) {
                      fx[bB.id] += Ftotal * nx;
                      fy[bB.id] += Ftotal * ny;
                      logF(bB.id, 'Fs', Ftotal * nx, Ftotal * ny);
                    }
                    if (!bA.fixed) {
                      fx[bA.id] -= Ftotal * nx;
                      fy[bA.id] -= Ftotal * ny;
                      logF(bA.id, 'Fs', -Ftotal * nx, -Ftotal * ny);
                    }
                  }
                }
              } else if (f.type === 'drag') {
                const b = state.bodies[f.body];
                if (b && !b.fixed) {
                  const coef = f.coef(scope);
                  const pwr = f.power(scope);
                  const spd = Math.hypot(b.vx, b.vy);
                  if (spd > 1e-6) {
                    const mag = coef * Math.pow(spd, pwr);
                    fx[b.id] -= mag * (b.vx / spd);
                    fy[b.id] -= mag * (b.vy / spd);
                    logF(b.id, 'D', -mag * (b.vx / spd), -mag * (b.vy / spd));
                  }
                }
              } else if (f.type === 'gravitation') {
                const G = f.G(scope);
                const soften = f.soften(scope);
                const ids = Object.keys(state.bodies);
                for (let i = 0; i < ids.length; i++) {
                  for (let j = i + 1; j < ids.length; j++) {
                    const b1 = state.bodies[ids[i]];
                    const b2 = state.bodies[ids[j]];
                    if (b1.fixed && b2.fixed) continue;
                    const dx = b2.x - b1.x;
                    const dy = b2.y - b1.y;
                    const distSq = dx * dx + dy * dy + soften * soften;
                    const dist = Math.sqrt(distSq);
                    const F = (G * b1.m * b2.m) / distSq;
                    const fxPair = F * (dx / dist);
                    const fyPair = F * (dy / dist);
                    if (!b1.fixed) { fx[b1.id] += fxPair; fy[b1.id] += fyPair; logF(b1.id, 'Fg', fxPair, fyPair); }
                    if (!b2.fixed) { fx[b2.id] -= fxPair; fy[b2.id] -= fyPair; logF(b2.id, 'Fg', -fxPair, -fyPair); }
                  }
                }
              } else if (f.type === 'custom') {
                const b = state.bodies[f.body];
                if (b && !b.fixed) {
                  const bScope = { ...scope, x: b.x, y: b.y, vx: b.vx, vy: b.vy, m: b.m };
                  const cfx = f.fx(bScope), cfy = f.fy(bScope);
                  fx[b.id] += cfx;
                  fy[b.id] += cfy;
                  logF(b.id, 'F', cfx, cfy);
                }
              } else if (f.type === 'uniform') {
                const fxVal = f.fx(scope);
                const fyVal = f.fy(scope);
                const targetIds = f.bodies || Object.keys(state.bodies);
                for (const bid of targetIds) {
                  const b = state.bodies[bid];
                  if (b && !b.fixed) {
                    fx[bid] += fxVal;
                    fy[bid] += fyVal;
                    logF(bid, 'F', fxVal, fyVal);
                  }
                }
              }
            }

            // 1b. Rods with one fixed end: apply the exact tension as a force before integrating,
            //     T = (other forces).n + m v_t^2 / L, so the bob stays on its circle without the
            //     energy loss of correcting position afterwards (projection below only fixes drift).
            state.rodTension = compiledSpec.links.map((l) => {
              const a = state.bodies[l.a], bb = state.bodies[l.b];
              if (!a || !bb || a.fixed === bb.fixed) return null;
              const [pivot, bob] = a.fixed ? [a, bb] : [bb, a];
              const dx = bob.x - pivot.x, dy = bob.y - pivot.y;
              const L = Math.hypot(dx, dy);
              if (L < 1e-9) return null;
              const nx = dx / L, ny = dy / L;
              const vr = bob.vx * nx + bob.vy * ny;
              const vt2 = Math.max(0, bob.vx * bob.vx + bob.vy * bob.vy - vr * vr);
              const T = fx[bob.id] * nx + fy[bob.id] * ny + (bob.m * vt2) / L;
              fx[bob.id] -= T * nx;
              fy[bob.id] -= T * ny;
              logF(bob.id, 'T', -T * nx, -T * ny);
              return T;
            });

            // 2. Integration step
            const prevPos = {};
            for (const id in state.bodies) {
              const b = state.bodies[id];
              prevPos[id] = { x: b.x, y: b.y };
            }

            let exploded = false;
            for (const id in state.bodies) {
              const b = state.bodies[id];
              if (!b.fixed) {
                const ax = fx[id] / b.m;
                const ay = fy[id] / b.m;
                b.vx += ax * subDt;
                b.vy += ay * subDt;
                b.x += b.vx * subDt;
                b.y += b.vy * subDt;

                if (!isFinite(b.x) || !isFinite(b.y) || isNaN(b.vx) || isNaN(b.vy) || Math.abs(b.x) > 1e4 || Math.abs(b.y) > 1e4) {
                  exploded = true;
                  break;
                }
              }
            }

            if (exploded) {
              setIsUnstable(true);
              setIsRunning(false);
              break;
            }

            // 3. XPBD Distance constraints (links: rod)
            const rodBodies = new Set();
            for (const l of compiledSpec.links) {
              rodBodies.add(l.a);
              rodBodies.add(l.b);
            }

            for (let iter = 0; iter < 8; iter++) {
              for (const l of compiledSpec.links) {
                const bA = state.bodies[l.a];
                const bB = state.bodies[l.b];
                if (!bA || !bB) continue;
                const targetLen = l.length !== null ? l.length(scope) : Math.hypot(bB.x - bA.x, bB.y - bA.y);
                const dx = bB.x - bA.x;
                const dy = bB.y - bA.y;
                const dist = Math.hypot(dx, dy);
                if (dist > 1e-6) {
                  const diff = (dist - targetLen) / dist;
                  if (bA.fixed && !bB.fixed) {
                    bB.x -= dx * diff;
                    bB.y -= dy * diff;
                  } else if (bB.fixed && !bA.fixed) {
                    bA.x += dx * diff;
                    bA.y += dy * diff;
                  } else if (!bA.fixed && !bB.fixed) {
                    const invA = 1 / bA.m;
                    const invB = 1 / bB.m;
                    const sumInv = invA + invB;
                    bA.x += dx * diff * (invA / sumInv);
                    bA.y += dy * diff * (invA / sumInv);
                    bB.x -= dx * diff * (invB / sumInv);
                    bB.y -= dy * diff * (invB / sumInv);
                  }
                }
              }
            }

            // XPBD Velocity Projection: Update velocity from post-relaxation displacement
            // v = (x - x_prev) / dt (eliminates phantom momentum & energy drift in linkages)
            for (const id of rodBodies) {
              const b = state.bodies[id];
              if (b && !b.fixed && prevPos[id]) {
                b.vx = (b.x - prevPos[id].x) / subDt;
                b.vy = (b.y - prevPos[id].y) / subDt;
              }
            }

            // 3b. Collisions: circle-circle, and circles against rods (impulse shared along the rod by the
            //     lever rule; a fixed end takes none). Restitution comes from world.restitution.
            if (world.collisions) {
              const ids = Object.keys(state.bodies);
              const invM = (b) => (b.fixed ? 0 : 1 / b.m);
              const linked = new Set(compiledSpec.links.flatMap((l) => [`${l.a}|${l.b}`, `${l.b}|${l.a}`]));
              for (let i = 0; i < ids.length; i++) {
                for (let j = i + 1; j < ids.length; j++) {
                  const p = state.bodies[ids[i]];
                  const q = state.bodies[ids[j]];
                  if ((p.fixed && q.fixed) || linked.has(`${p.id}|${q.id}`)) continue;
                  const dx = q.x - p.x, dy = q.y - p.y;
                  const dist = Math.hypot(dx, dy);
                  const overlap = p.r + q.r - dist;
                  if (overlap <= 0 || dist < 1e-9) continue;
                  const nx = dx / dist, ny = dy / dist;
                  const wSum = invM(p) + invM(q);
                  if (wSum === 0) continue;
                  p.x -= nx * overlap * (invM(p) / wSum); p.y -= ny * overlap * (invM(p) / wSum);
                  q.x += nx * overlap * (invM(q) / wSum); q.y += ny * overlap * (invM(q) / wSum);
                  const vn = (q.vx - p.vx) * nx + (q.vy - p.vy) * ny;
                  if (vn < 0) {
                    const J = (-(1 + restVal) * vn) / wSum;
                    if (!p.fixed) { p.vx -= J * nx * invM(p); p.vy -= J * ny * invM(p); }
                    if (!q.fixed) { q.vx += J * nx * invM(q); q.vy += J * ny * invM(q); }
                  }
                }
              }
              for (const l of compiledSpec.links) {
                const a = state.bodies[l.a];
                const bEnd = state.bodies[l.b];
                if (!a || !bEnd) continue;
                const sx = bEnd.x - a.x, sy = bEnd.y - a.y;
                const segLen2 = sx * sx + sy * sy;
                if (segLen2 < 1e-12) continue;
                for (const id of ids) {
                  const c = state.bodies[id];
                  if (c === a || c === bEnd || c.fixed) continue;
                  const u = Math.max(0, Math.min(1, ((c.x - a.x) * sx + (c.y - a.y) * sy) / segLen2));
                  if (u <= 0.02 || u >= 0.98) continue;  // near the ends the circle-circle step handles it
                  const px = a.x + u * sx, py = a.y + u * sy;
                  const dx = c.x - px, dy = c.y - py;
                  const dist = Math.hypot(dx, dy);
                  const overlap = c.r + 0.03 - dist;
                  if (overlap <= 0 || dist < 1e-9) continue;
                  const nx = dx / dist, ny = dy / dist;
                  // rod velocity at the contact point and its effective inverse mass there
                  const rvx = (1 - u) * a.vx + u * bEnd.vx, rvy = (1 - u) * a.vy + u * bEnd.vy;
                  const wRod = (1 - u) * (1 - u) * invM(a) + u * u * invM(bEnd);
                  const wSum = invM(c) + wRod;
                  c.x += nx * overlap; c.y += ny * overlap;
                  const vn = (c.vx - rvx) * nx + (c.vy - rvy) * ny;
                  if (vn < 0 && wSum > 0) {
                    const J = (-(1 + restVal) * vn) / wSum;
                    c.vx += J * nx * invM(c); c.vy += J * ny * invM(c);
                    if (!a.fixed) { a.vx -= J * nx * (1 - u) * invM(a); a.vy -= J * ny * (1 - u) * invM(a); }
                    if (!bEnd.fixed) { bEnd.vx -= J * nx * u * invM(bEnd); bEnd.vy -= J * ny * u * invM(bEnd); }
                  }
                }
              }
            }

            // 4. Ground and walls
            for (const id in state.bodies) {
              const b = state.bodies[id];
              if (!b.fixed) {
                if (world.ground && b.y - b.r <= 1e-3 && fy[id] < 0) {
                  logF(id, 'N', 0, -fy[id]);  // the ground pushes back on whatever presses into it
                }
                if (world.ground && b.y - b.r < 0) {
                  b.y = b.r;
                  if (b.vy < 0) {
                    b.vy = -b.vy * restVal;
                    b.vx *= 0.98;
                  }
                }
                if (world.walls) {
                  if (b.x - b.r < 0) {
                    b.x = b.r;
                    if (b.vx < 0) b.vx = -b.vx * restVal;
                  }
                  if (b.x + b.r > world.width) {
                    b.x = world.width - b.r;
                    if (b.vx > 0) b.vx = -b.vx * restVal;
                  }
                }
              }
            }

            state.t += subDt;
            state.forceLog = forceLog;
          }

          // Append trail points
          for (const id in state.bodies) {
            const b = state.bodies[id];
            if (b.trail && state.trails[id]) {
              const tr = state.trails[id];
              const last = tr[tr.length - 1];
              if (!last || Math.hypot(b.x - last.x, b.y - last.y) > 0.04) {
                tr.push({ x: b.x, y: b.y });
                if (tr.length > 250) tr.shift();
              }
            }
          }

          // Record series
          if (compiledSpec.series.length > 0) {
            const scope = { ...params, t: state.t };
            for (const id in state.bodies) {
              const b = state.bodies[id];
              scope[id] = { x: b.x, y: b.y, vx: b.vx, vy: b.vy, m: b.m, r: b.r, speed: Math.hypot(b.vx, b.vy) };
            }
            const pt = { t: state.t };
            for (const s of compiledSpec.series) {
              pt[s.label] = s.expr(scope);
            }
            state.seriesHistory.push(pt);
            const cutoff = state.t - 12;
            state.seriesHistory = state.seriesHistory.filter(p => p.t >= cutoff);
          }
        }

        // --- DRAW PARTICLES WORLD ---
        const padX = 36;
        const padY = 36;
        const chartStrip = compiledSpec.series.length > 0 ? 96 : 0;
        const availableW = Math.max(10, W - padX * 2);
        const availableH = Math.max(10, H - padY * 2 - chartStrip);
        // Camera: the world box, grown during a run to keep bodies in sight (up to 2.5x the world size)
        if (!state.view) state.view = { minX: 0, maxX: world.width, minY: 0, maxY: world.height };
        const vb = state.view;
        const limX = world.width * 0.75, limY = world.height * 0.75;
        for (const id in state.bodies) {
          const b = state.bodies[id];
          if (!isFinite(b.x) || !isFinite(b.y)) continue;
          vb.minX = Math.max(-limX, Math.min(vb.minX, b.x - b.r - 0.2));
          vb.maxX = Math.min(world.width + limX, Math.max(vb.maxX, b.x + b.r + 0.2));
          vb.minY = Math.max(-limY, Math.min(vb.minY, b.y - b.r - 0.2));
          vb.maxY = Math.min(world.height + limY, Math.max(vb.maxY, b.y + b.r + 0.2));
        }
        const viewW = vb.maxX - vb.minX, viewH = vb.maxY - vb.minY;
        const scale = Math.min(availableW / viewW, availableH / viewH);
        const originX = padX + (availableW - viewW * scale) / 2 - vb.minX * scale;
        const originY = H - chartStrip - (padY + (availableH - viewH * scale) / 2) + vb.minY * scale;

        const wX = (x) => originX + x * scale;
        const wY = (y) => originY - y * scale;
        const wR = (r) => Math.max(3, r * scale);

        // Everything in the world stays above the live-chart strip
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, W, H - chartStrip);
        ctx.clip();

        // World background box & grid
        ctx.strokeStyle = palette['rule'] || '#252827';
        ctx.lineWidth = 1;
        ctx.strokeRect(originX, originY - world.height * scale, world.width * scale, world.height * scale);

        // Subtle grid
        ctx.beginPath();
        const gridStep = Math.max(1, Math.round(world.width / 8));
        for (let gx = 0; gx <= world.width; gx += gridStep) {
          ctx.moveTo(wX(gx), wY(0));
          ctx.lineTo(wX(gx), wY(world.height));
        }
        for (let gy = 0; gy <= world.height; gy += gridStep) {
          ctx.moveTo(wX(0), wY(gy));
          ctx.lineTo(wX(world.width), wY(gy));
        }
        ctx.strokeStyle = palette['sunk'] || 'rgba(255, 255, 255, 0.04)';
        ctx.stroke();

        // Ground line
        if (world.ground) {
          ctx.beginPath();
          ctx.moveTo(wX(Math.min(0, vb.minX)), wY(0));
          ctx.lineTo(wX(Math.max(world.width, vb.maxX)), wY(0));
          ctx.strokeStyle = palette['rule-strong'] || '#444a47';
          ctx.lineWidth = 3;
          ctx.stroke();

          // Ground hash marks
          ctx.strokeStyle = palette['rule'] || 'rgba(255, 255, 255, 0.1)';
          ctx.lineWidth = 1;
          for (let gx = Math.min(0, vb.minX); gx < Math.max(world.width, vb.maxX); gx += Math.max(0.4, viewW / 60)) {
            ctx.beginPath();
            ctx.moveTo(wX(gx), wY(0));
            ctx.lineTo(wX(gx) - 8, wY(0) + 10);
            ctx.stroke();
          }
        }

        // Walls
        if (world.walls) {
          ctx.strokeStyle = palette['rule-strong'] || '#444a47';
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.moveTo(wX(0), wY(0));
          ctx.lineTo(wX(0), wY(world.height));
          ctx.moveTo(wX(world.width), wY(0));
          ctx.lineTo(wX(world.width), wY(world.height));
          ctx.stroke();
        }

        // Draw Links (rod)
        for (const l of compiledSpec.links) {
          const bA = state.bodies[l.a];
          const bB = state.bodies[l.b];
          if (bA && bB) {
            ctx.beginPath();
            ctx.moveTo(wX(bA.x), wY(bA.y));
            ctx.lineTo(wX(bB.x), wY(bB.y));
            ctx.strokeStyle = palette['ink-soft'] || 'rgba(200, 205, 210, 0.55)';
            ctx.lineWidth = 4;
            ctx.lineCap = 'round';
            ctx.stroke();

            // Link pin rivets
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(wX(bA.x), wY(bA.y), 2.5, 0, Math.PI * 2);
            ctx.arc(wX(bB.x), wY(bB.y), 2.5, 0, Math.PI * 2);
            ctx.fill();
          }
        }

        // Draw Springs
        for (const f of compiledSpec.forces) {
          if (f.type === 'spring') {
            const bA = state.bodies[f.a];
            const bB = state.bodies[f.b];
            if (bA && bB) {
              const x1 = wX(bA.x), y1 = wY(bA.y);
              const x2 = wX(bB.x), y2 = wY(bB.y);
              const dx = x2 - x1, dy = y2 - y1;
              const len = Math.hypot(dx, dy);
              if (len > 10) {
                const angle = Math.atan2(dy, dx);
                ctx.save();
                ctx.translate(x1, y1);
                ctx.rotate(angle);
                ctx.beginPath();
                ctx.moveTo(0, 0);
                const coils = 12;
                const lead = 15;
                const coilLen = Math.max(10, len - lead * 2);
                ctx.lineTo(lead, 0);
                for (let c = 0; c < coils; c++) {
                  const cx = lead + (c + 0.5) * (coilLen / coils);
                  const cy = (c % 2 === 0 ? -1 : 1) * 7;
                  ctx.lineTo(cx, cy);
                }
                ctx.lineTo(len - lead, 0);
                ctx.lineTo(len, 0);
                ctx.strokeStyle = palette['muted'] || '#888888';
                ctx.lineWidth = 2;
                ctx.stroke();
                ctx.restore();
              }
            }
          }
        }

        // Draw Trails
        for (const id in state.trails) {
          const pts = state.trails[id];
          if (pts && pts.length > 1) {
            const b = state.bodies[id];
            const col = resolveColor(b?.color, palette);
            ctx.save();
            ctx.strokeStyle = col;
            ctx.lineWidth = 2;
            for (let i = 1; i < pts.length; i++) {
              const alpha = (i / pts.length) * 0.7;
              ctx.globalAlpha = alpha;
              ctx.beginPath();
              ctx.moveTo(wX(pts[i - 1].x), wY(pts[i - 1].y));
              ctx.lineTo(wX(pts[i].x), wY(pts[i].y));
              ctx.stroke();
            }
            ctx.restore();
          }
        }

        // Draw Bodies
        for (const id in state.bodies) {
          const b = state.bodies[id];
          const cx = wX(b.x);
          const cy = wY(b.y);
          const rad = wR(b.r);
          const col = resolveColor(b.color, palette);

          // Glow / fill
          const grad = ctx.createRadialGradient(cx - rad * 0.3, cy - rad * 0.3, rad * 0.1, cx, cy, rad);
          grad.addColorStop(0, '#ffffff');
          grad.addColorStop(0.35, col);
          grad.addColorStop(1, col);

          ctx.beginPath();
          ctx.arc(cx, cy, rad, 0, Math.PI * 2);
          ctx.fillStyle = grad;
          ctx.fill();
          ctx.lineWidth = 1.5;
          ctx.strokeStyle = palette['ink'] || 'rgba(0, 0, 0, 0.6)';
          ctx.stroke();

          // Anchor mark for fixed bodies
          if (b.fixed) {
            ctx.strokeStyle = palette['ink'] || '#000000';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(cx - rad * 0.6, cy);
            ctx.lineTo(cx + rad * 0.6, cy);
            ctx.moveTo(cx, cy - rad * 0.6);
            ctx.lineTo(cx, cy + rad * 0.6);
            ctx.stroke();
          }

          // Label
          if (b.label && b.label !== b.id) {
            ctx.fillStyle = palette['ink-soft'] || '#a8aca9';
            ctx.font = '10px "IBM Plex Mono", "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(b.label, cx, cy - rad - 5);
          }
        }

        // Draw Vectors
        for (const v of compiledSpec.vectors) {
          const b = state.bodies[v.body];
          if (b) {
            const scope = { ...params, t: state.t };
            for (const id in state.bodies) {
              const bd = state.bodies[id];
              scope[id] = { x: bd.x, y: bd.y, vx: bd.vx, vy: bd.vy, m: bd.m, r: bd.r, speed: Math.hypot(bd.vx, bd.vy) };
            }
            const vxVal = v.x(scope);
            const vyVal = v.y(scope);
            const mag = Math.hypot(vxVal, vyVal);
            if (mag > 0.05) {
              const startX = wX(b.x);
              const startY = wY(b.y);
              const arrowLen = mag * v.scale * scale;
              const angle = Math.atan2(-vyVal, vxVal); // -vy because y is inverted on canvas
              const endX = startX + Math.cos(angle) * arrowLen;
              const endY = startY + Math.sin(angle) * arrowLen;

              const col = resolveColor(v.color, palette);
              ctx.strokeStyle = col;
              ctx.fillStyle = col;
              ctx.lineWidth = 2;
              ctx.beginPath();
              ctx.moveTo(startX, startY);
              ctx.lineTo(endX, endY);
              ctx.stroke();

              // Arrow head
              ctx.beginPath();
              ctx.moveTo(endX, endY);
              ctx.lineTo(endX - 7 * Math.cos(angle - Math.PI / 6), endY - 7 * Math.sin(angle - Math.PI / 6));
              ctx.lineTo(endX - 7 * Math.cos(angle + Math.PI / 6), endY - 7 * Math.sin(angle + Math.PI / 6));
              ctx.closePath();
              ctx.fill();

              if (v.label) {
                ctx.font = '11px "IBM Plex Mono", "JetBrains Mono", monospace';
                ctx.fillText(v.label, endX + 6, endY - 4);
              }
            }
          }
        }

        // ---------------- Teaching overlays ----------------
        const ov = overlaysRef.current;
        const oScope = { ...params, t: state.t };
        for (const id in state.bodies) {
          const b = state.bodies[id];
          oScope[id] = { x: b.x, y: b.y, vx: b.vx, vy: b.vy, m: b.m, r: b.r, speed: Math.hypot(b.vx, b.vy) };
        }
        const monoFont = '11px "IBM Plex Mono", "JetBrains Mono", monospace';
        const arrow = (x0, y0, x1, y1, color, label, width = 2) => {
          const ang = Math.atan2(y1 - y0, x1 - x0);
          ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = width;
          ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x1 - 8 * Math.cos(ang - 0.45), y1 - 8 * Math.sin(ang - 0.45));
          ctx.lineTo(x1 - 8 * Math.cos(ang + 0.45), y1 - 8 * Math.sin(ang + 0.45));
          ctx.closePath(); ctx.fill();
          if (label) { ctx.font = monoFont; ctx.textAlign = 'left'; ctx.fillText(label, x1 + 5, y1 - 5); }
        };

        // Stress: springs and rods colored by strain / tension (red = tension, blue = compression)
        if (ov.stress) {
          const strainColor = (e) => {
            const k = Math.min(1, Math.abs(e) / 0.25);
            return e >= 0 ? `rgba(196, 48, 43, ${0.35 + 0.65 * k})` : `rgba(37, 99, 160, ${0.35 + 0.65 * k})`;
          };
          let maxStrain = 0;
          compiledSpec.forces.forEach((f) => {
            if (f.type !== 'spring') return;
            const a = state.bodies[f.a], bb = state.bodies[f.b];
            if (!a || !bb) return;
            const rest = Math.max(1e-6, f.rest(oScope));
            const strain = (Math.hypot(bb.x - a.x, bb.y - a.y) - rest) / rest;
            if (Math.abs(strain) > Math.abs(maxStrain)) maxStrain = strain;
            ctx.strokeStyle = strainColor(strain);
            ctx.lineWidth = 5;
            ctx.beginPath(); ctx.moveTo(wX(a.x), wY(a.y)); ctx.lineTo(wX(bb.x), wY(bb.y)); ctx.stroke();
          });
          const tensions = (state.rodTension || []).filter((t) => t !== null && isFinite(t));
          const tMax = Math.max(1e-6, ...tensions.map(Math.abs));
          compiledSpec.links.forEach((l, i) => {
            const T = state.rodTension?.[i];
            const a = state.bodies[l.a], bb = state.bodies[l.b];
            if (T === null || T === undefined || !a || !bb) return;
            ctx.strokeStyle = strainColor((T / tMax) * 0.25);
            ctx.lineWidth = 5;
            ctx.beginPath(); ctx.moveTo(wX(a.x), wY(a.y)); ctx.lineTo(wX(bb.x), wY(bb.y)); ctx.stroke();
            ctx.fillStyle = palette['ink'] || '#000';
            ctx.font = monoFont; ctx.textAlign = 'left';
            ctx.fillText(`T=${T.toFixed(1)} N`, (wX(a.x) + wX(bb.x)) / 2 + 8, (wY(a.y) + wY(bb.y)) / 2);
          });
          ctx.fillStyle = palette['ink-soft'] || '#555';
          ctx.font = monoFont; ctx.textAlign = 'left';
          ctx.fillText(`stress: red = tension, blue = compression${maxStrain ? `, max strain ${(maxStrain * 100).toFixed(1)}%` : ''}`, 12, H - chartStrip - 12);
        }

        // Free-body diagram: every force on each moving body, to scale with the largest one on screen
        if (ov.fbd) {
          const FBD_COLORS = { W: palette['gold-text'], N: palette['accent'], Fs: palette['info'], D: palette['bad'], T: palette['plum'], Fg: palette['gold-text'], F: palette['ink'] };
          const FBD_NAMES = { W: 'W (weight)', N: 'N (normal)', Fs: 'spring', D: 'drag', T: 'T (tension)', Fg: 'gravity', F: 'applied' };
          const log = state.forceLog || {};
          let fMax = 1e-9;
          for (const id in log) for (const f of log[id]) fMax = Math.max(fMax, Math.hypot(f.x, f.y));
          const used = new Set();
          for (const id in log) {
            const b = state.bodies[id];
            if (!b || b.fixed) continue;
            const cx = wX(b.x), cy = wY(b.y);
            for (const f of log[id]) {
              const mag = Math.hypot(f.x, f.y);
              if (mag < fMax * 0.02) continue;
              const len = 18 + (mag / fMax) * 72;
              arrow(cx, cy, cx + (f.x / mag) * len, cy - (f.y / mag) * len, FBD_COLORS[f.label] || palette['ink'], `${f.label} ${mag.toFixed(1)}N`, 2.5);
              used.add(f.label);
            }
          }
          // legend of the force types on screen
          let ly = 18;
          ctx.font = monoFont; ctx.textAlign = 'right';
          for (const label of used) {
            ctx.fillStyle = FBD_COLORS[label] || palette['ink'];
            ctx.fillText(FBD_NAMES[label] || label, W - 12, ly);
            ly += 15;
          }
        }

        // Momentum: total p of the moving bodies, drawn at their center of mass
        if (ov.momentum) {
          let px = 0, py = 0, mSum = 0, cmx = 0, cmy = 0;
          for (const id in state.bodies) {
            const b = state.bodies[id];
            if (b.fixed) continue;
            px += b.m * b.vx; py += b.m * b.vy; mSum += b.m; cmx += b.m * b.x; cmy += b.m * b.y;
          }
          if (mSum > 0) {
            cmx /= mSum; cmy /= mSum;
            const pMag = Math.hypot(px, py);
            state.pMax = Math.max(state.pMax || 0, pMag, 1e-9);
            const len = (pMag / state.pMax) * 90;
            ctx.fillStyle = palette['ink'] || '#000';
            ctx.beginPath(); ctx.arc(wX(cmx), wY(cmy), 4, 0, Math.PI * 2); ctx.fill();
            if (pMag > state.pMax * 0.01) {
              arrow(wX(cmx), wY(cmy), wX(cmx) + (px / pMag) * len, wY(cmy) - (py / pMag) * len, palette['gold'], 'p total', 3);
            }
            ctx.fillStyle = palette['ink'] || '#000';
            ctx.font = monoFont; ctx.textAlign = 'right';
            ctx.fillText(`p = (${px.toFixed(2)}, ${py.toFixed(2)}) kg m/s   |p| = ${pMag.toFixed(2)}`, W - 12, H - chartStrip - 12);
          }
        }

        // Energy: kinetic, gravitational, spring and total, with what has been lost since the start
        if (ov.energy) {
          const g = world.gravity(oScope);
          let KE = 0, PEg = 0, PEs = 0, PEgrav = 0;
          for (const id in state.bodies) {
            const b = state.bodies[id];
            if (b.fixed) continue;
            KE += 0.5 * b.m * (b.vx * b.vx + b.vy * b.vy);
            PEg += b.m * g * b.y;
          }
          for (const f of compiledSpec.forces) {
            if (f.type === 'spring') {
              const a = state.bodies[f.a], bb = state.bodies[f.b];
              if (a && bb) PEs += 0.5 * f.k(oScope) * (Math.hypot(bb.x - a.x, bb.y - a.y) - f.rest(oScope)) ** 2;
            } else if (f.type === 'gravitation') {
              const ids = Object.keys(state.bodies);
              for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
                const p1 = state.bodies[ids[i]], p2 = state.bodies[ids[j]];
                PEgrav -= (f.G(oScope) * p1.m * p2.m) / Math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2 + f.soften(oScope) ** 2);
              }
            }
          }
          const total = KE + PEg + PEs + PEgrav;
          if (state.E0 === null || state.E0 === undefined) state.E0 = total;
          const lost = state.E0 - total;
          const rows = [['KE', KE, palette['info']]];
          if (g !== 0 || compiledSpec.forces.some((f) => f.type === 'gravitation')) rows.push(['PE grav', PEg + PEgrav, palette['gold-text']]);
          if (PEs > 1e-9 || compiledSpec.forces.some((f) => f.type === 'spring')) rows.push(['PE spring', PEs, palette['plum']]);
          rows.push(['total', total, palette['ink']]);
          if (Math.abs(lost) > Math.abs(state.E0) * 0.005) rows.push(['lost', lost, palette['bad']]);
          const scaleE = Math.max(1e-9, ...rows.map((r) => Math.abs(r[1])));
          const bx = 12, by = 12, rowH = 17, barMax = 110;
          ctx.fillStyle = palette['surface'] || '#fff';
          ctx.globalAlpha = 0.9;
          ctx.fillRect(bx - 6, by - 6, 230, rows.length * rowH + 10);
          ctx.globalAlpha = 1;
          ctx.font = monoFont; ctx.textAlign = 'left';
          rows.forEach(([label, val, color], i) => {
            const yRow = by + i * rowH;
            ctx.fillStyle = palette['ink-soft'] || '#555';
            ctx.fillText(label, bx, yRow + 10);
            ctx.fillStyle = color || palette['ink'];
            const w = (Math.abs(val) / scaleE) * barMax;
            ctx.fillRect(bx + 72, yRow + 2, Math.max(1, w), 9);
            ctx.fillStyle = palette['ink'] || '#000';
            ctx.fillText(`${val.toFixed(1)} J`, bx + 76 + Math.max(1, w), yRow + 10);
          });
        }

        ctx.restore();

        // Draw mini live chart overlay for series
        if (compiledSpec.series.length > 0 && state.seriesHistory.length > 2) {
          const chartW = W - padX * 2;
          const chartH = chartStrip - 22;
          const chartX = padX;
          const chartY = H - chartH - 10;

          ctx.fillStyle = palette['sunk'] || 'rgba(18, 19, 19, 0.85)';
          ctx.strokeStyle = palette['rule'] || '#333';
          ctx.lineWidth = 1;
          ctx.fillRect(chartX, chartY, chartW, chartH);
          ctx.strokeRect(chartX, chartY, chartW, chartH);

          // Find y range
          let minVal = Infinity, maxVal = -Infinity;
          for (const pt of state.seriesHistory) {
            for (const s of compiledSpec.series) {
              const v = pt[s.label];
              if (isFinite(v)) {
                if (v < minVal) minVal = v;
                if (v > maxVal) maxVal = v;
              }
            }
          }
          if (maxVal <= minVal) { maxVal = minVal + 1; minVal -= 1; }
          const padVal = (maxVal - minVal) * 0.1;
          minVal -= padVal; maxVal += padVal;

          const tMin = state.t - 12;
          const tMax = state.t;

          for (const s of compiledSpec.series) {
            ctx.beginPath();
            let first = true;
            for (const pt of state.seriesHistory) {
              const val = pt[s.label];
              if (!isFinite(val)) continue;
              const px = chartX + ((pt.t - tMin) / (tMax - tMin || 1)) * chartW;
              const py = chartY + chartH - ((val - minVal) / (maxVal - minVal || 1)) * chartH;
              if (first) { ctx.moveTo(px, py); first = false; } else { ctx.lineTo(px, py); }
            }
            ctx.strokeStyle = resolveColor(s.color, palette);
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }

          // Series Legend
          ctx.font = '11px "IBM Plex Mono", "JetBrains Mono", monospace';
          let legX = chartX + 6;
          for (const s of compiledSpec.series) {
            ctx.fillStyle = resolveColor(s.color, palette);
            ctx.fillText(s.label, legX, chartY + 12);
            legX += ctx.measureText(s.label).width + 8;
          }
        }

        // Throttle UI readouts updates (~10 Hz)
        if (currentTime - state.lastUiUpdate > 100) {
          state.lastUiUpdate = currentTime;
          const scope = { ...params, t: state.t };
          for (const id in state.bodies) {
            const b = state.bodies[id];
            scope[id] = { x: b.x, y: b.y, vx: b.vx, vy: b.vy, m: b.m, r: b.r, speed: Math.hypot(b.vx, b.vy) };
          }
          const readouts = compiledSpec.readouts.map(r => {
            const val = r.expr(scope);
            return {
              label: r.label,
              unit: r.unit,
              value: isFinite(val) ? val.toFixed(2) : '—'
            };
          });
          setReadoutsData(readouts);
        }

      } else if (compiledSpec.kind === 'graph') {
        const state = simStateRef.current;
        if ((compiledSpec.animate || compiledSpec.timeAxis) && isRunning) {
          state.t += dt;
        }

        const margin = { top: 28, right: 36, bottom: 44, left: 54 };
        const graphW = Math.max(10, W - margin.left - margin.right);
        const graphH = Math.max(10, H - margin.top - margin.bottom);

        const xMin = compiledSpec.x.min;
        const xMax = compiledSpec.x.max;
        const numSamples = 400;

        // Sample curves
        const sampledCurves = compiledSpec.curves.map(c => {
          const points = [];
          for (let i = 0; i <= numSamples; i++) {
            const x = xMin + (i / numSamples) * (xMax - xMin);
            const val = c.expr({ ...params, x, t: compiledSpec.timeAxis ? x : state.t });
            points.push({ x, y: isFinite(val) ? val : NaN });
          }
          return { label: c.label, color: c.color, points };
        });

        // Determine y range
        let yMin = compiledSpec.y.min;
        let yMax = compiledSpec.y.max;
        if (yMin === null || yMax === null) {
          let autoMin = state.yRange ? state.yRange[0] : Infinity, autoMax = state.yRange ? state.yRange[1] : -Infinity;
          for (const c of sampledCurves) {
            for (const p of c.points) {
              if (!isNaN(p.y)) {
                if (p.y < autoMin) autoMin = p.y;
                if (p.y > autoMax) autoMax = p.y;
              }
            }
          }
          if (autoMax <= autoMin) { autoMax = autoMin + 1; autoMin -= 1; }
          state.yRange = [autoMin, autoMax];
          const pad = (autoMax - autoMin) * 0.12;
          if (yMin === null) yMin = autoMin - pad;
          if (yMax === null) yMax = autoMax + pad;
        }

        const gX = (x) => margin.left + ((x - xMin) / (xMax - xMin || 1)) * graphW;
        const gY = (y) => margin.top + graphH - ((y - yMin) / (yMax - yMin || 1)) * graphH;

        // Draw graph background & grid lines
        ctx.strokeStyle = palette['rule'] || '#252827';
        ctx.lineWidth = 1;
        ctx.strokeRect(margin.left, margin.top, graphW, graphH);

        // Grid lines & ticks
        const xStep = (xMax - xMin) / 8;
        ctx.font = '10px "IBM Plex Mono", "JetBrains Mono", monospace';
        ctx.fillStyle = palette['muted'] || '#747c78';
        ctx.textAlign = 'center';

        for (let i = 0; i <= 8; i++) {
          const xv = xMin + i * xStep;
          const px = gX(xv);
          ctx.beginPath();
          ctx.moveTo(px, margin.top);
          ctx.lineTo(px, margin.top + graphH);
          ctx.strokeStyle = palette['sunk'] || 'rgba(255, 255, 255, 0.05)';
          ctx.stroke();
          ctx.fillText(xv.toFixed(1), px, margin.top + graphH + 16);
        }

        const yStep = (yMax - yMin) / 6;
        ctx.textAlign = 'right';
        for (let i = 0; i <= 6; i++) {
          const yv = yMin + i * yStep;
          const py = gY(yv);
          ctx.beginPath();
          ctx.moveTo(margin.left, py);
          ctx.lineTo(margin.left + graphW, py);
          ctx.strokeStyle = palette['sunk'] || 'rgba(255, 255, 255, 0.05)';
          ctx.stroke();
          ctx.fillText(yv.toFixed(1), margin.left - 8, py + 3);
        }

        // Draw zero axes if in view
        if (yMin <= 0 && yMax >= 0) {
          ctx.strokeStyle = palette['rule-strong'] || '#444a47';
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(margin.left, gY(0));
          ctx.lineTo(margin.left + graphW, gY(0));
          ctx.stroke();
        }
        if (xMin <= 0 && xMax >= 0) {
          ctx.strokeStyle = palette['rule-strong'] || '#444a47';
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(gX(0), margin.top);
          ctx.lineTo(gX(0), margin.top + graphH);
          ctx.stroke();
        }

        // Axis Labels
        ctx.fillStyle = palette['ink-soft'] || '#a8aca9';
        ctx.textAlign = 'center';
        ctx.font = '11px "IBM Plex Mono", "JetBrains Mono", monospace';
        ctx.fillText(compiledSpec.x.label, margin.left + graphW / 2, margin.top + graphH + 34);

        ctx.save();
        ctx.translate(margin.left - 38, margin.top + graphH / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(compiledSpec.y.label, 0, 0);
        ctx.restore();

        // Draw Curves, clipped to the plot area so out-of-range values don't paint over labels
        ctx.save();
        ctx.beginPath();
        ctx.rect(margin.left, margin.top, graphW, graphH);
        ctx.clip();
        for (const c of sampledCurves) {
          const col = resolveColor(c.color, palette);
          ctx.strokeStyle = col;
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          let started = false;
          for (const p of c.points) {
            if (isNaN(p.y)) { started = false; continue; }
            const px = gX(p.x);
            const py = gY(p.y);
            if (!started) { ctx.moveTo(px, py); started = true; } else { ctx.lineTo(px, py); }
          }
          ctx.stroke();
        }
        ctx.restore();

        // Time-axis graphs: a "now" line sweeps across while playing, with a dot on each curve
        if (compiledSpec.timeAxis) {
          const span = xMax - xMin || 1;
          const now = xMin + (state.t % span);
          const nx = gX(now);
          ctx.strokeStyle = palette['gold'] || '#c9a24a';
          ctx.lineWidth = 1.5;
          ctx.setLineDash([4, 4]);
          ctx.beginPath(); ctx.moveTo(nx, margin.top); ctx.lineTo(nx, margin.top + graphH); ctx.stroke();
          ctx.setLineDash([]);
          for (const c of compiledSpec.curves) {
            const v = c.expr({ ...params, x: now, t: now });
            if (!isFinite(v) || v < yMin || v > yMax) continue;
            ctx.fillStyle = resolveColor(c.color, palette);
            ctx.beginPath(); ctx.arc(nx, gY(v), 5, 0, Math.PI * 2); ctx.fill();
          }
        }

        // Curve Legends at top-right
        let legX = margin.left + graphW - 12;
        ctx.textAlign = 'right';
        ctx.font = '11px "IBM Plex Mono", "JetBrains Mono", monospace';
        let legY = margin.top + 16;
        for (const c of sampledCurves) {
          const col = resolveColor(c.color, palette);
          ctx.fillStyle = col;
          ctx.fillText(`— ${c.label}`, legX, legY);
          legY += 16;
        }
      }

      ctx.restore();
      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [compiledSpec, params, isRunning, isUnstable, speed]);

  return (
    <section className="sim stack" ref={containerRef} aria-label={spec.title || 'Simulation'}>
      <div className="page-head" style={{ alignItems: 'flex-start' }}>
        <div style={{ minWidth: 0 }}>
          <h2 style={{ fontSize: '1.2rem' }}>{spec.title || 'Interactive simulation'}</h2>
          {spec.description && <p className="hint" style={{ marginTop: 6, maxWidth: '70ch', fontSize: '0.95rem' }}>{spec.description}</p>}
        </div>
        <div className="btn-row">
          <button type="button" className={`btn btn-sm ${isRunning ? 'btn-secondary' : 'btn-primary'}`} onClick={() => setIsRunning(!isRunning)}>
            {isRunning ? <><Pause size={14} aria-hidden="true" /> Pause</> : <><Play size={14} aria-hidden="true" /> Play</>}
          </button>
          <button type="button" className="btn btn-quiet btn-sm" onClick={handleReset}>
            <RotateCcw size={14} aria-hidden="true" /> Reset
          </button>
          <label className="visually-hidden" htmlFor="sim-speed">Speed</label>
          <select id="sim-speed" className="input btn-sm" style={{ width: 'auto', minHeight: 30, padding: '0 8px' }}
            value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
            {SPEEDS.map((v) => <option key={v} value={v}>{v}x speed</option>)}
          </select>
        </div>
      </div>

      {isUnstable && (
        <p className="notice notice-bad" role="alert">
          <AlertTriangle size={14} aria-hidden="true" /> The simulation became unstable (numbers ran off to infinity).
          Try smaller values or a lower speed, then Reset.
        </p>
      )}
      {compiledSpec.errors?.length > 0 && (
        <p className="notice notice-info">Some formulas in this simulation could not be read and count as 0: {compiledSpec.errors[0]}</p>
      )}

      <div className="sim-canvas" style={{ height: 420 }}>
        <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }}
          role="img" aria-label={spec.description || spec.title || 'Simulation canvas'} />
      </div>

      {compiledSpec.kind === 'particles' && (
        <div className="btn-row" role="group" aria-label="Overlays">
          {[['fbd', 'Forces (free-body)'], ['energy', 'Energy'], ['momentum', 'Momentum'], ['stress', 'Stress']].map(([key, label]) => (
            <label key={key} className="check-row" htmlFor={`ov-${key}`} style={{ marginRight: 'var(--space-3)' }}>
              <input id={`ov-${key}`} type="checkbox" checked={overlays[key]}
                onChange={(e) => setOverlays((o) => ({ ...o, [key]: e.target.checked }))} />
              <span>{label}</span>
            </label>
          ))}
        </div>
      )}

      {readoutsData.length > 0 && (
        <div className="readouts" role="status">
          {readoutsData.map((r, i) => (
            <span key={i}>{r.label} <b>{r.value}{r.unit ? ` ${r.unit}` : ''}</b></span>
          ))}
        </div>
      )}

      {spec.params && spec.params.length > 0 && (
        <div className="sliders">
          {spec.params.map((p) => {
            const val = params[p.name] ?? p.value ?? p.min;
            const digits = p.step && p.step < 1 ? Math.min(3, Math.ceil(-Math.log10(p.step))) : 1;
            return (
              <div key={p.name} className="slider">
                <label htmlFor={`param-${p.name}`}>
                  <span>{p.label || p.name}</span>
                  <b className="num">{Number(val).toFixed(digits)}{p.unit ? ` ${p.unit}` : ''}</b>
                </label>
                <input id={`param-${p.name}`} type="range" min={p.min} max={p.max} step={p.step || (p.max - p.min) / 100}
                  value={val} onChange={(e) => handleParamChange(p.name, e.target.value)} />
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
