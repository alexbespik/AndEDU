"""Moral perspectives (Philosophy) and the Psychology subject: offline content, no model calls.

Data lives here (a root module, so the desktop bundle carries it) and is served read-only:
  GET /api/philosophy/moral-dilemmas   dilemmas on a left-right axis with four ethical frameworks
  GET /api/psychology/units            morale, perspective-taking and moral-psychology content

Rules (ARCHITECTURE.md 3.12): value claims are never ranked. A dilemma has no right answer, nothing here is
scored or pays XP, and a framework's `band` on the axis is a rough tendency of how that framework is often
argued, never a verdict. The morale simulation is a teaching toy that shows the idea, not an empirical model.
Studies are described in general terms and named only when they are well-documented classics.
"""
from typing import Any, Dict, List

import simspec

AXIS = {"left": "Cautious / pacifist", "right": "Hard-line",
        "note": "Neither end is better. The axis only shows how far an answer leans toward restraint or toward force."}

FRAMEWORKS = {
    "utilitarian": "Consequences (utilitarian)",
    "kantian": "Duty and rights (Kantian)",
    "virtue": "Character (virtue ethics)",
    "care": "Relationships (care ethics)",
}

DILEMMAS: List[Dict[str, Any]] = [
    {
        "id": "defend-the-village",
        "title": "Defend the village",
        "setup": "Raiders will reach a village by night. The villagers can flee into the hills and lose their homes and harvest, "
                 "or stay and fight with old weapons, which will likely save the homes but cost some lives on both sides.",
        "question": "What should the villagers do?",
        "frameworks": {
            "utilitarian": {"argues": "Count the expected harms: lives lost in a fight against a winter without food or shelter. "
                                       "The answer depends on the numbers, and it can point either way.", "band": [30, 75]},
            "kantian": {"argues": "Self-defence against an unjust attack is permitted, but no one may be used as a mere means, "
                                  "so no villager should be forced to fight against their will.", "band": [40, 70]},
            "virtue": {"argues": "Courage sits between cowardice and recklessness: the brave choice is the one that fits the real odds, "
                                 "not the most heroic-looking one.", "band": [35, 70]},
            "care": {"argues": "Start from who depends on whom: children, the old and the sick. Whatever keeps those bonds intact "
                               "matters more than the property.", "band": [10, 45]},
        },
        "reflect": ["Would your answer change if fleeing meant certain starvation?",
                    "Is defending property different from defending people?"],
    },
    {
        "id": "the-informant",
        "title": "The informant",
        "setup": "You learn that a friend is about to leak documents that expose real wrongdoing by your employer, "
                 "but the leak will also reveal the names of colleagues who did nothing wrong.",
        "question": "Do you stop your friend, report them, or stay out of it?",
        "frameworks": {
            "utilitarian": {"argues": "Weigh the public good of exposing the wrongdoing against the harm to the named colleagues; "
                                       "a redacted leak may get most of the good with less harm.", "band": [30, 60]},
            "kantian": {"argues": "Truthfulness and respect for persons both matter: exposing wrongdoing can be a duty, "
                                  "but carelessly exposing innocent people treats them as mere means.", "band": [35, 65]},
            "virtue": {"argues": "Loyalty, honesty and justice pull apart here; a practically wise person looks for the act "
                                 "that honours all three as far as possible, such as urging your friend to redact.", "band": [25, 55]},
            "care": {"argues": "Talk to your friend first: the relationship and the people who could be hurt come before an "
                               "abstract rule about reporting.", "band": [10, 40]},
        },
        "reflect": ["Does it matter whether you would also be named?",
                    "What would you want a friend to do in your place?"],
    },
    {
        "id": "quarantine-the-town",
        "title": "Quarantine the town",
        "setup": "A dangerous illness appears in one town. Closing the roads would slow its spread to the region, "
                 "but the town would run short of medicine and its people could not leave.",
        "question": "Should the authorities close the roads?",
        "frameworks": {
            "utilitarian": {"argues": "If the closure prevents far more illness than it causes, it is justified, as long as "
                                       "supplies get in.", "band": [55, 85]},
            "kantian": {"argues": "Restricting free movement needs a reason everyone could accept, including the people "
                                  "inside; a closure without medicine for them fails that test.", "band": [35, 65]},
            "virtue": {"argues": "Good leaders act with prudence and fairness: decisive, but sharing the burden rather than "
                                 "abandoning one town.", "band": [45, 75]},
            "care": {"argues": "Those inside are not a problem to be contained but people who need care; any closure must "
                               "come with support for them.", "band": [20, 55]},
        },
        "reflect": ["Would you accept the closure if you lived inside the town?",
                    "Who should decide, and how long should it last?"],
    },
    {
        "id": "the-deserter",
        "title": "The deserter",
        "setup": "During a war a young soldier runs from the front line, saying he could not bring himself to shoot at people. "
                 "His unit held the line without him, but two of his friends were wounded.",
        "question": "How should he be treated?",
        "frameworks": {
            "utilitarian": {"argues": "Ask what the response achieves: harsh punishment may deter desertion, while leniency may "
                                       "save a life and recognise real conscience. Look at the effects of each.", "band": [30, 70]},
            "kantian": {"argues": "He broke a promise he had made, but forcing a person to kill against conscience is itself "
                                  "a wrong; a duty-based view often separates the broken promise from the refusal to kill.", "band": [25, 60]},
            "virtue": {"argues": "Was it cowardice or conscience? Character ethics asks what kind of person acts this way, and "
                                 "the same act can come from either.", "band": [30, 65]},
            "care": {"argues": "Look at the relationships: his wounded friends, his family, his fear. Responsibility can be "
                               "owed without cruelty.", "band": [5, 40]},
        },
        "reflect": ["Is refusing to kill different from refusing to serve?",
                    "Should his friends' wounds change the judgment?"],
    },
    {
        "id": "the-last-lifeboat",
        "title": "The last lifeboat",
        "setup": "A lifeboat holds eight people safely and now carries ten. A storm is coming. If nobody leaves, the boat "
                 "will probably sink; if two people go into the water, the rest will probably survive.",
        "question": "What should the people in the boat do?",
        "frameworks": {
            "utilitarian": {"argues": "Eight saved is better than ten lost, so a fair way of choosing who leaves is "
                                       "justified if the odds are as stated.", "band": [55, 90]},
            "kantian": {"argues": "No one may be thrown overboard: each person has a dignity that cannot be traded. "
                                  "Volunteering is different from being forced.", "band": [10, 40]},
            "virtue": {"argues": "Justice and courage matter: a fair lottery, or someone choosing to sacrifice "
                                 "themselves, looks very different from the strong deciding for the weak.", "band": [30, 65]},
            "care": {"argues": "Who is in the boat matters to the people in it: a parent and a child cannot be "
                               "treated as interchangeable units.", "band": [15, 50]},
        },
        "reflect": ["Does a lottery make a forced choice fair?",
                    "Is it different if someone volunteers?"],
    },
    {
        "id": "strict-or-gentle",
        "title": "Strict or gentle teacher",
        "setup": "A student has copied homework several times. A strict response (a failing grade and a report) would set "
                 "a clear example; a gentle one (a private talk and a second chance) might help the student more.",
        "question": "What should the teacher do?",
        "frameworks": {
            "utilitarian": {"argues": "Which response leads to the most learning and the least cheating overall, for this "
                                       "student and the class?", "band": [35, 70]},
            "kantian": {"argues": "Rules should apply equally to everyone, so a consistent, announced consequence matters, "
                                  "delivered with respect.", "band": [50, 80]},
            "virtue": {"argues": "A good teacher is both just and kind: the response should help the student become "
                                 "honest, not just punish the act.", "band": [30, 60]},
            "care": {"argues": "Find out why it happened; the relationship and the student's situation come first.",
                     "band": [5, 35]},
        },
        "reflect": ["What would actually stop the copying?",
                    "Is fairness to the other students a reason for strictness?"],
    },
]

