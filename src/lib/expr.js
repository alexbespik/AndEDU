// ---------------------------------------------------------------------------
// Safe expression compiler for SimSpec simulations.
// Parses a small math grammar into closures — never eval/new Function — so specs
// written by agents are data only. Grammar mirrors simspec.py on the backend:
//   numbers, names, dotted names (ball.vx), + - * / % ^ (** alias), unary +/-,
//   comparisons < <= > >= == !=, parentheses, function calls.
// ---------------------------------------------------------------------------

import { Jet2 } from './dual_autodiff.js';

export { Jet2 };

export const CONSTS = {
  pi: Math.PI, PI: Math.PI,
  tau: 2 * Math.PI, TAU: 2 * Math.PI,
  e: Math.E, E: Math.E,
  phi: (1 + Math.sqrt(5)) / 2, PHI: (1 + Math.sqrt(5)) / 2,
  inf: Infinity, infinity: Infinity, Infinity: Infinity,
};

export const FUNCS = {
  // Trigonometric & reciprocal/arc
  sin: (x) => (x instanceof Jet2 ? x.sin() : Math.sin(x)),
  cos: (x) => (x instanceof Jet2 ? x.cos() : Math.cos(x)),
  tan: (x) => (x instanceof Jet2 ? x.tan() : Math.tan(x)),
  csc: (x) => (x instanceof Jet2 ? Jet2.constant(1).div(x.sin()) : 1 / Math.sin(x)),
  sec: (x) => (x instanceof Jet2 ? Jet2.constant(1).div(x.cos()) : 1 / Math.cos(x)),
  cot: (x) => (x instanceof Jet2 ? Jet2.constant(1).div(x.tan()) : 1 / Math.tan(x)),
  asin: Math.asin, arcsin: Math.asin, acos: Math.acos, arccos: Math.acos, atan: Math.atan, arctan: Math.atan, atan2: Math.atan2,
  acsc: (x) => Math.asin(1 / x), arccsc: (x) => Math.asin(1 / x),
  asec: (x) => Math.acos(1 / x), arcsec: (x) => Math.acos(1 / x),
  acot: (x) => Math.atan(1 / x), arccot: (x) => Math.atan(1 / x),

  // Hyperbolic & reciprocal/arc
  sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh,
  csch: (x) => 1 / Math.sinh(x), sech: (x) => 1 / Math.cosh(x), coth: (x) => 1 / Math.tanh(x),
  asinh: Math.asinh, arcsinh: Math.asinh, acosh: Math.acosh, arccosh: Math.acosh, atanh: Math.atanh, arctanh: Math.atanh,
  acsch: (x) => Math.asinh(1 / x), arccsch: (x) => Math.asinh(1 / x),
  asech: (x) => Math.acosh(1 / x), arcsech: (x) => Math.acosh(1 / x),
  acoth: (x) => Math.atanh(1 / x), arccoth: (x) => Math.atanh(1 / x),

  // Roots, powers, exponentials
  sqrt: (x) => (x instanceof Jet2 ? x.sqrt() : Math.sqrt(x)),
  cbrt: Math.cbrt,
  nthroot: (x, n = 2) => {
    if (x >= 0) return Math.pow(x, 1 / n);
    const rn = Math.round(n);
    if (Math.abs(n - rn) < 1e-9 && rn % 2 !== 0) return -Math.pow(-x, 1 / n);
    return NaN;
  },
  exp: (x) => (x instanceof Jet2 ? x.exp() : Math.exp(x)),
  pow: (x, p) => (x instanceof Jet2 ? x.pow(p) : Math.pow(x, p)),

  // Logarithms
  ln: (x) => (x instanceof Jet2 ? x.ln() : Math.log(x)),
  log2: Math.log2, log10: Math.log10,
  log: (x, b) => (x instanceof Jet2 ? (b !== undefined ? x.ln().div(Jet2.constant(Math.log(b))) : x.ln()) : (b !== undefined ? Math.log(x) / Math.log(b) : Math.log(x))),

  // Rounding, clamping, number theory
  abs: (x) => (x instanceof Jet2 ? x.abs() : Math.abs(x)),
  sign: Math.sign, sgn: Math.sign,
  floor: Math.floor, ceil: Math.ceil,
  round: (x, p = 0) => { const f = 10 ** p; return Math.round(x * f) / f; },
  trunc: Math.trunc, clamp: (v, lo, hi) => Math.min(Math.max(v, lo), hi), hypot: Math.hypot,
  mod: (a, b) => ((a % b) + b) % b,
  gcd: (a, b) => {
    a = Math.abs(Math.round(a)); b = Math.abs(Math.round(b));
    while (b) { const t = b; b = a % b; a = t; }
    return a;
  },
  lcm: (a, b) => {
    a = Math.abs(Math.round(a)); b = Math.abs(Math.round(b));
    if (!a || !b) return 0;
    let g = a, tb = b;
    while (tb) { const t = tb; tb = g % tb; g = t; }
    return Math.abs((a * b) / g);
  },
  min: Math.min, max: Math.max,

  // Combinatorics, statistics, special
  fact: (n) => { n = Math.round(n); if (!Number.isFinite(n) || n < 0 || n > 170) return NaN; let r = 1; for (let i = 2; i <= n; i++) r *= i; return r; },
  factorial: (n) => {
    if (Number.isInteger(n) && n >= 0 && n <= 170) return FUNCS.fact(n);
    if (n < 0 && Number.isInteger(n)) return NaN;
    return FUNCS.gamma(n + 1);
  },
  nPr: (n, r) => {
    n = Math.round(n); r = Math.round(r);
    if (!Number.isFinite(n) || !Number.isFinite(r) || r < 0 || r > n) return 0;
    if (n > 170) return Infinity;
    let res = 1;
    for (let i = 0; i < r; i++) res *= (n - i);
    return res;
  },
  perm: (n, r) => FUNCS.nPr(n, r),
  nCr: (n, r) => {
    n = Math.round(n); r = Math.round(r);
    if (!Number.isFinite(n) || !Number.isFinite(r) || r < 0 || r > n) return 0;
    if (r === 0 || r === n) return 1;
    if (n > 1000) return Infinity;
    if (r > n / 2) r = n - r;
    let res = 1;
    for (let i = 1; i <= r; i++) { res = (res * (n - i + 1)) / i; }
    return Math.round(res);
  },
  comb: (n, r) => FUNCS.nCr(n, r),
  erf: (x) => {
    if (x === 0) return 0;
    const s = x < 0 ? -1 : 1;
    const ax = Math.abs(x);
    const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
    const t = 1.0 / (1.0 + p * ax);
    const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-ax * ax);
    return s * y;
  },
  gamma: (z) => {
    if (z < 0.5) return Math.PI / (Math.sin(Math.PI * z) * FUNCS.gamma(1 - z));
    z -= 1;
    const c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
    let x = c[0];
    for (let i = 1; i < 9; i++) x += c[i] / (z + i);
    const t = z + 7.5;
    return Math.sqrt(2 * Math.PI) * Math.pow(t, z + 0.5) * Math.exp(-t) * x;
  },
  sinc: (x) => (x === 0 ? 1 : Math.sin(x) / x),
  step: (x) => (x < 0 ? 0 : 1),
  heaviside: (x) => (x < 0 ? 0 : 1),
  rect: (x) => (Math.abs(x) < 0.5 ? 1 : Math.abs(x) === 0.5 ? 0.5 : 0),
};

