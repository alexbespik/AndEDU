// ---------------------------------------------------------------------------
// Safe expression compiler for SimSpec simulations.
// Parses a small math grammar into closures — never eval/new Function — so specs
// written by agents are data only. Grammar mirrors simspec.py on the backend:
//   numbers, names, dotted names (ball.vx), + - * / % ^ (** alias), unary +/-,
//   comparisons < <= > >= == !=, parentheses, function calls.
// ---------------------------------------------------------------------------

const FUNCS = {
  sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
  atan2: Math.atan2, sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh, sqrt: Math.sqrt, abs: Math.abs,
  exp: Math.exp, log: Math.log, log10: Math.log10, min: Math.min, max: Math.max, pow: Math.pow,
  floor: Math.floor, ceil: Math.ceil, round: Math.round, sign: Math.sign, hypot: Math.hypot,
  clamp: (v, lo, hi) => Math.min(Math.max(v, lo), hi),
  fact: (n) => { n = Math.round(n); if (n < 0 || n > 170) return NaN; let r = 1; for (let i = 2; i <= n; i++) r *= i; return r; },
};
const CONSTS = { pi: Math.PI, tau: 2 * Math.PI, E: Math.E };
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
  '+': [2, (a, b) => a + b], '-': [2, (a, b) => a - b],
  '*': [3, (a, b) => a * b], '/': [3, (a, b) => a / b], '%': [3, (a, b) => a % b],
  '^': [5, Math.pow],
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
      return tok.v === '-' ? (s) => -operand(s) : operand;
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
        const fn = FUNCS[tok.v];
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
      const target = Object.hasOwn(s, obj) ? s[obj] : undefined;
      const v = target && Object.hasOwn(target, field) ? target[field] : undefined;
      return typeof v === 'number' ? v : NaN;
    };
  }
  return (s) => {
    const v = Object.hasOwn(s, name) ? s[name] : undefined;
    if (typeof v === 'number') return v;
    return name in CONSTS ? CONSTS[name] : NaN;
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
