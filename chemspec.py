"""
ChemSpec v1 — chemistry simulation kit for SciEdu Studio.
Declarative specifications for chemistry widgets, validated server-side
and rendered interactively by src/simulations/ChemSim.jsx.
"""
import math
from typing import Any, Dict, List, Tuple
import simspec


CHEM_WIDGETS: Dict[str, Tuple[Dict[str, set], Dict[str, Tuple[float, float, float]]]] = {
    "kinetics": (
        {"k": set(), "A0": set()},
        {"k": (0.01, 2.0, 0.5), "k_rev": (0.0, 1.0, 0.1), "A0": (0.1, 5.0, 2.0)}
    ),
    "equilibrium": (
        {"K": set()},
        {"A0": (0.0, 5.0, 2.0), "B0": (0.0, 5.0, 2.0), "C0": (0.0, 5.0, 0.0), "D0": (0.0, 5.0, 0.0)}
    ),
    "titration": (
        {"pKa": set(), "Va": set(), "Ca": set(), "Cb": set()},
        {"pKa": (1.0, 12.0, 4.75), "Va": (10.0, 100.0, 25.0), "Ca": (0.02, 1.0, 0.1), "Cb": (0.02, 1.0, 0.1), "Vb": (0.0, 60.0, 0.0)}
    ),
    "gas_law": (
        {},
        {"n": (0.1, 2.0, 1.0), "T": (100.0, 600.0, 300.0), "V": (5.0, 30.0, 15.0)}
    ),
    "energy_diagram": (
        {"Ea": set(), "deltaH": set()},
        {"T": (200.0, 1000.0, 298.0)}
    ),
    "decay": (
        {"t_half": set()},
        {"N0": (10.0, 200.0, 100.0), "t_half": (1.0, 30.0, 5.0)}
    ),
}

CHEM_DEFAULTS = {
    "kinetics": {"k": "k", "A0": "A0", "order": 1, "reversible": False},
    "equilibrium": {"K": 4.0, "a": 1, "b": 1, "c": 1, "d": 1},
    "titration": {"pKa": "pKa", "Va": "Va", "Ca": "Ca", "Cb": "Cb", "strong": False, "acid_name": "HA", "base_name": "NaOH"},
    "gas_law": {"gas_type": "ideal"},
    "energy_diagram": {"Ea": 50.0, "deltaH": -20.0, "Ea_cat": 25.0},
    "decay": {"t_half": "t_half"},
}


def solve_titration_ph(pKa: Any, Va: float, Ca: float, Cb: float, Vb: float, is_strong: bool = False) -> float:
    """
    Solves aqueous titration pH using rigorous charge balance at 25 °C (Kw = 1.0e-14):
      [H+] + [Na+] = [OH-] + [A-] (monoprotic)
      [H+] + [Na+] = [OH-] + [HA-] + 2[A2-] + ... (polyprotic)
    """
    Kw = 1.0e-14
    V_tot = Va + Vb
    if V_tot <= 0:
        return 7.0
    c_na = (Cb * Vb) / V_tot
    c_a_tot = (Ca * Va) / V_tot

    pkas: List[float] = []
    if isinstance(pKa, (list, tuple)):
        pkas = [float(x) for x in pKa]
    elif isinstance(pKa, (int, float)):
        pkas = [float(pKa)]
    else:
        try:
            pkas = [float(pKa)]
        except (ValueError, TypeError):
            pkas = [4.75]

    def f(log_h: float) -> float:
        h = 10.0 ** log_h
        oh = Kw / h
        if is_strong:
            a_charge = c_a_tot * len(pkas)
        else:
            n = len(pkas)
            Kas = [10.0 ** (-pk) for pk in pkas]
            terms = [1.0] * (n + 1)
            prod_ka = 1.0
            for k in range(1, n + 1):
                prod_ka *= Kas[k - 1]
                terms[k] = (h ** (n - k)) * prod_ka
            terms[0] = h ** n
            d = sum(terms)
            if d <= 0:
                a_charge = 0.0
            else:
                a_charge = c_a_tot * sum(k * terms[k] for k in range(1, n + 1)) / d

        return h - oh + c_na - a_charge

    lo, hi = -14.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    h = 10.0 ** ((lo + hi) / 2.0)
    return -math.log10(h)


