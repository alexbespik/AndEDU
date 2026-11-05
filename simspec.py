"""
SimSpec v1 — declarative simulations that agents can author as JSON.

A spec is data, never code: the frontend evaluates expressions with its own small
interpreter (src/lib/expr.js), and this module checks the same grammar server-side so
an agent gets precise errors back instead of a blank canvas.

Two kinds:
  "particles"  2D bodies integrated over time (gravity, springs, drag, mutual gravitation,
               custom forces, rigid rods, ground/walls with restitution). Covers projectiles,
               pendulums, oscillators, orbits, collisions, charged particles in fields, ...
  "graph"      y = f(x, t) curves with sliders, optionally animated in t. Covers waves,
               interference, thermodynamic curves, distributions, any function family.
"""
import ast
import re
from typing import Any, Dict, List, Tuple

FUNCTIONS = {
    "sin", "cos", "tan", "csc", "sec", "cot",
    "asin", "arcsin", "acos", "arccos", "atan", "arctan", "atan2",
    "acsc", "arccsc", "asec", "arcsec", "acot", "arccot",
    "sinh", "cosh", "tanh", "csch", "sech", "coth",
    "asinh", "arcsinh", "acosh", "arccosh", "atanh", "arctanh",
    "acsch", "arccsch", "asech", "arcsech", "acoth", "arccoth",
    "sqrt", "cbrt", "nthroot", "exp", "pow",
    "ln", "log", "log2", "log10",
    "abs", "sign", "sgn", "floor", "ceil", "round", "trunc", "clamp", "hypot",
    "mod", "gcd", "lcm", "min", "max",
    "fact", "factorial", "nPr", "perm", "nCr", "comb",
    "erf", "gamma", "sinc", "step", "heaviside", "rect",
    "if",
}
CONSTANTS = {"pi", "PI", "tau", "TAU", "e", "E", "phi", "PHI", "inf", "infinity", "Infinity"}
BODY_FIELDS = {"x", "y", "vx", "vy", "m", "r", "speed"}
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")
COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{3,8}|accent|gold|green|cyan|pink|orange|purple|white)$")

MAX_EXPR_LEN = 400
MAX_PARAMS = 12
MAX_BODIES = 24
MAX_FORCES = 32
MAX_CURVES = 6
MAX_SERIES = 4

FORCE_TYPES = {"spring", "drag", "gravitation", "custom", "uniform"}
LINK_TYPES = {"rod"}


class SpecError(ValueError):
    pass


def _check_expr(expr: Any, names: set, where: str, errors: List[str], body_ids: set = frozenset()):
    """Validates one expression against the whitelist grammar shared with src/lib/expr.js."""
    if isinstance(expr, (int, float)) and not isinstance(expr, bool):
        return
    if not isinstance(expr, str) or not expr.strip():
        errors.append(f"{where}: expected a number or expression string")
        return
    if len(expr) > MAX_EXPR_LEN:
        errors.append(f"{where}: expression longer than {MAX_EXPR_LEN} characters")
        return
    # The JS grammar uses ^ for powers; Python parses it as BitXor, which we accept as power here.
    # `if` is a Python keyword, so the if(c,a,b) helper is parsed under an alias.
    py_src = re.sub(r"\bif\s*\(", "if_(", expr.replace("**", "^"))
    try:
        tree = ast.parse(py_src, mode="eval")
    except SyntaxError as e:
        errors.append(f"{where}: syntax error in '{expr}' ({e.msg})")
        return

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                raise SpecError(f"only numeric literals are allowed, got {node.value!r}")
            return
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.BitXor)):
                raise SpecError(f"operator {type(node.op).__name__} is not allowed")
            visit(node.left); visit(node.right); return
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, (ast.USub, ast.UAdd)):
                raise SpecError("only unary + and - are allowed")
            visit(node.operand); return
        if isinstance(node, ast.Compare):
            for op in node.ops:
                if not isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)):
                    raise SpecError("only < <= > >= == != comparisons are allowed")
            visit(node.left)
            for c in node.comparators:
                visit(c)
            return
        if isinstance(node, ast.Name):
            if node.id not in names and node.id not in CONSTANTS:
                raise SpecError(f"unknown name '{node.id}' (known: {', '.join(sorted(names | CONSTANTS))})")
            return
        if isinstance(node, ast.Attribute):
            if not isinstance(node.value, ast.Name) or node.value.id not in body_ids:
                raise SpecError("dotted names must look like <bodyId>.<field>")
            if node.attr not in BODY_FIELDS:
                raise SpecError(f"unknown body field '.{node.attr}' (use {', '.join(sorted(BODY_FIELDS))})")
            return
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "if_":
                node.func.id = "if"
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                fname = getattr(node.func, "id", "?")
                raise SpecError(f"function '{fname}' is not available (use {', '.join(sorted(FUNCTIONS))})")
            if node.keywords:
                raise SpecError("keyword arguments are not allowed")
            for a in node.args:
                visit(a)
            return
        raise SpecError(f"{type(node).__name__} is not allowed in expressions")

    try:
        visit(tree)
    except SpecError as e:
        errors.append(f"{where}: {e} in '{expr}'")


