#!/usr/bin/env python3
"""
Example lessons for the eleven kits (literature, music, art_history, classics, rhetoric, polity, ee, ai, systems, stats,
bio: four practice types each, 44 in all) plus one free-body-diagram lesson. Nothing here calls a model.

    python3 scripts/seed_kits.py --dry-run   # normalize every lesson offline against a throwaway data folder; writes nothing
    python3 scripts/seed_kits.py             # POST each lesson to the running backend (ANDEDU_API, default 127.0.0.1:8090)

With accounts on, set ANDEDU_TOKEN to an admin session token. The lessons are library topics with ids kit-<kit>-sample
and kit-fbd-sample; running it again updates them in place (answer keys are computed by the server from these fields).
"""
import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API = os.environ.get("ANDEDU_API", "http://127.0.0.1:8090").rstrip("/")
TOKEN = os.environ.get("ANDEDU_TOKEN", "")

# kit -> (workspace the lesson opens in, category, title, practice items)
_SONNET = [
    "Shall I compare thee to a summer's day?", "Thou art more lovely and more temperate:",
    "Rough winds do shake the darling buds of May,", "And summer's lease hath all too short a date;",
    "Sometime too hot the eye of heaven shines,", "And often is his gold complexion dimm'd;",
    "And every fair from fair sometime declines,", "By chance or nature's changing course untrimm'd;",
    "But thy eternal summer shall not fade,", "Nor lose possession of that fair thou ow'st;",
    "Nor shall death brag thou wander'st in his shade,", "When in eternal lines to time thou grow'st:",
    "So long as men can breathe or eyes can see,", "So long lives this, and this gives life to thee.",
]

