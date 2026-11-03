#!/usr/bin/env python3
"""
Adds four mechanics showcase lessons whose simulations use the teaching overlays:
free-body diagrams, momentum conservation, energy conservation and material stress.

    python3 scripts/showcase_topics.py            # posts to http://127.0.0.1:8090
Each topic goes through POST /api/topics, so the server validates every simulation spec.
"""
import json
import math
import sys
import urllib.request

API = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8090") + "/api/topics"


def post(topic):
    req = urllib.request.Request(API, data=json.dumps(topic).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req))
    print(f"{topic['id']:<34} {res['status']}  warnings: {res.get('warnings') or 'none'}")


# ---------------------------------------------------------------- free-body diagrams
fbd = {
    "id": "free-body-diagrams",
    "title": "Free-Body Diagrams",
    "category": "Classical Mechanics",
    "difficulty": "Introductory",
    "summary": "Isolate one object, draw every force on it, and Newton's second law writes itself. Watch live free-body diagrams for a resting box, a hanging mass and a ball flying through air.",
    "cheatSheet": [
        {"label": "Newton's second law", "formula": "\\sum \\vec F = m\\vec a"},
        {"label": "Weight", "formula": "W = mg"},
        {"label": "Hooke's law", "formula": "F_s = -k\\,\\Delta x"},
        {"label": "Quadratic drag", "formula": "F_D = c\\,v^2"},
        {"label": "Equilibrium", "formula": "\\sum F_x = 0,\\ \\sum F_y = 0"},
    ],
    "mermaid": "graph LR\n  A[\"Pick one object\"] --> B[\"Draw every force on it\"]\n  B --> C[\"Choose axes\"]\n  C --> D[\"Sum forces per axis\"]\n  D --> E[\"Solve for a or the unknown force\"]",
    "markdownContent": """# Free-Body Diagrams

A free-body diagram (FBD) shows **one object** and **every force acting on it**, nothing else. Once you have it,
Newton's second law is just bookkeeping:

$$\\sum \\vec F = m\\vec a$$

## How to draw one

1. **Isolate the object.** Draw it as a dot or a simple shape, cut off from everything it touches.
2. **Gravity first.** Every object near Earth has weight $W = mg$, pointing straight down.
3. **Then every contact.** Each thing touching the object can push or pull on it:
   a floor pushes up with a normal force $N$, a spring pulls or pushes along its length, a string pulls with tension $T$.
4. **Then non-contact forces** like air drag, which always points opposite to the velocity.
5. **Never draw forces the object exerts on others.** Those belong on the other object's diagram.

## Three cases in the simulation

| Object | Forces | What the diagram tells you |
| --- | --- | --- |
| Box on the floor | $W$ down, $N$ up | At rest, so $N = W = mg$ |
| Mass on a spring | $W$ down, spring force up | At equilibrium $k\\,\\Delta x = mg$, so $\\Delta x = mg/k$ |
| Ball in flight | $W$ down, drag opposite to $\\vec v$ | No force pushes it forward; it only slows down |

## Worked example

A $2.0\\,\\text{kg}$ mass hangs from a spring with $k = 25\\,\\text{N/m}$. At rest, the FBD has the weight
$W = (2.0)(9.81) = 19.6\\,\\text{N}$ down and the spring force up. Equilibrium means they balance:

$$k\\,\\Delta x = mg \\quad\\Rightarrow\\quad \\Delta x = \\frac{19.6}{25} = 0.78\\,\\text{m}$$

## Common mistakes

> A thrown ball has **no force in its direction of motion**. Students often add a "force of the throw";
> that force ended when the ball left the hand. Look at the ball's diagram in the simulation: only weight and drag.

- Drawing the normal force as always equal to $mg$: it only is when nothing else pushes vertically and the object does not accelerate vertically.
- Forgetting that drag flips direction as the ball goes up and comes down.

## Try it

Turn on **Forces (free-body)** if it is off. Increase the mass $m$ and watch $W$ and $N$ grow together,
increase the drag coefficient $c$ and watch the ball's drag arrow lengthen, and add a push $F$ to the box.
""",
    "quiz": [
        {"question": "A ball is thrown upward and is still rising. Ignoring air resistance, which forces act on it?",
         "options": ["Only its weight, pointing down", "Its weight and an upward force from the throw",
                     "No forces, because it moves freely", "An upward force larger than its weight"],
         "correctAnswer": 0, "hint": "Which objects are touching it right now?",
         "explanation": "Once the ball leaves the hand nothing touches it; only gravity acts. The upward velocity is left over from the throw, not a force."},
        {"question": "A 3.0 kg box rests on a level floor while you push straight down on it with 10 N. What is the normal force? ($g = 9.81\\,\\text{m/s}^2$)",
         "options": ["29.4 N", "39.4 N", "19.4 N", "10 N"], "correctAnswer": 1,
         "hint": "Draw all the vertical forces on the box and set their sum to zero.",
         "explanation": "Up: $N$. Down: $mg = 29.4\\,\\text{N}$ plus your 10 N. Equilibrium gives $N = 39.4\\,\\text{N}$."},
        {"question": "Air drag on a moving object always points…",
         "options": ["Down", "Opposite to the object's velocity", "Opposite to its acceleration", "Toward the ground"],
         "correctAnswer": 1, "hint": "Watch the drag arrow on the ball in the simulation as it rises and falls.",
         "explanation": "Drag opposes motion through the air, so it is always antiparallel to the velocity."},
    ],
    "practice": [
        {"type": "numeric", "prompt": "A 1.5 kg mass hangs at rest from a spring with $k = 30\\,\\text{N/m}$. How far is the spring stretched? ($g = 9.81\\,\\text{m/s}^2$)",
         "answer": 0.49, "tolerance": 0.03, "unit": "m", "explanation": "$\\Delta x = mg/k = (1.5)(9.81)/30 = 0.49\\,\\text{m}$."},
        {"type": "order_steps", "prompt": "Put the steps for solving a dynamics problem with a free-body diagram in order.",
         "steps": ["Isolate the object you care about", "Draw its weight", "Draw every contact and non-contact force on it",
                   "Choose axes and resolve forces into components", "Apply $\\sum F = ma$ along each axis"],
         "explanation": "Isolate, draw all forces, choose axes, then apply Newton's second law per axis."},
        {"type": "true_false", "prompt": "The normal force on an object on a level floor is always equal to its weight.",
         "answer": False, "explanation": "Only if nothing else pushes vertically and it is not accelerating vertically; pushing down on it increases $N$."},
    ],
    "simulation": {
        "kind": "particles",
        "title": "Live free-body diagrams",
        "description": "Every arrow is a real force the simulation is using, drawn to scale. Change the mass, the spring stiffness, the drag and a push on the box, and watch each diagram respond.",
        "params": [
            {"name": "m", "label": "Mass of box and hanging mass", "min": 0.5, "max": 5, "value": 2, "step": 0.1, "unit": "kg"},
            {"name": "k", "label": "Spring stiffness", "min": 5, "max": 60, "value": 25, "step": 1, "unit": "N/m"},
            {"name": "c", "label": "Drag coefficient on the ball", "min": 0, "max": 0.3, "value": 0.08, "step": 0.01, "unit": "kg/m"},
            {"name": "F", "label": "Push on the box", "min": 0, "max": 20, "value": 0, "step": 0.5, "unit": "N"},
        ],
        "world": {"width": 12, "height": 7, "ground": True, "walls": True, "gravity": "9.81", "restitution": "0.4", "collisions": True},
        "bodies": [
            {"id": "box", "label": "Box", "x": "2", "y": "0.45", "mass": "m", "radius": "0.45", "color": "gold"},
            {"id": "anchor", "label": "Anchor", "x": "6.5", "y": "6.6", "fixed": True, "radius": "0.08", "color": "white"},
            {"id": "hang", "label": "Hanging mass", "x": "6.5", "y": "4.6", "mass": "m", "radius": "0.3", "color": "accent"},
            {"id": "ball", "label": "Ball", "x": "8.8", "y": "0.8", "vx": "2.5", "vy": "8", "mass": "0.5", "radius": "0.2", "color": "cyan", "trail": True},
        ],
        "forces": [
            {"type": "spring", "a": "anchor", "b": "hang", "k": "k", "rest": "1.2", "damping": "0.6"},
            {"type": "drag", "body": "ball", "coef": "c", "power": "2"},
            {"type": "uniform", "fx": "F", "fy": "0", "bodies": ["box"]},
        ],
        "readouts": [
            {"label": "Spring stretch", "expr": "6.6 - hang.y - 1.2", "unit": "m"},
            {"label": "Expected mg/k", "expr": "m*9.81/k", "unit": "m"},
            {"label": "Ball speed", "expr": "ball.speed", "unit": "m/s"},
        ],
        "overlays": {"fbd": True},
    },
}