def _num(v: Any, default: float) -> float:
    try:
        f = float(v)
        return f if f == f and abs(f) < 1e12 else default
    except (TypeError, ValueError):
        return default


def _clean_params(raw: Any, errors: List[str]) -> List[Dict[str, Any]]:
    params = []
    if not isinstance(raw, list):
        return params
    for i, p in enumerate(raw[:MAX_PARAMS]):
        if not isinstance(p, dict) or not NAME_RE.match(str(p.get("name", ""))):
            errors.append(f"params[{i}]: needs a 'name' like 'k' or 'v0'")
            continue
        lo, hi = _num(p.get("min"), 0.0), _num(p.get("max"), 1.0)
        if hi <= lo:
            errors.append(f"params[{i}] ({p['name']}): max must be greater than min")
            continue
        value = min(max(_num(p.get("value"), lo), lo), hi)
        params.append({
            "name": p["name"],
            "label": str(p.get("label") or p["name"])[:60],
            "min": lo, "max": hi, "value": value,
            "step": _num(p.get("step"), (hi - lo) / 100) or (hi - lo) / 100,
            "unit": str(p.get("unit") or "")[:16],
        })
    return params


def _clean_color(c: Any, fallback: str) -> str:
    return c if isinstance(c, str) and COLOR_RE.match(c) else fallback