KITS = {
    "literature": ("literature", "Literature", "Reading poems closely", [
        {"type": "scansion", "prompt": "Mark each syllable of the line: 1 for stressed, 0 for unstressed.",
         "line": _SONNET[0], "meter": "iambic pentameter", "stress_pattern": "0 1 0 1 0 1 0 1 0 1",
         "explanation": "Five iambs (da-DUM), ten syllables."},
        {"type": "volta_spot", "prompt": "Which line (0 is the first) is the turn of the sonnet?", "lines": _SONNET,
         "target_index": 8, "explanation": "The octave describes summer's flaws; line 9 turns to what will not fade."},
        {"type": "rhyme_scheme_audit", "prompt": "Give the end-rhyme scheme of the first four lines (one letter per line).",
         "lines": _SONNET[:4], "rhyme_scheme": "A B A B", "explanation": "day / temperate / May / date."},
        {"type": "chronology_unravel", "prompt": "Put the events in the order they happened in the story.",
         "events": [{"id": "e1", "text": "Mara finds an unsent letter in the attic."},
                    {"id": "e2", "text": "Her father hides the letter in a trunk."},
                    {"id": "e3", "text": "Her father writes the letter to an old friend."}],
         "canonical_order": ["e3", "e2", "e1"], "explanation": "Written, then hidden, then found."},
    ]),
    "music": ("music", "Music", "Hearing and writing harmony", [
        {"type": "lint_satb_progression", "prompt": "List the voice-leading errors in this progression (codes like parallel_fifth:S_T:chord_1_to_2), or submit valid if there are none.",
         "chords": [{"s": "G4", "a": "E4", "t": "C4", "b": "C3"}, {"s": "A4", "a": "F4", "t": "D4", "b": "D3"}],
         "explanation": "Soprano and tenor, and soprano and bass, move in parallel fifths."},
        {"type": "roman_numeral_analysis", "prompt": "Label each chord with its Roman numeral.", "key": "C major",
         "chords": ["C", "F", "G", "C"], "expected": ["I", "IV", "V", "I"], "explanation": "A plain cadential progression."},
        {"type": "ear_interval_id", "prompt": "Listen to the two notes and name the interval.", "notes": ["C4", "G4"],
         "explanation": "Seven semitones: a perfect fifth."},
        {"type": "figured_bass_realize", "prompt": "Realize the figure in C major: write the two upper voices above the bass.",
         "bass_note": "E3", "figures": "6", "solution": ["G4", "C5"], "explanation": "A 6 above E is C; with the third, G."},
    ]),
    "art_history": ("art_history", "Art history", "Reading images and buildings", [
        {"type": "composition_vector", "prompt": "Click the centre of the cell diagram.", "image_url": "/diagrams/cell.svg",
         "focal_point": {"x": 0.5, "y": 0.5}, "tolerance": 0.1, "explanation": "The nucleus sits at the centre."},
        {"type": "label_architecture", "prompt": "Match each description to its Greek order.",
         "solution": {"capital with a plain cushion": "Doric", "capital with scroll-like volutes": "Ionic",
                      "capital of acanthus leaves": "Corinthian"}, "explanation": "Doric, Ionic, Corinthian."},
        {"type": "iconography_decode", "prompt": "Match each attribute to the saint it identifies.",
         "solution": {"keys": "Saint Peter", "wheel": "Saint Catherine", "lion": "Saint Mark"},
         "explanation": "Attributes are how saints are told apart in images."},
        {"type": "stylistic_taxonomy", "prompt": "Which period do these traits point to?",
         "traits": ["strong contrast of light and dark", "dramatic diagonal composition", "heightened emotion"],
         "period": "Baroque", "options": ["Renaissance", "Baroque", "Impressionism", "Gothic"],
         "explanation": "Chiaroscuro and drama mark the Baroque."},
    ]),
    "classics": ("classics", "Classics", "Rome and Athens at work", [
        {"type": "epigraphy_transcribe", "prompt": "Expand the abbreviation into the full Latin phrase.", "inscription_raw": "SPQR",
         "transcription": "Senatus Populusque Romanus", "language": "latin", "explanation": "The Senate and People of Rome."},
        {"type": "harris_matrix_build", "prompt": "Layers: topsoil lies over the floor; the floor lies over the foundation; the wall also stands on the foundation. Give each [above, below] pair.",
         "strata": ["Topsoil", "Floor", "Wall", "Foundation"],
         "solution": [["Topsoil", "Floor"], ["Floor", "Foundation"], ["Wall", "Foundation"]],
         "explanation": "Each pair is a direct stratigraphic relation."},
        {"type": "cursus_honorum_order", "prompt": "Order these offices from the first to the last of the career path.",
         "solution": ["Quaestor", "Aedile", "Praetor", "Consul"], "explanation": "The ladder of Roman magistracies."},
        {"type": "athenian_sortition_sim", "prompt": "Draw by lot: choose the stated number of citizens from each tribe.",
         "candidates": {"Erechtheis": ["Kallias", "Perikles", "Diodoros", "Lysias"], "Aigeis": ["Nikias", "Phormion", "Archelaos"]},
         "quotas": {"Erechtheis": 2, "Aigeis": 1}, "explanation": "Each tribe fills its own quota from its own pool."},
    ]),
    "rhetoric": ("rhetoric", "Rhetoric", "How arguments persuade", [
        {"type": "stasis_classify", "prompt": "Which question does this case turn on?", "case": "Did the defendant take the money?",
         "correct_stasis": "conjecture", "explanation": "A dispute over whether the act happened."},
        {"type": "trope_hunter", "prompt": "Name the figure of speech.", "passage": "All the world's a stage, and all the men and women merely players.",
         "target_trope": "metaphor", "options": ["metaphor", "irony", "hyperbole", "synecdoche"], "explanation": "The world is called a stage."},
        {"type": "dispositio_sort", "prompt": "Put the parts of a classical oration in order.",
         "solution": ["exordium", "narratio", "partitio", "confirmatio", "refutatio", "peroratio"],
         "explanation": "The classical six-part arrangement."},
        {"type": "enthymeme_excavator", "prompt": "Which unstated premise completes the argument?",
         "stated_premise": "Socrates is a human.", "conclusion": "Socrates is mortal.",
         "options": ["All humans are mortal.", "All mortals are human.", "Some humans are wise."], "solution": 0,
         "explanation": "The missing bridge links humans to mortality."},
    ]),
    "polity": ("polity", "Political science", "Counting votes and vetoes", [
        {"type": "compute_dhondt", "prompt": "Allocate the seats with the D'Hondt method.",
         "votes": {"Party A": 100000, "Party B": 80000, "Party C": 30000, "Party D": 20000}, "seats": 8,
         "explanation": "Repeatedly give a seat to the highest quotient votes / (seats + 1)."},
        {"type": "compute_shapley_shubik_pivotal", "prompt": "Find each voter's Shapley-Shubik power index (a fraction of 1).",
         "quota": 51, "weights": {"A": 50, "B": 49, "C": 1}, "explanation": "Count how often each voter is the pivot over all orderings."},
        {"type": "veto_pipeline", "prompt": "A budget bill needs the President, the Senate and the House. The President opposes it; the Senate and House support it. Will it pass, and who blocks it?",
         "bill": "Budget act", "veto_players": ["President", "Senate", "House"], "will_pass": False, "blocking_actor": "President",
         "explanation": "Every veto player must agree."},
        {"type": "instant_runoff_tally", "prompt": "Run the instant-runoff count: who wins, and in what order are candidates eliminated?",
         "candidates": ["Ana", "Ben", "Cy"],
         "ballots": [["Ana", "Ben", "Cy"]] * 4 + [["Ben", "Cy", "Ana"]] * 3 + [["Cy", "Ben", "Ana"]] * 2,
         "explanation": "Eliminate the last-place candidate and transfer their ballots."},
    ]),
    "ee": ("lab", "Electrical engineering", "Circuits and signals", [
        {"type": "circuit_kcl_kvl", "prompt": "A 12 V source drives a 1 kOhm and a 2 kOhm resistor in series. What is the voltage across the 2 kOhm resistor?",
         "target_variable": "V2", "unit": "V", "tolerance": 0.02, "solution": 8, "explanation": "Voltage divider: 12 * 2 / 3."},
        {"type": "bode_plot_analyzer", "prompt": "Find the cutoff frequency of the first-order low-pass filter.",
         "transfer_function": "H(s) = 1 / (1 + s/1000)", "cutoff_rad_s": 1000, "tolerance": 0.05, "explanation": "The pole sits at 1000 rad/s."},
        {"type": "boolean_gate_minimization", "prompt": "Minimize the function that is 1 for the minterms listed.",
         "variables": ["A", "B"], "minterms": [1, 2], "solution": "A'B + AB'", "explanation": "That is exclusive OR."},
        {"type": "opamp_gain_calc", "prompt": "Find the output of this inverting amplifier.", "topology": "inverting",
         "R1": 1000, "Rf": 4700, "Vin": 1.0, "explanation": "Gain is -Rf/R1 = -4.7."},
    ]),
    "ai": ("code", "Machine learning", "Gradients and metrics", [
        {"type": "backprop_layer_step", "prompt": "Give grad_W and grad_b for a linear layer with input X and upstream gradient delta.",
         "X": [1.0, 2.0], "delta": [0.5, -1.0], "explanation": "grad_W is the outer product of delta and X; grad_b is delta."},
        {"type": "attention_score_matrix", "prompt": "Compute the attention weights softmax(QK^T / sqrt(d_k)) row by row.",
         "Q": [[1.0, 0.0], [0.0, 1.0]], "K": [[1.0, 0.0], [0.0, 1.0]], "explanation": "Scale the dot products, then softmax each row."},
        {"type": "confusion_matrix_metrics", "prompt": "Compute precision, recall, f1 and specificity.", "TP": 40, "FP": 10, "FN": 5, "TN": 45,
         "explanation": "Precision 0.8, recall 0.889, f1 0.842, specificity 0.818."},
        {"type": "loss_gradient_verify", "prompt": "Give the binary cross-entropy loss and its gradient for the prediction.",
         "loss_type": "cross_entropy", "y_true": 1, "y_pred": 0.8, "explanation": "Loss -ln 0.8; gradient y_pred - y_true."},
    ]),
    "systems": ("code", "Computer systems", "Memory, caches and scheduling", [
        {"type": "page_table_walk", "prompt": "Translate the virtual address. Virtual page 1 maps to frame 0x11.",
         "virtual_address": "0x1234", "page_size_bytes": 4096, "ppn": 17, "explanation": "Frame 0x11 with offset 0x234."},
        {"type": "cache_tag_index_offset", "prompt": "How many bits are the tag, index and offset?", "address_bits": 32,
         "cache_size_bytes": 32768, "block_size_bytes": 64, "associativity_ways": 4, "explanation": "Offset 6, sets 128 so index 7, tag 19."},
        {"type": "assembly_reg_trace", "prompt": "Give the final value of every register.",
         "instructions": ["addi x1, x0, 5", "addi x2, x0, 7", "add x3, x1, x2", "slli x4, x3, 2"], "initial_registers": {"x0": 0},
         "explanation": "x1=5, x2=7, x3=12, x4=48."},
        {"type": "deadlock_bankers", "prompt": "Is this state safe? If so, give a safe sequence of process indices.",
         "allocation": [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
         "max_claim": [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]], "available": [3, 3, 2],
         "explanation": "Run any process whose need fits what is available, then release its resources."},
    ]),
    "stats": ("math", "Statistics", "Estimating and testing", [
        {"type": "hypothesis_test_two_sample", "prompt": "Test whether the two means differ (two-sided z test).",
         "mean1": 52, "std1": 8, "n1": 40, "mean2": 48, "std2": 9, "n2": 45, "alpha": 0.05,
         "explanation": "z = 4 / sqrt(64/40 + 81/45)."},
        {"type": "bayes_posterior_update", "prompt": "A condition has prior 1%. A test detects it 90% of the time and fires falsely 5% of the time. Find P(condition | positive).",
         "prior": 0.01, "sensitivity": 0.9, "false_positive_rate": 0.05, "explanation": "Bayes' rule: about 0.154."},
        {"type": "mle_parameter_derivation", "prompt": "Find the maximum-likelihood rate of the exponential sample.", "distribution": "exponential",
         "samples": [1.2, 0.8, 1.0, 1.4, 0.6], "explanation": "The MLE of the rate is 1 / mean."},
        {"type": "markov_steady_state", "prompt": "Find the stationary distribution of the two-state chain.", "alpha": 0.3, "beta": 0.6,
         "explanation": "pi = (beta, alpha) / (alpha + beta)."},
    ]),
    "bio": ("lab", "Bioinformatics", "Sequences and maps", [
        {"type": "smith_waterman_align", "prompt": "Give the best local alignment score (match +2, mismatch -1, gap -2).",
         "seq1": "ACACACTA", "seq2": "AGCACACA", "match_score": 2, "mismatch_penalty": 1, "gap_penalty": 2,
         "explanation": "The maximum cell of the dynamic-programming matrix."},
        {"type": "orf_finder_translate", "prompt": "Translate the open reading frame (ATG to stop) in one-letter codes.",
         "dna_sequence": "GGATGGCCAAATAGCC", "explanation": "ATG GCC AAA TAG gives M A K."},
        {"type": "restriction_digest_mapper", "prompt": "Give the fragment sizes (bp) after cutting this circular plasmid.",
         "total_length_bp": 5000, "circular": True, "cleavage_sites": [500, 2000, 3500], "explanation": "Three cuts make three fragments."},
        {"type": "phylogenetic_upgma_step", "prompt": "Which two taxa does UPGMA merge first?", "taxa": ["A", "B", "C", "D"],
         "distance_matrix": [[0, 5, 9, 9], [5, 0, 10, 10], [9, 10, 0, 8], [9, 10, 8, 0]], "explanation": "The smallest distance is A-B."},
    ]),
}