# ---------------------------------------------------------------- momentum conservation
momentum = {
    "id": "momentum-conservation",
    "title": "Momentum Conservation in Collisions",
    "category": "Classical Mechanics",
    "difficulty": "Introductory",
    "summary": "In a collision the total momentum never changes; only kinetic energy can be lost. Collide two carts with any masses, speeds and bounciness and watch the total stay put.",
    "cheatSheet": [
        {"label": "Momentum", "formula": "\\vec p = m\\vec v"},
        {"label": "Conservation", "formula": "m_1 v_1 + m_2 v_2 = m_1 v_1' + m_2 v_2'"},
        {"label": "Coefficient of restitution", "formula": "e = \\frac{v_2' - v_1'}{v_1 - v_2}"},
        {"label": "Perfectly inelastic", "formula": "v' = \\frac{m_1 v_1 + m_2 v_2}{m_1 + m_2}"},
    ],
    "mermaid": "graph TD\n  A[\"No external force on the pair\"] --> B[\"Total momentum is constant\"]\n  B --> C[\"Elastic e = 1: KE also kept\"]\n  B --> D[\"Inelastic e < 1: some KE becomes heat and sound\"]",
    "markdownContent": """# Momentum Conservation in Collisions

Momentum is mass times velocity, $\\vec p = m\\vec v$. During a collision the two objects push on each other with
equal and opposite forces (Newton's third law), for the same short time. So whatever momentum one gains,
the other loses, and the **total stays the same**:

$$m_1 v_1 + m_2 v_2 = m_1 v_1' + m_2 v_2'$$

This holds for every collision, bouncy or sticky, as long as no outside force acts during the impact.

## Elastic or inelastic: what changes is energy

The coefficient of restitution $e$ says how bouncy the collision is:

$$e = \\frac{v_2' - v_1'}{v_1 - v_2}$$

| $e$ | Name | Kinetic energy |
| --- | --- | --- |
| 1 | Elastic | Kept |
| between 0 and 1 | Inelastic | Partly lost |
| 0 | Perfectly inelastic: objects move together | Most lost |

## Worked example

A $2\\,\\text{kg}$ cart at $3\\,\\text{m/s}$ hits a $1\\,\\text{kg}$ cart moving at $-1\\,\\text{m/s}$, and they stick ($e = 0$):

$$v' = \\frac{(2)(3) + (1)(-1)}{2 + 1} = \\frac{5}{3} = 1.67\\,\\text{m/s}$$

Kinetic energy before: $\\tfrac12(2)(3^2) + \\tfrac12(1)(1^2) = 9.5\\,\\text{J}$. After: $\\tfrac12(3)(1.67^2) = 4.2\\,\\text{J}$.
Momentum is the same, $5\\,\\text{kg·m/s}$, but $5.3\\,\\text{J}$ of kinetic energy turned into heat and sound.

## Common mistakes

> "In an inelastic collision momentum is lost." No: momentum is conserved in **every** collision. Kinetic energy is what gets lost.

- Forgetting signs: a cart moving left has negative velocity and negative momentum.

## Try it

Keep **Momentum** and **Energy** switched on. Slide $e$ from 1 down to 0: the gold total-momentum arrow and the $p$ readout do not change, while the energy panel shows a growing **lost** bar.
""",
    "quiz": [
        {"question": "Two carts collide and stick together. What happens to the total momentum of the two carts?",
         "options": ["It stays the same", "It decreases, because they stick", "It increases", "It becomes zero"],
         "correctAnswer": 0, "hint": "Compare the forces the carts exert on each other.",
         "explanation": "The carts exert equal and opposite forces on each other for the same time, so total momentum is conserved; it is kinetic energy that decreases."},
        {"question": "A 3 kg cart at 4 m/s collides with a 1 kg cart at rest and they stick. What is their common speed?",
         "options": ["4 m/s", "3 m/s", "2 m/s", "1 m/s"], "correctAnswer": 1,
         "hint": "Total momentum before = total momentum after.",
         "explanation": "$v' = (3)(4)/(3+1) = 3\\,\\text{m/s}$."},
        {"question": "In the simulation, lowering $e$ from 1 to 0 changes which quantity after the collision?",
         "options": ["Total momentum", "Total kinetic energy", "Both", "Neither"], "correctAnswer": 1,
         "hint": "Watch the momentum readout and the energy panel while you move the slider.",
         "explanation": "Momentum is conserved for every value of $e$; the energy lost in the collision grows as $e$ falls."},
    ],
    "practice": [
        {"type": "numeric", "prompt": "A 2 kg cart at 3 m/s hits a 1 kg cart moving at $-1$ m/s and they stick. What is their velocity afterwards?",
         "answer": 1.667, "tolerance": 0.02, "unit": "m/s", "explanation": "$v' = (2\\cdot 3 + 1\\cdot(-1))/3 = 5/3 \\approx 1.67\\,\\text{m/s}$."},
        {"type": "fill_blank", "prompt": "In every collision without outside forces, total ___ is conserved.",
         "options": ["momentum", "kinetic energy", "velocity", "speed"], "answer": "momentum",
         "explanation": "Momentum is always conserved; kinetic energy only in elastic collisions."},
        {"type": "true_false", "prompt": "In a perfectly elastic collision, both momentum and kinetic energy are conserved.",
         "answer": True, "explanation": "That is the definition of an elastic collision ($e = 1$)."},
    ],
    "simulation": {
        "kind": "particles",
        "title": "Two carts on a frictionless track",
        "description": "Set the masses, starting velocities and bounciness e, then press Reset. The gold arrow is the total momentum; the energy panel shows how much kinetic energy each collision loses.",
        "params": [
            {"name": "m1", "label": "Mass of cart A", "min": 0.5, "max": 5, "value": 2, "step": 0.1, "unit": "kg"},
            {"name": "m2", "label": "Mass of cart B", "min": 0.5, "max": 5, "value": 1, "step": 0.1, "unit": "kg"},
            {"name": "v1", "label": "Velocity of A", "min": 0, "max": 6, "value": 3, "step": 0.1, "unit": "m/s"},
            {"name": "v2", "label": "Velocity of B", "min": -6, "max": 6, "value": -1, "step": 0.1, "unit": "m/s"},
            {"name": "e", "label": "Bounciness e", "min": 0, "max": 1, "value": 1, "step": 0.05, "unit": ""},
        ],
        "world": {"width": 16, "height": 3, "ground": False, "walls": False, "gravity": "0", "restitution": "e", "collisions": True},
        "bodies": [
            {"id": "a", "label": "A", "x": "4", "y": "1.5", "vx": "v1", "mass": "m1", "radius": "0.25 + 0.08*m1", "color": "gold", "trail": True},
            {"id": "b", "label": "B", "x": "10", "y": "1.5", "vx": "v2", "mass": "m2", "radius": "0.25 + 0.08*m2", "color": "cyan", "trail": True},
        ],
        "readouts": [
            {"label": "Total momentum", "expr": "a.m*a.vx + b.m*b.vx", "unit": "kg m/s"},
            {"label": "Total kinetic energy", "expr": "0.5*a.m*a.speed^2 + 0.5*b.m*b.speed^2", "unit": "J"},
            {"label": "v of A", "expr": "a.vx", "unit": "m/s"},
            {"label": "v of B", "expr": "b.vx", "unit": "m/s"},
        ],
        "series": [
            {"label": "total p", "expr": "a.m*a.vx + b.m*b.vx", "color": "gold"},
            {"label": "total KE", "expr": "0.5*a.m*a.speed^2 + 0.5*b.m*b.speed^2", "color": "cyan"},
        ],
        "overlays": {"momentum": True, "energy": True},
    },
}