def validate_spec(spec: Any) -> Tuple[Dict[str, Any], List[str]]:
    """Returns (cleaned_spec, errors). The spec is usable only when errors is empty."""
    errors: List[str] = []
    if not isinstance(spec, dict):
        return {}, ["simulation must be a JSON object"]
    kind = spec.get("kind")
    if kind == "math":
        return validate_math(spec)
    if kind == "chem":
        try:
            import chemspec  # chemistry kit (agy): validate_chem(spec) -> (clean, errors)
        except ImportError:
            return {}, ["simulation.kind 'chem' is not available yet"]
        return chemspec.validate_chem(spec)
    if kind not in ("particles", "graph"):
        return {}, ["simulation.kind must be 'particles', 'graph', 'math' or 'chem'"]

    params = _clean_params(spec.get("params"), errors)
    param_names = {p["name"] for p in params}
    clean: Dict[str, Any] = {
        "version": 1,
        "kind": kind,
        "title": str(spec.get("title") or "Simulation")[:100],
        "description": str(spec.get("description") or "")[:600],
        "params": params,
    }

    if kind == "graph":
        x = spec.get("x") if isinstance(spec.get("x"), dict) else {}
        xmin, xmax = _num(x.get("min"), 0.0), _num(x.get("max"), 10.0)
        if xmax <= xmin:
            errors.append("x.max must be greater than x.min")
        clean["x"] = {"min": xmin, "max": xmax, "label": str(x.get("label") or "x")[:40]}
        y = spec.get("y") if isinstance(spec.get("y"), dict) else {}
        clean["y"] = {"label": str(y.get("label") or "y")[:40]}
        if "min" in y and "max" in y and _num(y["max"], 1) > _num(y["min"], 0):
            clean["y"].update(min=_num(y["min"], 0), max=_num(y["max"], 1))
        clean["animate"] = bool(spec.get("animate", False))
        names = param_names | {"x", "t"}
        curves = []
        for i, c in enumerate((spec.get("curves") or [])[:MAX_CURVES]):
            if not isinstance(c, dict):
                continue
            _check_expr(c.get("expr"), names, f"curves[{i}].expr", errors)
            curves.append({
                "expr": c.get("expr"),
                "label": str(c.get("label") or f"curve {i + 1}")[:40],
                "color": _clean_color(c.get("color"), ["gold", "cyan", "pink", "green", "orange", "purple"][i % 6]),
            })
        if not curves:
            errors.append("graph simulations need at least one entry in 'curves'")
        clean["curves"] = curves
        return clean, errors

    # ---- particles ----
    world = spec.get("world") if isinstance(spec.get("world"), dict) else {}
    width, height = _num(world.get("width"), 10.0), _num(world.get("height"), 6.0)
    if width <= 0 or height <= 0:
        errors.append("world.width and world.height must be positive (metres)")
    clean["world"] = {
        "width": width, "height": height,
        "ground": bool(world.get("ground", False)),
        "walls": bool(world.get("walls", False)),
        "collisions": bool(world.get("collisions", True)),   # bodies bounce off each other and off rods
        "label": str(world.get("label") or "")[:60],
    }
    base_names = param_names | {"t"}
    for key in ("gravity", "restitution"):
        if key in world:
            _check_expr(world[key], base_names, f"world.{key}", errors)
            clean["world"][key] = world[key]

    raw_bodies = spec.get("bodies") if isinstance(spec.get("bodies"), list) else []
    body_ids = set()
    bodies = []
    for i, b in enumerate(raw_bodies[:MAX_BODIES]):
        if not isinstance(b, dict) or not NAME_RE.match(str(b.get("id", ""))):
            errors.append(f"bodies[{i}]: needs an 'id' like 'ball' or 'planet2'")
            continue
        if b["id"] in body_ids or b["id"] in param_names:
            errors.append(f"bodies[{i}]: id '{b['id']}' is already used")
            continue
        body_ids.add(b["id"])
        bodies.append(b)
    if not bodies:
        errors.append("particles simulations need at least one body")

    init_names = base_names
    clean_bodies = []
    for b in bodies:
        cb = {"id": b["id"], "label": str(b.get("label") or b["id"])[:40],
              "color": _clean_color(b.get("color"), "gold"), "fixed": bool(b.get("fixed", False)),
              "trail": bool(b.get("trail", False))}
        for field, default in (("x", 0), ("y", 0), ("vx", 0), ("vy", 0), ("mass", 1), ("radius", 0.2)):
            v = b.get(field, default)
            _check_expr(v, init_names, f"bodies.{b['id']}.{field}", errors)
            cb[field] = v
        clean_bodies.append(cb)
    clean["bodies"] = clean_bodies

    dyn_names = base_names | {"x", "y", "vx", "vy", "m"}
    forces = []
    for i, f in enumerate((spec.get("forces") or [])[:MAX_FORCES]):
        if not isinstance(f, dict) or f.get("type") not in FORCE_TYPES:
            errors.append(f"forces[{i}]: type must be one of {', '.join(sorted(FORCE_TYPES))}")
            continue
        cf = {"type": f["type"]}
        targets = [k for k in ("a", "b", "body") if k in f]
        for k in targets:
            if f[k] not in body_ids:
                errors.append(f"forces[{i}].{k}: unknown body '{f[k]}'")
            cf[k] = f[k]
        need = {"spring": ("a", "b"), "drag": ("body",), "custom": ("body",), "uniform": (), "gravitation": ()}[f["type"]]
        for k in need:
            if k not in f:
                errors.append(f"forces[{i}] ({f['type']}): missing '{k}'")
        exprs = {"spring": ("k", "rest", "damping"), "drag": ("coef", "power"), "gravitation": ("G", "soften"),
                 "custom": ("fx", "fy"), "uniform": ("fx", "fy")}[f["type"]]
        for k in exprs:
            if k in f:
                _check_expr(f[k], dyn_names, f"forces[{i}].{k}", errors, body_ids)
                cf[k] = f[k]
        if f["type"] == "uniform" and "bodies" in f and isinstance(f["bodies"], list):
            cf["bodies"] = [x for x in f["bodies"] if x in body_ids]
        forces.append(cf)
    clean["forces"] = forces

    links = []
    for i, l in enumerate((spec.get("links") or [])[:MAX_FORCES]):
        if not isinstance(l, dict) or l.get("type") not in LINK_TYPES:
            errors.append(f"links[{i}]: type must be 'rod'")
            continue
        if l.get("a") not in body_ids or l.get("b") not in body_ids:
            errors.append(f"links[{i}]: 'a' and 'b' must be body ids")
            continue
        cl = {"type": "rod", "a": l["a"], "b": l["b"]}
        if "length" in l:
            _check_expr(l["length"], init_names, f"links[{i}].length", errors)
            cl["length"] = l["length"]
        links.append(cl)
    clean["links"] = links

    live_names = base_names
    for section, limit in (("readouts", 8), ("series", MAX_SERIES)):
        out = []
        for i, r in enumerate((spec.get(section) or [])[:limit]):
            if not isinstance(r, dict):
                continue
            _check_expr(r.get("expr"), live_names, f"{section}[{i}].expr", errors, body_ids)
            out.append({"expr": r.get("expr"), "label": str(r.get("label") or f"{section} {i + 1}")[:40],
                        "unit": str(r.get("unit") or "")[:16],
                        "color": _clean_color(r.get("color"), ["gold", "cyan", "pink", "green"][i % 4])})
        clean[section] = out

    vectors = []
    for i, v in enumerate((spec.get("vectors") or [])[:12]):
        if not isinstance(v, dict) or v.get("body") not in body_ids:
            errors.append(f"vectors[{i}]: 'body' must be a body id")
            continue
        for k in ("x", "y"):
            _check_expr(v.get(k), live_names, f"vectors[{i}].{k}", errors, body_ids)
        vectors.append({"body": v["body"], "x": v.get("x"), "y": v.get("y"),
                        "label": str(v.get("label") or "")[:12], "scale": _num(v.get("scale"), 0.2),
                        "color": _clean_color(v.get("color"), "cyan")})
    clean["vectors"] = vectors
    clean["duration"] = min(max(_num(spec.get("duration"), 0), 0), 600)
    ov = spec.get("overlays") if isinstance(spec.get("overlays"), dict) else {}
    clean["overlays"] = {k: bool(ov.get(k, False)) for k in ("fbd", "energy", "momentum", "stress")}
    return clean, errors