# A toy model to explore the idea, not an empirical one: morale moves toward a level set by pressure, cohesion and
# leadership, faster in close-knit groups. The break line marks where a group starts to come apart.
MORALE_SIM = {
    "kind": "graph",
    "title": "Morale under pressure",
    "description": "A teaching toy, not real data. Raise the pressure and watch morale fall toward the break line; "
                   "then add cohesion or leadership and see where it settles instead. Cohesion also makes the group "
                   "react faster, in both directions.",
    "x": {"min": 0, "max": 20, "label": "weeks"},
    "y": {"min": 0, "max": 100, "label": "morale"},
    "params": [
        {"name": "P", "label": "Pressure", "min": 0, "max": 1, "value": 0.6, "step": 0.05},
        {"name": "C", "label": "Cohesion", "min": 0, "max": 1, "value": 0.4, "step": 0.05},
        {"name": "L", "label": "Leadership", "min": 0, "max": 1, "value": 0.4, "step": 0.05},
        {"name": "M0", "label": "Starting morale", "min": 0, "max": 100, "value": 70, "step": 1},
    ],
    "curves": [
        {"expr": "clamp(40 + 35*C + 25*L - 60*P, 0, 100) + (M0 - clamp(40 + 35*C + 25*L - 60*P, 0, 100))*exp(-(0.15 + 0.5*C)*x)",
         "label": "morale", "color": "accent"},
        {"expr": "clamp(40 + 35*C - 60*P, 0, 100) + (M0 - clamp(40 + 35*C - 60*P, 0, 100))*exp(-(0.15 + 0.5*C)*x)",
         "label": "same group, no leadership", "color": "muted"},
        {"expr": "30", "label": "break line", "color": "pink"},
    ],
}