# ---------------------------------------------------------------- energy conservation
energy = {
    "id": "energy-conservation-pendulum",
    "title": "Energy Conservation: the Pendulum",
    "category": "Classical Mechanics",
    "difficulty": "Introductory",
    "summary": "A swinging pendulum trades potential energy for kinetic energy and back; the total stays constant until friction takes some away. Watch the energy bars move in real time.",
    "cheatSheet": [
        {"label": "Kinetic energy", "formula": "K = \\tfrac12 m v^2"},
        {"label": "Gravitational potential energy", "formula": "U = mgh"},
        {"label": "Conservation", "formula": "K_1 + U_1 = K_2 + U_2"},
        {"label": "Speed at the bottom", "formula": "v = \\sqrt{2gL(1-\\cos\\theta_0)}"},
    ],
    "mermaid": "graph LR\n  A[\"Top: all potential\"] --> B[\"Swinging down: U becomes K\"]\n  B --> C[\"Bottom: most kinetic\"]\n  C --> D[\"Swinging up: K becomes U\"]\n  D --> A",
    "markdownContent": """# Energy Conservation: the Pendulum

Energy is never created or destroyed; it changes form. For a pendulum the two forms are

$$K = \\tfrac12 m v^2 \\qquad U = mgh$$

and without friction their sum, the **mechanical energy**, is constant:

$$K_1 + U_1 = K_2 + U_2$$

## Why the rod does no work

The rod's tension always points along the rod, perpendicular to the bob's motion, so it does no work. Only gravity
does work, and gravity's work is exactly the change in $U$. That is why energy is conserved here even though the rod
pulls with a large, changing force (turn on **Forces** to see it).

## Worked example

Release a pendulum of length $L = 2\\,\\text{m}$ from $\\theta_0 = 45^\\circ$. It drops a height
$h = L(1 - \\cos\\theta_0) = 2(1 - 0.707) = 0.586\\,\\text{m}$, so at the bottom

$$v = \\sqrt{2gh} = \\sqrt{2(9.81)(0.586)} = 3.39\\,\\text{m/s}$$

Notice the mass cancels: a heavy and a light bob swing at the same speed.

## When energy is lost

With air drag ($c > 0$) some mechanical energy becomes heat every swing. The total bar shrinks and the **lost** bar
grows by exactly the same amount: energy is still conserved, it has just left the pendulum.

## Common mistakes

> The fastest point is the **bottom**, where $U$ is smallest, not the moment of release.

- Measuring $h$ from the pivot instead of from the lowest point of the swing.

## Try it

Watch the energy panel as the bob swings: KE and PE trade places while the total stays flat. Then raise the drag $c$.
""",
    "quiz": [
        {"question": "Where is the pendulum bob moving fastest?",
         "options": ["At the release point", "At the lowest point of the swing", "Halfway down", "At the highest point on the other side"],
         "correctAnswer": 1, "hint": "Where is the potential energy smallest?",
         "explanation": "With the total fixed, kinetic energy is largest where potential energy is smallest: the bottom."},
        {"question": "A pendulum of length 1.0 m is released from 60°. What is its speed at the bottom? ($g = 9.81\\,\\text{m/s}^2$)",
         "options": ["1.57 m/s", "3.13 m/s", "4.43 m/s", "9.81 m/s"], "correctAnswer": 1,
         "hint": "$h = L(1-\\cos\\theta_0)$, then $v = \\sqrt{2gh}$.",
         "explanation": "$h = 1.0(1 - 0.5) = 0.5\\,\\text{m}$, so $v = \\sqrt{2(9.81)(0.5)} = 3.13\\,\\text{m/s}$."},
        {"question": "Why does the rod's tension do no work on the bob?",
         "options": ["Tension is small", "Tension is always perpendicular to the bob's velocity", "The rod is massless", "Tension cancels gravity"],
         "correctAnswer": 1, "hint": "Work is $\\vec F \\cdot \\vec d$.",
         "explanation": "The bob moves along a circle, always perpendicular to the rod, so $\\vec T \\cdot d\\vec s = 0$."},
    ],
    "practice": [
        {"type": "numeric", "prompt": "A 0.5 kg bob on a 2 m pendulum is released from 30°. How much potential energy does it lose by the bottom? ($g = 9.81\\,\\text{m/s}^2$)",
         "answer": 1.314, "tolerance": 0.03, "unit": "J", "explanation": "$h = 2(1 - \\cos 30^\\circ) = 0.268\\,\\text{m}$, $\\Delta U = mgh = 0.5(9.81)(0.268) = 1.31\\,\\text{J}$."},
        {"type": "true_false", "prompt": "Doubling the bob's mass doubles its speed at the bottom of the swing.",
         "answer": False, "explanation": "Mass cancels in $mgh = \\tfrac12 m v^2$; the speed is the same."},
    ],
    "simulation": {
        "kind": "particles",
        "title": "Pendulum energy",
        "description": "The energy panel shows kinetic, potential and total energy as the bob swings. Raise the drag to see energy leave the pendulum as heat.",
        "params": [
            {"name": "L", "label": "Length", "min": 0.5, "max": 3, "value": 2, "step": 0.1, "unit": "m"},
            {"name": "th", "label": "Release angle", "min": 10, "max": 80, "value": 45, "step": 1, "unit": "deg"},
            {"name": "c", "label": "Air drag", "min": 0, "max": 0.5, "value": 0, "step": 0.02, "unit": "kg/s"},
        ],
        "world": {"width": 7, "height": 5, "ground": False, "walls": False, "gravity": "9.81"},
        "bodies": [
            {"id": "pivot", "label": "Pivot", "x": "3.5", "y": "4.7", "fixed": True, "radius": "0.06", "color": "white"},
            {"id": "bob", "label": "Bob", "x": "3.5 + L*sin(th*pi/180)", "y": "4.7 - L*cos(th*pi/180)", "mass": "1", "radius": "0.15", "color": "gold", "trail": True},
        ],
        "links": [{"type": "rod", "a": "pivot", "b": "bob", "length": "L"}],
        "forces": [{"type": "drag", "body": "bob", "coef": "c", "power": "1"}],
        "readouts": [
            {"label": "Speed", "expr": "bob.speed", "unit": "m/s"},
            {"label": "Height above lowest point", "expr": "bob.y - (4.7 - L)", "unit": "m"},
            {"label": "Predicted max speed", "expr": "sqrt(2*9.81*L*(1 - cos(th*pi/180)))", "unit": "m/s"},
        ],
        "series": [
            {"label": "KE", "expr": "0.5*bob.m*bob.speed^2", "color": "cyan"},
            {"label": "PE", "expr": "bob.m*9.81*(bob.y - (4.7 - L))", "color": "gold"},
        ],
        "overlays": {"energy": True},
    },
}