SPEC_GUIDE = """
SimSpec v1 (JSON). Expressions are strings using + - * / ^ %, comparisons, parentheses,
functions sin cos tan asin acos atan atan2 sinh cosh tanh sqrt abs exp log log10 min max pow
floor ceil round sign hypot clamp(v,lo,hi) if(cond,a,b), constants pi tau E, slider params by name,
time t. Units are SI; the canvas auto-scales the world box. y points UP.

kind "particles":
{"kind":"particles","title":"...","description":"what to try with the sliders",
 "params":[{"name":"k","label":"Spring constant","min":1,"max":100,"value":20,"step":1,"unit":"N/m"}],
 "world":{"width":10,"height":6,"ground":true,"walls":false,"gravity":"g","restitution":"0.8","collisions":true},
   // collisions (default true): bodies bounce off each other and off rods (a ball can strike a pendulum rod)
   // with gravity on, set ground: true unless falling forever is the point; keep motion inside the world box
 "bodies":[{"id":"anchor","x":"5","y":"6","fixed":true,"radius":"0.08","color":"white"},
           {"id":"bob","x":"5+L*sin(theta0)","y":"6-L*cos(theta0)","mass":"m","radius":"0.2","trail":true}],
 "forces":[{"type":"spring","a":"anchor","b":"bob","k":"k","rest":"L","damping":"0"},
           {"type":"drag","body":"bob","coef":"c","power":"1"},
           {"type":"gravitation","G":"G"},                       // mutual between all non-fixed bodies
           {"type":"custom","body":"bob","fx":"-q*B*vy","fy":"q*B*vx"},   // x,y,vx,vy,m = that body's state
           {"type":"uniform","fx":"0","fy":"-q*Ef","bodies":["bob"]}],
 "links":[{"type":"rod","a":"anchor","b":"bob","length":"L"}],  // rigid distance constraint (pendulums)
 "vectors":[{"body":"bob","x":"bob.vx","y":"bob.vy","label":"v","scale":0.3}],
 "readouts":[{"label":"Speed","expr":"bob.speed","unit":"m/s"}],
 "series":[{"label":"KE","expr":"0.5*bob.m*bob.speed^2"}],   // plotted live vs time
 "duration":20,   // optional: auto-reset after N seconds
 "overlays":{"fbd":true,"energy":false,"momentum":false,"stress":false}}
   // overlays start switched on (students can toggle all four): fbd = labeled force arrows on every body,
   // energy = KE / PE / spring / total / lost bars, momentum = total p at the center of mass,
   // stress = springs and rods colored by strain (red tension, blue compression)
Body fields usable in readouts/series/vectors/custom forces: <id>.x .y .vx .vy .m .r .speed

kind "graph": x is the HORIZONTAL axis variable. To plot something against time, make x the time axis and
write the curves in x (e.g. "v0*x - 0.5*g*x^2" with x label "time (s)"); use t only for animation (animate: true).
{"kind":"graph","title":"...","description":"...","params":[...],
 "x":{"min":0,"max":10,"label":"x (m)"},"y":{"min":-2,"max":2,"label":"displacement (m)"},
 "animate":true,
 "curves":[{"expr":"A*sin(k*x-w*t)","label":"wave 1"},{"expr":"A*sin(k*x+w*t)","label":"wave 2"}]}
Colors: accent gold green cyan pink orange purple white or #hex.
"""