/** Names the compiler treats as functions or constants (everything else is a variable). */
export const RESERVED_NAMES = new Set([...Object.keys(FUNCS), ...Object.keys(CONSTS), 'if']);

function tokenize(src) {
  const tokens = [];
  const re = /\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)|(\*\*|<=|>=|==|!=|[-+*/%^(),<>]))/y;
  let pos = 0;
  const s = String(src);
  while (pos < s.length) {
    if (/^\s*$/.test(s.slice(pos))) break;
    re.lastIndex = pos;
    const m = re.exec(s);
    if (!m) throw new Error(`Unexpected character '${s[pos]}' at ${pos} in "${s}"`);
    pos = re.lastIndex;
    if (m[1] !== undefined) tokens.push({ t: 'num', v: parseFloat(m[1]) });
    else if (m[2] !== undefined) tokens.push({ t: 'name', v: m[2] });
    else tokens.push({ t: 'op', v: m[3] === '**' ? '^' : m[3] });
  }
  return tokens;
}

const BINARY = {
  '<': [1, (a, b) => +(a < b)], '<=': [1, (a, b) => +(a <= b)], '>': [1, (a, b) => +(a > b)],
  '>=': [1, (a, b) => +(a >= b)], '==': [1, (a, b) => +(a === b)], '!=': [1, (a, b) => +(a !== b)],
  '+': [2, (a, b) => (a instanceof Jet2 ? a.add(b) : (b instanceof Jet2 ? b.add(a) : a + b))],
  '-': [2, (a, b) => (a instanceof Jet2 ? a.sub(b) : (b instanceof Jet2 ? Jet2.constant(a).sub(b) : a - b))],
  '*': [3, (a, b) => (a instanceof Jet2 ? a.mul(b) : (b instanceof Jet2 ? b.mul(a) : a * b))],
  '/': [3, (a, b) => (a instanceof Jet2 ? a.div(b) : (b instanceof Jet2 ? Jet2.constant(a).div(b) : a / b))],
  '%': [3, (a, b) => (a instanceof Jet2 || b instanceof Jet2 ? NaN : a % b)],
  '^': [5, (a, b) => (a instanceof Jet2 ? a.pow(b) : (b instanceof Jet2 ? Jet2.constant(a).pow(b) : Math.pow(a, b)))],
};