# ---------------------------------------------------------------- material stress (cantilever truss)
cols, dx, top_y, bot_y = 6, 1.6, 3.4, 2.0
bodies, forces = [], []
for i in range(cols):
    x = 1 + dx * i
    fixed = i == 0
    bodies.append({"id": f"t{i}", "label": f"t{i}", "x": f"{x}", "y": f"{top_y}", "mass": "1", "radius": "0.09", "fixed": fixed, "color": "white" if fixed else "gold"})
    bodies.append({"id": f"b{i}", "label": f"b{i}", "x": f"{x}", "y": f"{bot_y}", "mass": "1", "radius": "0.09", "fixed": fixed, "color": "white" if fixed else "gold"})
diag = math.hypot(dx, top_y - bot_y)
for i in range(cols - 1):
    for a, b, rest in ((f"t{i}", f"t{i+1}", dx), (f"b{i}", f"b{i+1}", dx), (f"t{i}", f"b{i+1}", diag)):
        forces.append({"type": "spring", "a": a, "b": b, "k": "k", "rest": f"{rest:.4f}", "damping": "30"})
for i in range(1, cols):
    forces.append({"type": "spring", "a": f"t{i}", "b": f"b{i}", "k": "k", "rest": f"{top_y - bot_y}", "damping": "30"})