# ---------------------------------------------------------------- kind "math": the math simulation kit
# widget -> (expression fields with the variables each may use, sliders the player adds when missing)
MATH_WIDGETS: Dict[str, Tuple[Dict[str, set], Dict[str, Tuple[float, float, float]]]] = {
    "epsilon_delta": ({"f": {"x"}, "a": set(), "L": set()}, {"eps": (0.02, 2, 0.5), "delta": (0.005, 2, 0.4)}),
    "epsilon_n": ({"term": {"n"}, "L": set()}, {"eps": (0.005, 1, 0.2)}),
    "secant_tangent": ({"f": {"x"}, "a": set()}, {"h": (-3, 3, 1.5)}),
    "riemann": ({"f": {"x"}, "a": set(), "b": set()}, {"n": (1, 100, 6)}),
    "series": ({"term": {"k", "x"}, "target": {"x"}}, {"N": (0, 25, 3)}),
    "unit_circle": ({}, {"theta": (0, 360, 45)}),
    "parametric": ({"x": {"t"}, "y": {"t"}, "tmin": set(), "tmax": set()}, {"t": (0, 1, 0.3)}),
    "vector_field": ({"P": {"x", "y"}, "Q": {"x", "y"}}, {}),
    "transform2d": ({"a": set(), "b": set(), "c": set(), "d": set()}, {"m11": (-3, 3, 1), "m12": (-3, 3, 0.5), "m21": (-3, 3, 0), "m22": (-3, 3, 1)}),
}
MATH_DEFAULTS = {  # fields a widget can do without
    "epsilon_n": {}, "series": {"target": None}, "parametric": {"tmin": 0, "tmax": "2*pi"},
    "transform2d": {"a": "m11", "b": "m12", "c": "m21", "d": "m22"},
}
RIEMANN_METHODS = ("left", "right", "mid", "trap")