_FBD_SPEC = {
    "kind": "fbd", "title": "Box on a table", "description": "The weight is balanced by the normal force.",
    "view": {"xmin": -3, "xmax": 3, "ymin": -3, "ymax": 3, "grid": True, "axes": False},
    "bodies": [{"id": "box", "type": "box", "x": -0.6, "y": -0.4, "width": 1.2, "height": 0.8, "label": "m"}],
    "forces": [{"id": "fg", "body": "box", "origin": "center", "angle": 270, "magnitude": 1.6, "label": "m\\vec{g}"},
               {"id": "fn", "body": "box", "origin": "center", "angle": 90, "magnitude": 1.6, "label": "\\vec{F}_N"}],
}


def build_topics():
    """Every lesson as a topic dict: ids kit-<kit>-sample (11) and kit-fbd-sample."""
    topics = []
    for kit, (workspace, category, title, practice) in KITS.items():
        topics.append({
            "id": f"kit-{kit.replace('_', '-')}-sample", "title": f"{title} (sample)", "category": category,
            "difficulty": "Introductory", "summary": f"Four {kit.replace('_', ' ')} exercises checked by the server.",
            "markdownContent": f"# {title}\n\nSample exercises for the {kit.replace('_', ' ')} kit. Open the Practice tab.\n",
            "source": {"workspace": workspace}, "quiz": [], "practice": practice,
        })
    topics.append({
        "id": "kit-fbd-sample", "title": "Free-body diagram (sample)", "category": "Physics", "difficulty": "Introductory",
        "summary": "A box at rest: draw the forces.",
        "markdownContent": "# Free-body diagram\n\nA box rests on a table.\n\n```fbd\n" + json.dumps(_FBD_SPEC, indent=2) + "\n```\n",
        "source": {"workspace": "lab"}, "quiz": [],
        "practice": [{"type": "draw", "prompt": "Draw the free-body diagram of the box at rest on the table.",
                      "criteria": ["A downward arrow for the weight", "An upward arrow for the normal force", "The two arrows are equally long"],
                      "reference": "Weight down and normal force up, equal in length.", "background": "grid",
                      "fbd_spec": {"body_origin": [500.0, 300.0], "origin_tol_px": 40.0, "targets": [
                          {"name": "gravity", "aliases": ["mg", "w", "fg"], "angle_deg": 270.0, "angle_tol_deg": 5.0, "required": True},
                          {"name": "normal", "aliases": ["n", "fn"], "angle_deg": 90.0, "angle_tol_deg": 5.0, "required": True}]},
                      "explanation": "At rest the forces balance."}],
    })
    return topics