PSYCHOLOGY_UNITS: List[Dict[str, Any]] = [
    {
        "id": "morale",
        "title": "Morale",
        "intro": "Morale is a group's shared confidence and will to keep going. It is not the same as happiness: a team "
                 "can be tired and unhappy yet hold together, or comfortable and still fall apart.",
        "points": [
            {"title": "Pressure", "text": "Danger, loss, exhaustion and uncertainty wear morale down, especially when they "
                                          "seem to have no end or no purpose."},
            {"title": "Cohesion", "text": "People often keep going for the people next to them. Close bonds in a small "
                                          "group are one of the strongest supports of morale, and they also let fear spread fast."},
            {"title": "Leadership", "text": "Leaders who share the hardship, explain the purpose and treat people fairly "
                                            "tend to steady a group; unfair or absent leadership tends to drain it."},
            {"title": "Meaning", "text": "A goal people believe in makes the same hardship easier to carry."},
            {"title": "Break point", "text": "Morale rarely fades evenly. Groups often hold on and then come apart quickly "
                                             "once enough people stop believing the effort is worth it."},
        ],
        "simulation": MORALE_SIM,
        "reflect": ["Think of a team you were part of under pressure. What held it together?",
                    "Can high morale be a bad thing, for example when it keeps a group on a wrong course?"],
    },
    {
        "id": "perspective",
        "title": "Perspective-taking",
        "intro": "The same event looks different from each person's position. Perspective-taking means imagining how a "
                 "situation looks and feels to someone else, which is different from agreeing with them.",
        "cases": [
            {"id": "late-project", "event": "A group project is handed in a day late.",
             "views": [
                 {"who": "The student who did most of the work", "sees": "I carried the team and we still got marked down."},
                 {"who": "The student who was ill that week", "sees": "I could not help it, and nobody asked how I was."},
                 {"who": "The teacher", "sees": "The deadline was clear, and every other group managed it."}],
             "reflect": "Which view did you take first? What would each person need to hear?"},
            {"id": "factory-closing", "event": "A town's main factory announces it will close next year.",
             "views": [
                 {"who": "A worker with twenty years there", "sees": "My skills and my whole life are tied to this place."},
                 {"who": "The company's owner", "sees": "We have lost money for years; keeping it open would sink the rest of the firm."},
                 {"who": "A teenager in the town", "sees": "Maybe this is the push to leave, or maybe there is nothing left to come back to."}],
             "reflect": "Is anyone in this story simply wrong? What would a fair response look like to all three?"},
            {"id": "ceasefire", "event": "Two sides in a long conflict agree to a ceasefire.",
             "views": [
                 {"who": "A soldier on the front", "sees": "Relief, and fear that it will not hold."},
                 {"who": "A family who lost someone", "sees": "Was the loss for nothing if it ends like this?"},
                 {"who": "A negotiator", "sees": "An imperfect deal that stops the dying is worth defending."}],
             "reflect": "Can you hold all three views as reasonable at once?"},
        ],
    },
    {
        "id": "moral-psychology",
        "title": "Moral psychology",
        "intro": "Moral psychology studies how people actually make moral judgments: what pushes them, what they notice "
                 "and what they miss. It describes; it does not tell you what is right.",
        "cards": [
            {"id": "obedience", "title": "Obedience to authority",
             "text": "In Stanley Milgram's obedience studies at Yale in the early 1960s, many participants kept following an "
                     "experimenter's instructions to give what they believed were painful shocks to another person. "
                     "The studies are famous and also debated, for their ethics and for how they were run."},
            {"id": "conformity", "title": "Conformity",
             "text": "In Solomon Asch's line-judgment experiments in the 1950s, people sometimes gave an answer they could "
                     "see was wrong because everyone else in the room had given it."},
            {"id": "bystander", "title": "The bystander effect",
             "text": "Darley and Latané's studies in the late 1960s found that people were less likely to help when they "
                     "believed others were also present: responsibility feels shared, so each person feels less of it."},
            {"id": "foundations", "title": "Moral foundations",
             "text": "Moral foundations theory (Jonathan Haidt and colleagues) proposes that moral intuitions draw on "
                     "several concerns, such as care, fairness, loyalty, authority, sanctity and liberty, and that people "
                     "and cultures weigh them differently."},
            {"id": "attribution", "title": "Fundamental attribution error",
             "text": "People tend to explain others' behaviour by their character (\"he is lazy\") and their own by the "
                     "situation (\"I was exhausted\"), a pattern Lee Ross named in the 1970s."},
            {"id": "dual-process", "title": "Fast and slow judgment",
             "text": "Many moral judgments come quickly, as a gut reaction, and reasoning arrives afterwards to justify "
                     "them. Slower reflection can change the first reaction, but it does not always."},
        ],
        "quiz": [
            {"id": "q1", "scenario": "Everyone in a meeting agrees with a plan you think is flawed, so you agree too.",
             "options": ["conformity", "obedience", "bystander", "attribution"], "answer": "conformity"},
            {"id": "q2", "scenario": "Dozens of people walk past someone who has collapsed, each assuming someone else will call for help.",
             "options": ["foundations", "bystander", "conformity", "dual-process"], "answer": "bystander"},
            {"id": "q3", "scenario": "A colleague is late and you think \"they are careless\"; when you are late you blame the traffic.",
             "options": ["attribution", "obedience", "bystander", "conformity"], "answer": "attribution"},
            {"id": "q4", "scenario": "A worker follows a manager's order to cut safety checks, saying \"I was told to\".",
             "options": ["dual-process", "conformity", "obedience", "foundations"], "answer": "obedience"},
            {"id": "q5", "scenario": "Two friends disagree about a law: one cares most that it is fair, the other that it respects tradition.",
             "options": ["foundations", "attribution", "bystander", "obedience"], "answer": "foundations"},
        ],
        "reflect": ["When did you last change your mind about a moral question, and what changed it?"],
    },
]