def validate_math(spec: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    widget = spec.get("widget")
    if widget not in MATH_WIDGETS:
        return {}, [f"math simulations need 'widget': one of {', '.join(MATH_WIDGETS)}"]
    fields, sliders = MATH_WIDGETS[widget]
    params = _clean_params(spec.get("params"), errors)
    have = {p["name"] for p in params}
    for name, (lo, hi, val) in sliders.items():  # the widget's own sliders, unless the spec defines them
        if name not in have and len(params) < MAX_PARAMS:
            params.append({"name": name, "label": name, "min": lo, "max": hi, "value": val,
                           "step": 1 if name in ("n", "N") else (hi - lo) / 200, "unit": ""})
    names = {p["name"] for p in params}
    clean: Dict[str, Any] = {"version": 1, "kind": "math", "widget": widget,
                             "title": str(spec.get("title") or "Math simulation")[:100],
                             "description": str(spec.get("description") or "")[:600], "params": params}
    defaults = MATH_DEFAULTS.get(widget, {})
    for field, variables in fields.items():
        value = spec.get(field, defaults.get(field))
        if value is None:
            if field in defaults:
                continue
            errors.append(f"math widget '{widget}' needs '{field}'")
            continue
        _check_expr(value, names | variables, field, errors)
        clean[field] = value
    if widget == "epsilon_delta" and spec.get("delta_rule") not in (None, ""):
        _check_expr(spec["delta_rule"], names | {"eps"}, "delta_rule", errors)
        clean["delta_rule"] = spec["delta_rule"]
    if widget == "riemann":
        clean["method"] = spec.get("method") if spec.get("method") in RIEMANN_METHODS else "left"
    if widget == "epsilon_n":
        clean["nmax"] = int(min(max(_num(spec.get("nmax"), 60), 10), 400))
    view = spec.get("view") if isinstance(spec.get("view"), dict) else {}
    v = {k: _num(view.get(k), d) for k, d in (("xmin", -5), ("xmax", 5), ("ymin", -4), ("ymax", 4))}
    if v["xmax"] <= v["xmin"] or v["ymax"] <= v["ymin"]:
        errors.append("view: max must be greater than min")
    if view:
        clean["view"] = v
    return clean, errors


MATH_GUIDE = """
kind "math": interactive math widgets (pick the one that makes the class's key idea visible).
{"kind":"math","widget":"<widget>","title":"...","description":"what to drag and what to notice",
 "params":[{"name":"c","label":"...","min":0,"max":2,"value":1,"step":0.1}],   // optional extra sliders
 "view":{"xmin":-1,"xmax":4,"ymin":-1,"ymax":6}, ...widget fields}
Widgets (expressions use the same grammar as other specs; fact(n) is n!):
- "epsilon_delta": f (in x), a, L, optional delta_rule (in eps, e.g. "eps/2" or "min(1, eps/5)"). Sliders eps,
   delta are added. Shows the eps-band around L and the delta-band around a, marks where f escapes, plots the
   largest working delta as a function of eps, and checks a delta_rule for every eps (the proof's choice of delta).
   Give the correct delta_rule when the class teaches a specific proof; omit it to let the student discover one.
- "epsilon_n": term (in n), L, optional nmax. Slider eps. Plots a_n with the eps-band and the first N after which
   every term stays inside.
- "secant_tangent": f, a. Slider h. Secant through (a, f(a)) and (a+h, f(a+h)) approaching the tangent.
- "riemann": f, a, b, method "left"|"right"|"mid"|"trap". Slider n. Rectangles, their sum and the exact area.
- "series": term (in k and x), optional target (in x). Slider N. Partial sum S_N(x) = sum of term for k=0..N
   against the target, e.g. Taylor term "(-1)^k * x^(2*k+1) / fact(2*k+1)" with target "sin(x)".
- "unit_circle": slider theta (degrees). Angle, cos and sin as projections, and the sine graph traced.
- "parametric": x and y (in t), tmin, tmax. Slider t (0..1 of the way along). Curve and moving point.
- "vector_field": P and Q (in x, y). Arrows of (P, Q); click the plot to drop a flow line.
- "transform2d": a, b, c, d (default sliders m11 m12 m21 m22). The matrix acting on the grid and unit square,
   with the determinant as signed area.
"""