function parse(tokens, src) {
  let i = 0;
  const peek = () => tokens[i];
  const expect = (v) => {
    const tok = tokens[i++];
    if (!tok || tok.v !== v) throw new Error(`Expected '${v}' in "${src}"`);
  };

  // Pratt parser; ^ is right-associative and binds tighter than unary minus (-x^2 = -(x^2)).
  function expression(minPrec = 0) {
    let left = unary();
    for (;;) {
      const tok = peek();
      if (!tok || tok.t !== 'op' || !BINARY[tok.v]) break;
      const [prec, fn] = BINARY[tok.v];
      if (prec < minPrec) break;
      i++;
      const right = expression(tok.v === '^' ? prec : prec + 1);
      const l = left;
      left = (s) => fn(l(s), right(s));
    }
    return left;
  }

  function unary() {
    const tok = peek();
    if (tok && tok.t === 'op' && (tok.v === '-' || tok.v === '+')) {
      i++;
      const operand = expression(4); // below ^, above * /
      return tok.v === '-' ? (s) => {
        const v = operand(s);
        return v instanceof Jet2 ? v.neg() : -v;
      } : operand;
    }
    return primary();
  }

  function primary() {
    const tok = tokens[i++];
    if (!tok) throw new Error(`Unexpected end of "${src}"`);
    if (tok.t === 'num') {
      const v = tok.v;
      return () => v;
    }
    if (tok.t === 'op' && tok.v === '(') {
      const inner = expression();
      expect(')');
      return inner;
    }
    if (tok.t === 'name') {
      if (peek() && peek().v === '(') {
        i++;
        const args = [];
        if (!(peek() && peek().v === ')')) {
          do { args.push(expression()); } while (peek() && peek().v === ',' && ++i);
        }
        expect(')');
        if (tok.v === 'if') {
          if (args.length !== 3) throw new Error(`if(cond, a, b) needs 3 arguments in "${src}"`);
          const [c, a, b] = args;
          return (s) => (c(s) ? a(s) : b(s));
        }
        const fn = Object.hasOwn(FUNCS, tok.v) ? FUNCS[tok.v] : undefined;
        if (!fn) throw new Error(`Unknown function '${tok.v}' in "${src}"`);
        return (s) => fn(...args.map((a) => a(s)));
      }
      return nameLookup(tok.v);
    }
    throw new Error(`Unexpected '${tok.v}' in "${src}"`);
  }

  const result = expression();
  if (i < tokens.length) throw new Error(`Unexpected '${tokens[i].v}' in "${src}"`);
  return result;
}

function nameLookup(name) {
  const dot = name.indexOf('.');
  if (dot > 0) {
    const obj = name.slice(0, dot);
    const field = name.slice(dot + 1);
    return (s) => {
      const target = s != null && Object.hasOwn(s, obj) ? s[obj] : undefined;
      const v = target && Object.hasOwn(target, field) ? target[field] : undefined;
      return typeof v === 'number' || v instanceof Jet2 ? v : NaN;
    };
  }
  return (s) => {
    const v = s != null && Object.hasOwn(s, name) ? s[name] : undefined;
    if (typeof v === 'number' || v instanceof Jet2) return v;
    return Object.hasOwn(CONSTS, name) ? CONSTS[name] : NaN;
  };
}

const cache = new Map();

/** Compiles an expression (string or number) into fn(scope) -> number. Throws on syntax errors. */
export function compile(expr) {
  if (typeof expr === 'number') return () => expr;
  const key = String(expr);
  if (!cache.has(key)) {
    if (cache.size > 2000) cache.clear();
    cache.set(key, parse(tokenize(key), key));
  }
  return cache.get(key);
}

/** compile() that reports errors instead of throwing; returns [fn, errorMessage]. */
export function tryCompile(expr, fallback = 0) {
  try {
    return [compile(expr ?? fallback), null];
  } catch (e) {
    return [() => fallback, e.message];
  }
}