def _post(topic):
    req = urllib.request.Request(API + "/api/topics", method="POST", data=json.dumps(topic).encode(),
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{topic['id']}: HTTP {e.code} {e.read().decode()[:300]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"The &.edu backend is not reachable at {API} ({e.reason}). Start it, or use --dry-run.")


def main():
    parser = argparse.ArgumentParser(description="Post one example lesson per kit (and an FBD lesson) to the backend")
    parser.add_argument("--dry-run", action="store_true", help="normalize offline against a throwaway data folder and write nothing")
    args = parser.parse_args()
    topics = build_topics()
    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="andedu-seed-") as scratch:
            os.environ["SCIEDU_CONTENT_DIR"] = scratch  # the server opens its data here, never the live database
            import server  # noqa: E402
            bad = 0
            for t in topics:
                clean, warnings = server.normalize_topic(t)
                kept, sent = len(clean["practice"]), len(t["practice"])
                print(f"{t['id']}: {kept}/{sent} items{'  WARNINGS: ' + '; '.join(warnings) if warnings else ''}")
                bad += bool(warnings) or kept != sent
            sys.exit(1 if bad else 0)
    for t in topics:
        res = _post(t)
        print(f"{t['id']}: saved" + (f" with warnings {res['warnings']}" if res.get("warnings") else ""))
        if res.get("warnings"):
            sys.exit(1)


if __name__ == "__main__":
    main()