def validate_chem(spec: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validates a chemistry simulation specification.
    Returns (cleaned_spec, errors).
    """
    errors: List[str] = []
    if not isinstance(spec, dict):
        return {}, ["chemistry simulation must be a JSON object"]

    widget = spec.get("widget")
    if widget not in CHEM_WIDGETS:
        return {}, [f"unknown chemistry widget '{widget}'; must be one of {', '.join(sorted(CHEM_WIDGETS))}"]

    fields, sliders = CHEM_WIDGETS[widget]
    params = simspec._clean_params(spec.get("params"), errors)
    have = {p["name"] for p in params}

    # Add default sliders unless defined in spec
    for name, (lo, hi, val) in sliders.items():
        if name not in have and len(params) < simspec.MAX_PARAMS:
            step = 1.0 if name == "N0" else (hi - lo) / 100.0
            params.append({
                "name": name,
                "label": name,
                "min": lo,
                "max": hi,
                "value": val,
                "step": step,
                "unit": "M" if "0" in name or name in ("Ca", "Cb") else "mL" if name in ("Va", "Vb") else "K" if name == "T" else "s" if name in ("t_half",) else ""
            })

    names = {p["name"] for p in params}
    clean: Dict[str, Any] = {
        "version": 1,
        "kind": "chem",
        "widget": widget,
        "title": str(spec.get("title") or f"{widget.replace('_', ' ').capitalize()} Simulation")[:100],
        "description": str(spec.get("description") or "")[:600],
        "params": params,
    }

    defaults = CHEM_DEFAULTS.get(widget, {})
    # Copy auxiliary fields
    for k, v in defaults.items():
        if k not in fields:
            clean[k] = spec.get(k, v)

    for field, variables in fields.items():
        value = spec.get(field, defaults.get(field))
        if value is None:
            if field in defaults:
                continue
            errors.append(f"chem widget '{widget}' needs '{field}'")
            continue
        simspec._check_expr(value, names | variables, field, errors)
        clean[field] = value

    return clean, errors


CHEM_GUIDE = """
kind "chem": interactive chemistry simulation kit (makes molecular & chemical behavior visible).
{"kind":"chem","widget":"<widget>","title":"...","description":"what to adjust and explore",
 "params":[...], ...widget fields}

Widgets:
- "kinetics": reaction rates A -> B (orders 0, 1, 2) or reversible A <=> B. Sliders k, k_rev, [A]0.
  Plots [A](t) and [B](t) with half-life markers and instantaneous rate readouts.
- "equilibrium": general equilibrium aA + bB <=> cC + dD with constant K. Sliders for initial amounts A0, B0, C0, D0.
  Solves equilibrium extent, showing reaction quotient Q vs K, Le Chatelier shifts, and dynamic bar charts.
- "titration": acid-base titration curve (strong/weak acid with strong base). Sliders pKa, Va, Ca, Cb, Vb.
  Renders pH titration curve with equivalence point, buffer half-equivalence region, and beaker indicator color.
- "gas_law": interactive piston cylinder with moving gas particles. Sliders n, T, V.
  Visualizes kinetic theory of gases, calculating theoretical pressure P = nRT/V vs wall collision frequency.
- "energy_diagram": reaction coordinate potential energy profile showing reactants, transition state barrier (Ea),
  enthalpy change (deltaH), and catalyzed pathway (Ea_cat) with Maxwell-Boltzmann fraction readout exp(-Ea/RT).
- "decay": radioactive first-order decay. N particles in a lattice decaying probabilistically over half-life t_half
  plotted against the continuous analytic decay law N0 * exp(-lambda * t).
"""