forces.append({"type": "uniform", "fx": "0", "fy": "-P", "bodies": [f"b{cols - 1}"]})

stress = {
    "id": "material-stress-truss",
    "title": "Stress and Strain in a Loaded Truss",
    "category": "Mechanics of Materials",
    "difficulty": "Intermediate",
    "summary": "Hang a load on the tip of a cantilever truss and see which members stretch (tension) and which squeeze (compression). Stress, strain and stiffness made visible.",
    "cheatSheet": [
        {"label": "Normal stress", "formula": "\\sigma = \\frac{F}{A}"},
        {"label": "Strain", "formula": "\\varepsilon = \\frac{\\Delta L}{L_0}"},
        {"label": "Hooke's law (material)", "formula": "\\sigma = E\\,\\varepsilon"},
        {"label": "Member stiffness", "formula": "k = \\frac{EA}{L_0}"},
        {"label": "Bending: top and bottom", "formula": "\\sigma_{\\text{top}} > 0,\\ \\sigma_{\\text{bottom}} < 0"},
    ],
    "mermaid": "graph TD\n  A[\"Load P at the tip\"] --> B[\"Truss bends down\"]\n  B --> C[\"Top chord stretches: tension\"]\n  B --> D[\"Bottom chord squeezes: compression\"]\n  C --> E[\"Largest strain near the wall\"]\n  D --> E",
    "markdownContent": """# Stress and Strain in a Loaded Truss

When a structure carries a load, every member carries an internal force. Engineers describe it with two numbers:

$$\\sigma = \\frac{F}{A} \\quad\\text{(stress)} \\qquad \\varepsilon = \\frac{\\Delta L}{L_0} \\quad\\text{(strain)}$$

Stress is force per area (pascals); strain is the fractional change in length (no units). For most materials,
while the load is small, they are proportional, with the **Young's modulus** $E$:

$$\\sigma = E\\,\\varepsilon$$

Steel has $E \\approx 200\\,\\text{GPa}$, aluminium $70\\,\\text{GPa}$, wood around $10\\,\\text{GPa}$.

## Tension and compression

- **Tension**: the member is pulled and gets longer, $\\varepsilon > 0$ (red in the simulation).
- **Compression**: the member is pushed and gets shorter, $\\varepsilon < 0$ (blue).

## The cantilever

The truss is fixed to a wall on the left and loaded at the right tip. It bends downward, like a diving board.
Bending **stretches the top** and **squeezes the bottom**, and the effect is largest **near the wall**, where the
lever arm of the load is longest: the bending moment there is $M = P\\,\\ell$.

## Worked example

A steel member with cross-section $A = 2\\,\\text{cm}^2 = 2\\times10^{-4}\\,\\text{m}^2$ carries $F = 10\\,\\text{kN}$ in tension:

$$\\sigma = \\frac{10^4}{2\\times10^{-4}} = 50\\,\\text{MPa} \\qquad \\varepsilon = \\frac{\\sigma}{E} = \\frac{50\\times10^6}{200\\times10^9} = 2.5\\times10^{-4}$$

That is a stretch of $0.025\\,\\%$: real structures deform very little. The simulation exaggerates strain so you can see it.

## Common mistakes

> A member's stiffness depends on its geometry, not only its material: $k = EA/L_0$. A long, thin member is much softer than a short, thick one of the same steel.

- Assuming every member carries the load equally: the members near the wall work hardest.

## Try it

Turn on **Stress** (it starts on). Increase the load $P$ and watch the colors deepen, most near the wall.
Increase the stiffness $k$: the same load now causes less strain and a smaller tip deflection.
""",
    "quiz": [
        {"question": "A cantilever truss is loaded downward at its tip. Which chord is in tension?",
         "options": ["The top chord", "The bottom chord", "Both chords", "Neither; only the diagonals carry load"],
         "correctAnswer": 0, "hint": "Which side of a bending diving board gets longer?",
         "explanation": "Bending downward stretches the top chord (tension) and shortens the bottom chord (compression)."},
        {"question": "A rod of original length 2.0 m stretches by 1.0 mm. What is its strain?",
         "options": ["$5\\times10^{-4}$", "$2\\times10^{-3}$", "$5\\times10^{-2}$", "$1\\times10^{-3}$"], "correctAnswer": 0,
         "hint": "$\\varepsilon = \\Delta L / L_0$ with both in metres.",
         "explanation": "$\\varepsilon = 0.001 / 2.0 = 5\\times10^{-4}$."},
        {"question": "Where are the members of the loaded cantilever most strained?",
         "options": ["Near the loaded tip", "Near the wall", "In the middle", "Equally everywhere"], "correctAnswer": 1,
         "hint": "Where is the bending moment $M = P\\ell$ largest?",
         "explanation": "The lever arm of the tip load is longest at the wall, so the bending moment and the chord forces are largest there."},
    ],
    "practice": [
        {"type": "numeric", "prompt": "A steel bar ($E = 200\\,\\text{GPa}$) is under a stress of 100 MPa. What is its strain?",
         "answer": 0.0005, "tolerance": 0.02, "unit": "", "explanation": "$\\varepsilon = \\sigma/E = 100\\times10^6 / 200\\times10^9 = 5\\times10^{-4}$."},
        {"type": "fill_blank", "prompt": "A member that gets shorter under load is in ___.",
         "options": ["compression", "tension", "shear", "torsion"], "answer": "compression",
         "explanation": "Shortening means negative strain: compression."},
        {"type": "true_false", "prompt": "Doubling a member's cross-sectional area halves its stress for the same force.",
         "answer": True, "explanation": "$\\sigma = F/A$: twice the area, half the stress."},
    ],
    "simulation": {
        "kind": "particles",
        "title": "Cantilever truss under a tip load",
        "description": "Members are colored by strain: red stretched (tension), blue squeezed (compression). Increase the load P or lower the stiffness k and watch where the truss works hardest.",
        "params": [
            {"name": "P", "label": "Tip load P", "min": 0, "max": 200, "value": 80, "step": 5, "unit": "N"},
            {"name": "k", "label": "Member stiffness k", "min": 3000, "max": 20000, "value": 8000, "step": 500, "unit": "N/m"},
        ],
        "world": {"width": 10.5, "height": 4.5, "ground": False, "walls": False, "gravity": "0", "collisions": False},
        "bodies": bodies,
        "forces": forces,
        "readouts": [
            {"label": "Tip deflection", "expr": f"{bot_y} - b{cols - 1}.y", "unit": "m"},
            {"label": "Top chord strain at wall", "expr": f"(t1.x - t0.x - {dx}) / {dx}", "unit": ""},
            {"label": "Bottom chord strain at wall", "expr": f"(b1.x - b0.x - {dx}) / {dx}", "unit": ""},
        ],
        "overlays": {"stress": True},
    },
}

for t in (fbd, momentum, energy, stress):
    post(t)
