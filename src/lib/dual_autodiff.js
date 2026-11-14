// ---------------------------------------------------------------------------
// Jet2 (Second-Order Dual Number) for Machine-Precision Forward-Mode Autodiff
// Computes f(x), f'(x), and f''(x) simultaneously without finite-difference noise.
// ---------------------------------------------------------------------------

export class Jet2 {
  /**
   * @param {number} val Function value f(x)
   * @param {number} d1 First derivative f'(x)
   * @param {number} d2 Second derivative f''(x)
   */
  constructor(val, d1 = 0, d2 = 0) {
    this.val = val;
    this.d1 = d1;
    this.d2 = d2;
  }

  static constant(c) {
    return new Jet2(c, 0, 0);
  }

  static variable(x) {
    return new Jet2(x, 1, 0);
  }

  add(other) {
    const b = typeof other === 'number' ? Jet2.constant(other) : other;
    return new Jet2(this.val + b.val, this.d1 + b.d1, this.d2 + b.d2);
  }

  sub(other) {
    const b = typeof other === 'number' ? Jet2.constant(other) : other;
    return new Jet2(this.val - b.val, this.d1 - b.d1, this.d2 - b.d2);
  }

  neg() {
    return new Jet2(-this.val, -this.d1, -this.d2);
  }

  mul(other) {
    const b = typeof other === 'number' ? Jet2.constant(other) : other;
    const u = this.val, v = b.val;
    const u1 = this.d1, v1 = b.d1;
    const u2 = this.d2, v2 = b.d2;
    return new Jet2(
      u * v,
      u1 * v + u * v1,
      u2 * v + 2 * u1 * v1 + u * v2
    );
  }

  div(other) {
    const b = typeof other === 'number' ? Jet2.constant(other) : other;
    const u = this.val, v = b.val;
    const u1 = this.d1, v1 = b.d1;
    const u2 = this.d2, v2 = b.d2;
    if (v === 0) {
      return new Jet2(NaN, NaN, NaN);
    }
    const w = u / v;
    const w1 = (u1 - w * v1) / v;
    const w2 = (u2 - 2 * w1 * v1 - w * v2) / v;
    return new Jet2(w, w1, w2);
  }

  pow(p) {
    if (typeof p === 'number') {
      const u = this.val, u1 = this.d1, u2 = this.d2;
      if (p === 0) return Jet2.constant(1);
      if (p === 1) return new Jet2(u, u1, u2);
      if (u === 0 && p > 0) {
        return new Jet2(0, 0, 0);
      }
      const val = Math.pow(u, p);
      const d1 = p * Math.pow(u, p - 1) * u1;
      const d2 = p * (p - 1) * Math.pow(u, p - 2) * (u1 * u1) + p * Math.pow(u, p - 1) * u2;
      return new Jet2(val, d1, d2);
    }
    // General u^v = exp(v * ln(u))
    return this.ln().mul(p).exp();
  }

  sin() {
    const u = this.val, u1 = this.d1, u2 = this.d2;
    const s = Math.sin(u), c = Math.cos(u);
    return new Jet2(s, u1 * c, u2 * c - u1 * u1 * s);
  }

  cos() {
    const u = this.val, u1 = this.d1, u2 = this.d2;
    const s = Math.sin(u), c = Math.cos(u);
    return new Jet2(c, -u1 * s, -u2 * s - u1 * u1 * c);
  }

  tan() {
    const u = this.val, u1 = this.d1, u2 = this.d2;
    const t = Math.tan(u);
    const sec2 = 1 + t * t;
    return new Jet2(t, u1 * sec2, u2 * sec2 + 2 * u1 * u1 * t * sec2);
  }

  exp() {
    const u = this.val, u1 = this.d1, u2 = this.d2;
    const e = Math.exp(u);
    return new Jet2(e, u1 * e, (u2 + u1 * u1) * e);
  }

  ln() {
    const u = this.val, u1 = this.d1, u2 = this.d2;
    if (u <= 0) return new Jet2(NaN, NaN, NaN);
    return new Jet2(Math.log(u), u1 / u, (u2 * u - u1 * u1) / (u * u));
  }

  sqrt() {
    const u = this.val, u1 = this.d1, u2 = this.d2;
    if (u < 0) return new Jet2(NaN, NaN, NaN);
    const s = Math.sqrt(u);
    if (s === 0) return new Jet2(0, NaN, NaN);
    const d1 = u1 / (2 * s);
    const d2 = (u2 - 2 * d1 * d1) / (2 * s);
    return new Jet2(s, d1, d2);
  }

  abs() {
    const u = this.val, u1 = this.d1, u2 = this.d2;
    const s = Math.sign(u);
    return new Jet2(Math.abs(u), s * u1, s * u2);
  }
}

/**
 * Evaluates an AST or compiled function using Jet2 algebra for exact derivatives.
 */
export function evalDual(f, x) {
  const vx = Jet2.variable(x);
  try {
    const res = f(vx);
    if (res instanceof Jet2) {
      return res;
    }
    if (typeof res === 'number') {
      return Jet2.constant(res);
    }
    return new Jet2(NaN, NaN, NaN);
  } catch (err) {
    return new Jet2(NaN, NaN, NaN);
  }
}

/**
 * Second-Difference Divergence & Reciprocal-Zero Guard.
 * Detects both odd-order poles (e.g. 1/(x-2)) and even-order poles (e.g. 1/(x-2)^2, sec^2(x)).
 *
 * @param {Function} f Function f(x)
 * @param {number} x Point of interest
 * @param {number} dx Step size (e.g. pixel span in world units)
 * @returns {boolean} True if x is in the immediate vicinity of a vertical asymptote / pole
 */
export function isVerticalAsymptote(f, x, dx = 1e-4) {
  try {
    const y0 = f(x);
    const yLeft = f(x - dx);
    const yRight = f(x + dx);

    // If any are infinite or NaN
    if (!Number.isFinite(y0) || !Number.isFinite(yLeft) || !Number.isFinite(yRight)) {
      return true;
    }

    // 1. Classical sign inversion across a large jump (odd-order pole)
    if (Math.sign(yLeft) !== Math.sign(yRight) && (Math.abs(yLeft) > 100 || Math.abs(yRight) > 100)) {
      return true;
    }

    // 2. Even-order pole guard: reciprocal zero & second-difference divergence
    // Check reciprocal g(x) = 1 / f(x). At a pole, g(x) -> 0.
    const gLeft = Math.abs(1 / yLeft);
    const g0 = Math.abs(1 / y0);
    const gRight = Math.abs(1 / yRight);

    if (g0 < 1e-3 && (Math.abs(y0) > 500 || Math.abs(yLeft) > 500 || Math.abs(yRight) > 500)) {
      // Local dip in reciprocal towards zero indicates a pole
      if (g0 <= gLeft && g0 <= gRight) {
        return true;
      }
    }

    // 3. Second-difference spike check: |f(x-dx) - 2f(x) + f(x+dx)|
    const secondDiff = Math.abs(yLeft - 2 * y0 + yRight);
    if (secondDiff > 1e4 && (Math.abs(y0) > 200 || Math.abs(yLeft) > 200 || Math.abs(yRight) > 200)) {
      return true;
    }

    return false;
  } catch {
    return true;
  }
}