# ---------------------------------------------------------------- validation
def _band_ok(band: Any) -> bool:
    return (isinstance(band, list) and len(band) == 2 and all(isinstance(v, (int, float)) for v in band)
            and 0 <= band[0] < band[1] <= 100)


def validate_dilemma(d: Any) -> List[str]:
    """Every problem with one dilemma, or [] when it is usable."""
    if not isinstance(d, dict):
        return ["a dilemma must be an object"]
    where = d.get("id", "?")
    errors = [f"{where}: missing '{k}'" for k in ("id", "title", "setup", "question") if not str(d.get(k) or "").strip()]
    fw = d.get("frameworks")
    if not isinstance(fw, dict) or set(fw) != set(FRAMEWORKS):
        errors.append(f"{where}: frameworks must be exactly {sorted(FRAMEWORKS)}")
    else:
        for k, v in fw.items():
            if not isinstance(v, dict) or not str(v.get("argues") or "").strip():
                errors.append(f"{where}.{k}: needs 'argues'")
            elif not _band_ok(v.get("band")):
                errors.append(f"{where}.{k}: band must be [low, high] within 0-100")
    if not isinstance(d.get("reflect"), list):
        errors.append(f"{where}: reflect must be a list")
    return errors


def validate_content() -> List[str]:
    """All problems in the built-in content (tests call this)."""
    errors: List[str] = []
    ids = [d.get("id") for d in DILEMMAS]
    if len(ids) != len(set(ids)):
        errors.append("dilemma ids must be unique")
    for d in DILEMMAS:
        errors += validate_dilemma(d)
    for unit in PSYCHOLOGY_UNITS:
        sim = unit.get("simulation")
        if sim is not None:
            errors += [f"{unit['id']}.simulation: {e}" for e in simspec.validate_spec(sim)[1]]
        for q in unit.get("quiz") or []:
            card_ids = {c["id"] for c in unit.get("cards") or []}
            if q.get("answer") not in q.get("options", []) or not set(q.get("options", [])) <= card_ids:
                errors.append(f"{unit['id']}.{q.get('id')}: answer and options must be card ids, answer among options")
    return errors


def moral_dilemmas() -> Dict[str, Any]:
    return {"axis": AXIS, "frameworks": FRAMEWORKS, "dilemmas": DILEMMAS}


def psychology_units() -> Dict[str, Any]:
    units = []
    for unit in PSYCHOLOGY_UNITS:
        u = dict(unit)
        if "simulation" in u:
            u["simulation"] = simspec.validate_spec(u["simulation"])[0]
        units.append(u)
    return {"units": units}
