"""
William & Mary Academic Advising Knowledge Base & Guidelines.

Contains official undergraduate academic advising recommendations, degree progression rules,
COLL curriculum sequencing, proficiency timelines, and major gateway pathways for W&M students.
"""
import re
from datetime import date
from typing import Any, Dict, List, Optional, Set

# --- Core Academic Regulations & Policies ---
WM_CORE_POLICIES = """WILLIAM & MARY ACADEMIC REGULATIONS & ADVISING POLICIES:
- Course Load: Standard full-time semester load is 14–16 credits (typically 4 academic courses plus a 1-credit lab or activity).
  - Minimum full-time load: 12 credit hours. Dropping below 12 is an underload and requires approval from the Dean of Students.
  - Registration caps (registrar, per add/drop period): carts and the first add/drop period allow up to 16 credits
    (the senior class may go to 18 in first/second add/drop); every undergraduate may go up to 18 credits in the
    final add/drop period. More than 18 is an overload. Students with GPA < 3.00 and first-semester freshmen cannot overload.
    Exact dates for the next term are in TERM CONTEXT.
  - Degree Requirement: 120 academic credits minimum with at least 2.00 cumulative GPA (and 2.00 in major) to graduate.
- COLL 100 & COLL 150 Rule: Students MUST complete COLL 100 in one semester and COLL 150 in the other during Year 1.
  Students should NEVER take both COLL 100 and COLL 150 in the same semester. A grade of C- or higher is required in both.
- COLL 200 Domain Requirement: 12 credits total (3 courses, at least 9 credits taken at W&M). Must span all three domains:
  ALV (Arts, Letters, Values), CSI (Cultures, Societies, Individuals), and NQR (Natural World & Quantitative Reasoning).
  Each course is anchored in one domain and reaches into another.
- COLL 300 (In the World / Global): 3 credits, typically taken in Year 3 (junior year). Completed through study abroad,
  the W&M Washington Center semester, or designated on-campus colloquia.
- COLL 400 (Capstone in Major): 3 credits, taken in Year 4 (senior year) within the student's declared major
  (undergraduate research, honors thesis 495-496, or major capstone seminar).
- Proficiencies:
  - Foreign Language: Competence through 202 level. Strongly recommended by the end of sophomore year.
  - Mathematics: Must be satisfied within the first 60 earned credit hours (e.g. MATH 104, 106, 111, 131, CSCI 141).
  - Creative & Performing Arts (ARTS): 2 credits in the same discipline (e.g. MUSC, THEA, DANC, ART).
- Major Declaration Milestone: Students are eligible to declare a major at 39 earned credits and MUST declare by 54 credits
  (end of sophomore year) to avoid a registration hold.
- Key Deadlines: The last day to add/drop, the course withdrawal window ('W' on transcript) and the pass/fail election
  window are set by the registrar's calendar for each term; use the exact dates in TERM CONTEXT. Pass/fail is for
  juniors and seniors only.
- Academic Continuance: Students must maintain minimum academic standards to remain in good standing.
  Freshmen with semester GPA < 1.5 are placed on academic warning; continued issues lead to academic suspension.
  Students suspended once may apply to return after one semester; twice = permanent dismissal.
- Two-Course Overlap Rule: Students may not simultaneously enroll in two courses that have more than a 50% content overlap
  (e.g. CSCI 141 and CSCI 140 cannot both be taken for credit; CHEM 103 and CHEM 105 overlap).
- 48-Credit Department Cap: Students may not count more than 48 credits from a single department toward the 120-credit degree total.
- 10-Semester Limit: Students are expected to complete the degree within 10 regular (fall/spring) semesters (5 years).
  Extensions require petition to the Dean's office.
- Course Repeat Policy: When a course is repeated, only the most recent grade counts in GPA; both attempts appear on the transcript.
  Federal aid requires SAP (Satisfactory Academic Progress): > 67% of attempted credits completed with cumulative 2.0 GPA.
- COLL 200 In-Residence Rule: At least 9 of the 12 COLL 200 credits must be completed at W&M (not transferred in).
  Transfer credits can count for at most ONE COLL 200 course."""

# --- Major Gateway Roadmaps & First/Second Year Pathways ---
MAJOR_ROADMAPS: Dict[str, Dict[str, Any]] = {
    "computer_science": {
        "name": "Computer Science (B.S.)",
        "keywords": ["cs", "csci", "computer", "coding", "software", "algorithm", "programming"],
        "guidelines": """Computer Science Pathway:
  - Year 1: Start with CSCI 141 (Modern Programming Fundamentals). Take MATH 111 (Calculus I) and MATH 112 (Calculus II).
  - Year 2: Take CSCI 241 (Data Structures, prereq CSCI 141), then CSCI 243 (Logic and Discrete Structures) or MATH 214 (Foundations of Math), and a required 300-level course such as CSCI 301 (Software Development).
  - Math Requirement (B.S.): proficiency in MATH 111 (or 131), MATH 112 (or 132) and MATH 109 Linear Algebra (formerly MATH 211), ideally by the end of sophomore year.
  - Core Upper-level: CSCI 303 (Algorithms), CSCI 304 (Computer Organization), CSCI 312 (Principles of Programming Languages); the B.S. also requires CSCI 423 (Finite Automata and Theory of Computation).
  - B.S. students choose a concentration (General, AI/ML, Cybersecurity); the B.A. replaces CSCI 423 and the concentration with 15 broader elective credits. Full lists are in the W&M PROGRAMS block."""
    },
    "pre_med": {
        "name": "Pre-Med / Pre-Health Track",
        "keywords": ["pre-med", "premed", "medicine", "doctor", "health", "mcat", "medical", "physician"],
        "guidelines": """Pre-Med / Pre-Health Pathway:
  - Year 1: CHEM 103 + 103L (General Chemistry I + Lab) in Fall; CHEM 208 + 254 (General Chemistry II) in Spring. BIOL 203 + 203L (Introduction to Biology). MATH 111 or 131 (Calculus) and MATH 106 or BIOL 327 (Statistics).
  - Year 2: CHEM 301 + 303 (Organic Chemistry I + Lab) in Fall; CHEM 302 + 309 (Organic Chemistry II) in Spring. BIOL 204 + 204L (Introduction to Biology).
  - Year 3: BIOL 314 or CHEM 314 (Biochemistry), PHYS 107 + 107L (or PHYS 101) in Fall, PHYS 108 + 108L (or PHYS 102) in Spring. Prepare for MCAT in Spring/Summer of junior year.
  - Recommendations: Register with the W&M Pre-Health Advising listserv and meet with a pre-health advisor early. Balance heavy science labs with manageable COLL courses."""
    },
    "business": {
        "name": "Business (Mason School B.B.A.)",
        "keywords": ["business", "buad", "finance", "accounting", "marketing", "consulting", "mason", "bba"],
        "guidelines": """Business (Mason School of Business B.B.A.) Pathway:
  - Admission: Competitive application during sophomore year (February for Fall entry, September for Spring entry).
  - Prerequisites (must complete prior to admission with competitive grades):
    1. BUAD 203 (Principles of Accounting, 3 cr)
    2. ECON 101 (Principles of Microeconomics, 3 cr)
    3. ECON 102 (Principles of Macroeconomics, 3 cr)
    4. BUAD 231 (Statistics) or approved equivalent (MATH 106, PSYC 301, ECON 308)
  - Requirements: At least 54 completed credit hours prior to entering the business school; minimum 2.50 GPA (competitive average is ~3.3+).
  - Strongly Recommended: Complete COLL 100, COLL 150, foreign language proficiency, and as much of COLL 200 as possible before starting the Foundation Semester (Block)."""
    },
    "biology": {
        "name": "Biology (B.S.)",
        "keywords": ["biology", "biol", "ecology", "genetics", "organism", "botany", "cell"],
        "guidelines": """Biology Pathway:
  - Year 1: BIOL 203 + 203L (Organismal Biology), CHEM 103 + 103L (General Chem I), CHEM 208 (General Chem II), MATH 111 or 131.
  - Year 2: BIOL 204 + 204L (Cell & Molecular Biology), CHEM 301 + 303 (Organic Chem I), and an introductory statistics course (MATH 106 or BIOL 327).
  - Year 3 & 4: Upper-level biology electives across the organismal, molecular, and ecological breadths. Complete COLL 400 via BIOL 400 or BIOL 495-496 (Honors)."""
    },
    "economics": {
        "name": "Economics (B.A.)",
        "keywords": ["economics", "econ", "micro", "macro", "econometrics", "market", "policy"],
        "guidelines": """Economics Pathway:
  - Year 1: ECON 101 (Microeconomics) and ECON 102 (Macroeconomics). Math foundation: MATH 111 or 131 (Calculus I).
  - Year 2: ECON 303 (Intermediate Microeconomics, prereqs ECON 101 and MATH 111) and ECON 304 (Intermediate Macroeconomics, prereqs ECON 102 and MATH 111).
  - Year 3: ECON 308 (Econometrics, prereqs ECON 101, 102, MATH 111, and introductory statistics).
  - Major requirements: Minimum 30 credits in economics including ECON 101, 102, 303, 304, 308 and at least 9 credits at the 400-level."""
    },
    "psychology": {
        "name": "Psychological Sciences (B.A. / B.S.)",
        "keywords": ["psychology", "psyc", "psych", "cognitive", "clinical", "mental", "behavior"],
        "guidelines": """Psychological Sciences Pathway:
  - Year 1: PSYC 201 (Intro to Psychology as a Natural Science) or PSYC 202 (Intro to Psychology as a Social Science).
  - Year 2: PSYC 301 (Elementary Statistics, prereq MATH 104/106/111) in Fall, followed by PSYC 302 (Experimental Methods, prereq PSYC 301) in Spring.
  - Year 3: PSYC 302 is the strict prerequisite for upper-level content labs (PSYC 410-422) and advanced research seminars.
  - B.S. vs B.A.: B.S. requires 3 additional science/math courses outside psychology (e.g. BIOL, CHEM, MATH, CSCI, PHYS)."""
    },
    "government": {
        "name": "Government / International Relations",
        "keywords": ["government", "govt", "politics", "international", "ir", "inrl", "law", "diplomacy"],
        "guidelines": """Government / International Relations Pathway:
  - Year 1: Introductory surveys: GOVT 201 (Introduction to American Politics), GOVT 203 (Introduction to Comparative Politics), or GOVT 204 (Introduction to International Politics).
  - Year 2: Deepen focus with political theory (GOVT 202) and intermediate 300-level courses. For International Relations majors: take ECON 101 and 102 early.
  - Foreign Language: International Relations requires language proficiency through the 202 level plus at least 3 credits of language literature/culture beyond 202."""
    },
    "data_science": {
        "name": "Data Science (B.S.)",
        "keywords": ["data", "analytics", "machine learning", "statistics", "data science"],
        "guidelines": """Data Science Pathway:
  - Year 1: DATA 101 (Reasoning with Generative AI) or CSCI 141, then DATA 201 (Data in the Age of AI); start DATA 209 (Applied Linear Algebra & Calculus) or MATH 109 + MATH 111.
  - Year 2: DATA 202 (AI & Data Ethics), DATA 210 (Research Design and Statistics) or MATH 352, and begin DATA 301 (Applied Machine Learning), DATA 302 (Databases), DATA 303 (Data Visualization).
  - Declare between 39 and 54 credits and pick a track (AI, Algorithms, Data Application, Spatial Data Analytics) at declaration; finish with one 400-level DATA capstone. Full lists are in the W&M PROGRAMS block."""
    },
    "mathematics": {
        "name": "Mathematics (B.S. / B.A.)",
        "keywords": ["math", "mathematics", "calculus", "algebra", "analysis", "topology", "statistics", "actuarial"],
        "guidelines": """Mathematics Pathway:
  - Year 1: MATH 111 (Calculus I) and MATH 112 (Calculus II). Students with AP Calc BC score of 4 or 5 may start at MATH 109 Linear Algebra (formerly MATH 211).
  - Year 2: MATH 109 (Linear Algebra, formerly MATH 211), MATH 214 (Foundations of Mathematics — the proof-writing gateway course).
  - Year 3: MATH 311 (Real Analysis I) and MATH 307 (Abstract Algebra I) are core requirements. Choose applied or pure track.
  - B.S. requires 36+ credits in math including analysis and algebra. B.A. requires 30 credits.
  - Capstone: MATH 495-496 (Honors Thesis) or MATH 400 (Senior Seminar) satisfies COLL 400."""
    },
    "chemistry": {
        "name": "Chemistry (B.S. / B.A.)",
        "keywords": ["chemistry", "chem", "organic", "biochemistry", "inorganic", "analytical", "spectroscopy"],
        "guidelines": """Chemistry Pathway:
  - Year 1: CHEM 103 + 103L (General Chemistry I) in Fall, CHEM 208 + 254 (General Chemistry II) in Spring. MATH 111.
  - Year 2: CHEM 301 + 303 (Organic Chemistry I + Lab) in Fall, CHEM 302 + 309 (Organic Chemistry II + Lab) in Spring. MATH 112.
  - Year 3: CHEM 311 (Analytical Chemistry), CHEM 351 (Physical Chemistry I, prereqs CHEM 208, MATH 112, PHYS 108), and CHEM 321 (Inorganic Chemistry).
  - B.S. requires PHYS 107 + 108, MATH 109 (Linear Algebra, formerly MATH 211), CHEM 495-496 (research). B.A. is more flexible.
  - Capstone: CHEM 495-496 (Honors Research) or CHEM 400 (Senior Seminar) satisfies COLL 400."""
    },
    "physics": {
        "name": "Physics (B.S. / B.A.)",
        "keywords": ["physics", "phys", "mechanics", "quantum", "electromagnetism", "thermodynamics", "astrophysics"],
        "guidelines": """Physics Pathway:
  - Year 1: PHYS 101 (General Physics I, calculus-based) or PHYS 107 + 107L. MATH 111 and MATH 112 concurrently.
  - Year 2: PHYS 201 (General Physics II), PHYS 251 (Modern Physics, prereq PHYS 101/107). MATH 109 (Linear Algebra, formerly MATH 211) and MATH 212 (Multivariable Calculus).
  - Year 3: PHYS 301 (Classical Mechanics), PHYS 321 (Electricity & Magnetism I), PHYS 311 (Mathematical Methods in Physics).
  - Year 4: PHYS 401 (Quantum Mechanics I), PHYS 421 (Thermodynamics & Statistical Mechanics), plus electives.
  - Capstone: PHYS 495-496 (Honors Research) or approved senior capstone satisfies COLL 400."""
    },
    "english": {
        "name": "English (B.A.)",
        "keywords": ["english", "engl", "literature", "writing", "poetry", "rhetoric", "creative writing", "shakespeare"],
        "guidelines": """English Pathway:
  - Year 1: ENGL 200 (Reading and Writing the Literary Essay) is the gateway course required of all majors.
  - Year 2: ENGL 300-level survey courses (American Literature, British Literature, World Literature) and one linguistics or creative writing course.
  - Distribution: Majors must complete courses in pre-1800 literature, post-1800 literature, and either world literature or non-English-language texts in translation.
  - Creative Writing Track: ENGL 201 (Intro to Creative Writing) → ENGL 301/302 (Intermediate Fiction/Poetry) → ENGL 401 (Advanced Workshop).
  - Capstone: ENGL 495-496 (Honors Thesis) or ENGL 400 (Senior Seminar) satisfies COLL 400."""
    },
    "history": {
        "name": "History (B.A.)",
        "keywords": ["history", "hist", "historical", "medieval", "modern", "colonial", "revolution", "war"],
        "guidelines": """History Pathway:
  - Year 1: HIST 101-199 (introductory surveys or themed 100-level history courses). No strict prerequisites.
  - Year 2: HIST 200 (Historical Methods — the gateway course for all majors; covers primary sources, historiography, and research writing).
  - Distribution: Majors must complete courses spanning at least THREE of the four geographic/thematic fields: US, European, Non-Western, and Comparative/Transnational.
  - Year 3+: Upper-level seminars (HIST 300-400). HIST 400 capstone seminar fulfills COLL 400.
  - At least 36 credits in history required; at least 18 must be at the 300+ level."""
    },
    "neuroscience": {
        "name": "Neuroscience (B.S.)",
        "keywords": ["neuroscience", "neuro", "brain", "neural", "cognitive", "neurobiology"],
        "guidelines": """Neuroscience Pathway (interdisciplinary B.S.):
  - Year 1: BIOL 203 + 203L (Organismal Biology), CHEM 103 + 103L (General Chem I), PSYC 201 or PSYC 202, MATH 111 or 131.
  - Year 2: BIOL 204 + 204L (Cell & Molecular Biology), CHEM 208 (General Chem II), PSYC 301 (Statistics), NEUR 201 (Intro to Neuroscience, if offered).
  - Year 3: NEUR 302/BIOL 302 (Neurobiology), PSYC/BIOL 310 (Behavioral Neuroscience), CHEM 301 (Organic Chem I recommended).
  - Interdisciplinary: Requires courses from Biology, Psychology, Chemistry and Physics. Plan carefully with both a Biology and Psychology advisor.
  - Capstone: NEUR 495-496 or interdisciplinary research project satisfies COLL 400."""
    },
    "environmental_science": {
        "name": "Environmental Science (B.S.)",
        "keywords": ["environmental", "environment", "ecology", "sustainability", "climate", "conservation", "earth science"],
        "guidelines": """Environmental Science Pathway:
  - Year 1: BIOL 203 + 203L, CHEM 103 + 103L, MATH 111 or 131, and GEOL 101 or ENSP 101 (Environmental Science I).
  - Year 2: BIOL 204 + 204L, CHEM 208, GEOL 201 (Earth Systems), ENSP 201 (Environmental Science II), and introductory statistics.
  - Year 3: ENSP 301 (Ecology), CHEM 311 (Analytical Chemistry), upper-level GEOL or BIOL electives, GIS (Geographic Information Systems).
  - Fieldwork: Many upper-level courses include mandatory field components. Plan for summer research opportunities.
  - Capstone: ENSP 495-496 (Honors Research) or ENSP 400 (Senior Seminar) satisfies COLL 400."""
    },
    "public_policy": {
        "name": "Public Policy (B.A.)",
        "keywords": ["public policy", "policy", "government policy", "urban planning", "social policy", "public affairs"],
        "guidelines": """Public Policy Pathway:
  - Year 1: GOVT 201 (American Politics) or ECON 101 (Microeconomics). No dedicated intro course — take broad social science foundations.
  - Year 2: PUBP 201 (Introduction to Public Policy, the gateway course), ECON 101 + 102 (Micro/Macroeconomics), and GOVT 201/202.
  - Year 3: PUBP 301 (Policy Analysis), PUBP 311 (Statistics for Public Policy), and elective concentrations in Health, Environmental, or Social Policy.
  - Internship: PUBP 391 (Policy Internship) is strongly recommended — DC semester, state legislature, or non-profit placements.
  - Capstone: PUBP 495-496 (Honors Thesis) or PUBP 400 (Policy Capstone) satisfies COLL 400."""
    },
}


def get_relevant_advising_context(
    user_id: str,
    audit: Dict[str, Any],
    message: str,
    completed_courses: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Selects and formats pertinent William & Mary academic advising rules and pathways
    tailored to the student's credit standing, degree gaps, and stated goals/questions.
    """
    lines = [WM_CORE_POLICIES]

    total_credits = float(audit.get("total_credits") or 0.0)
    completed_count = len(completed_courses or [])

    # Progression stage advice
    stage_notes = []
    if total_credits < 30:
        stage_notes.append(
            "- Year 1 Status (< 30 credits): Prioritize taking either COLL 100 or COLL 150 (not both this term), "
            "making progress on foreign language toward the 202 requirement, and taking exploratory courses toward prospective majors. "
            "Aim for 14–16 credits."
        )
    elif total_credits < 54:
        stage_notes.append(
            f"- Sophomore Status ({total_credits} credits earned): Major declaration is eligible at 39 credits and MANDATORY at 54 credits. "
            "Prioritize completing major gateway prerequisites (e.g. CSCI 241, BUAD 203, ECON 101/102, PSYC 301/302, CHEM 103/208) "
            "and satisfying the Mathematics proficiency (required before 60 credits). Balance remaining COLL 200 domains."
        )
    elif total_credits < 89:
        stage_notes.append(
            f"- Junior Status ({total_credits} credits earned): Major should now be declared. Plan for COLL 300 "
            "(study abroad, DC semester, or campus colloquium) and core upper-level major seminars. Ensure any remaining COLL 200s are scheduled."
        )
    else:
        stage_notes.append(
            f"- Senior Status ({total_credits} credits earned): Focus on completing the major capstone (COLL 400), "
            "final major electives, and verifying overall 120 credit count and 2.0 GPA graduation requirements."
        )

    # Gap-specific advising notes
    coll = audit.get("coll") or {}
    coll100 = coll.get("coll100") or {}
    coll150 = coll.get("coll150") or {}

    if not coll100.get("met") and not coll150.get("met"):
        stage_notes.append(
            "- COLL 100 & 150 Notice: Neither COLL 100 nor COLL 150 is completed. Recommend registering for ONE of them "
            "for the upcoming term, and taking the other in the subsequent term."
        )

    prof = audit.get("proficiencies") or {}
    math_prof = prof.get("math") or {}
    if not math_prof.get("met") and total_credits >= 30:
        stage_notes.append(
            "- Mathematics Proficiency Warning: Student has completed 30+ credits without fulfilling the Math proficiency. "
            "Must be completed before 60 credits! Recommend taking an approved math course this semester."
        )

    if stage_notes:
        lines.append("\nSTUDENT DEGREE PROGRESSION & TIMELINE GUIDELINES:\n" + "\n".join(stage_notes))

    # Relevant major pathways based on message and completed course codes
    msg_lower = (message or "").lower()
    codes = {str(c.get("code") or "").upper().split()[0] for c in (completed_courses or [])}

    matched_majors = []
    for key, major in MAJOR_ROADMAPS.items():
        # Match by keywords in message
        if any(re.search(rf"\b{re.escape(k)}\b", msg_lower) for k in major["keywords"]):
            matched_majors.append(major)
            continue
        # Match by department codes in completed courses if message is broad ("what should I take?")
        dept_map = {
            "computer_science": {"CSCI", "DATA"},
            "pre_med": {"CHEM", "BIOL", "KINE"},
            "business": {"BUAD", "FIN", "ACCT"},
            "biology": {"BIOL"},
            "economics": {"ECON"},
            "psychology": {"PSYC"},
            "government": {"GOVT", "INRL"},
            "data_science": {"DATA"},
            "mathematics": {"MATH", "APSC"},
            "chemistry": {"CHEM"},
            "physics": {"PHYS", "APSC"},
            "english": {"ENGL"},
            "history": {"HIST"},
            "neuroscience": {"NEUR", "BIOL", "PSYC"},
            "environmental_science": {"ENSP", "GEOL", "BIOL"},
            "public_policy": {"PUBP", "GOVT"},
        }
        if key in dept_map and codes & dept_map[key] and any(w in msg_lower for w in ["next", "plan", "major", "should", "schedule", "recommend"]):
            matched_majors.append(major)

    if matched_majors:
        lines.append("\nRECOMMENDED MAJOR ROADMAPS & GATEWAYS:")
        for m in matched_majors[:2]:  # at most 2 major roadmaps to conserve context budget
            lines.append(f"\n{m['name']}:\n{m['guidelines']}")

    return "\n\n".join(lines)


# --- W&M CS / Data Science programs and the registrar calendar --------------------------------------------
# Transcribed from the official 2026-2027 W&M Academic Catalog (catalog.wm.edu) and the registrar's 2026-27
# undergraduate calendar. Inline (not a data file) so it ships wherever wm_advising.py does. Refresh every catalog
# year: update catalog_year/as_of, each program, and add the new terms to WM_CALENDAR (see ARCHITECTURE.md).
CATALOG_YEAR = "2026-2027"
CATALOG_AS_OF = "2026-11-07"
_CAT = "https://catalog.wm.edu/programs/"

WM_PROGRAMS: List[Dict[str, Any]] = [
    {
        "id": "cs_bs", "dept": "CSCI", "name": "Computer Science major, B.S.",
        "source": _CAT + "computer-science-bs-computer-science/index.html",
        "credits": "36-37 major credits (48-51 with math proficiency and concentration counted)",
        "requirements": [
            "Core: CSCI 141 Modern Programming Fundamentals (4), CSCI 241 Data Structures, CSCI 243 Logic and Discrete Structures (or MATH 214 Foundations of Math), CSCI 301 Software Development, CSCI 303 Algorithms, CSCI 304 Computer Organization, CSCI 312 Principles of Programming Languages, CSCI 423 Finite Automata and Theory of Computation",
            "Math proficiency: MATH 111 (or 131) Calculus I, MATH 112 (or 132) Calculus II, MATH 109 Linear Algebra (formerly MATH 211)",
            "Concentration (12-15 cr), chosen at declaration: General, Artificial Intelligence/Machine Learning, or Cybersecurity",
            "Writing requirement: met by completing the core. At least half of the major's courses must be taken at W&M; at most two 300-400 level courses taken elsewhere count.",
            "Recommended by end of sophomore year: CSCI 141, 241, 243 (or MATH 214), one required 300-level CSCI course, and the math proficiency.",
        ],
        "tracks": [
            {"name": "General", "lines": [
                "12 credits from any 300-400 level CSCI courses (excluding CSCI 320 Directed Study, CSCI 430, CSCI 498 Internship); MATH 413 and MATH 414 Numerical Analysis also count."]},
            {"name": "Artificial Intelligence/Machine Learning (15 cr)", "lines": [
                "Proficiency: MATH 351 Probability and Statistics for Scientists or MATH 451 Probability",
                "12 credits from: CSCI 356 Large Language Models, CSCI 416 Fundamentals of AI/ML, CSCI 421 Database Systems, CSCI 436 Data Mining, CSCI 446 Neural Networks for Machine Learning, CSCI 455 Generative AI for Software Development, CSCI 466 Applied Topology Data Science, DATA 441 Advanced Applications of AI",
                "Select CSCI 420 Special Topics may count if the CS Undergraduate Director approves."]},
            {"name": "Cybersecurity (12 cr)", "lines": [
                "Required: CSCI 444 Principles of Operating Systems, CSCI 454 Computer and Network Security, CSCI 464 Penetration Testing",
                "One of: CSCI 324 Cybersecurity Fundamentals, CSCI 415 Systems Programming, CSCI 434 Network Systems and Design, CSCI 445 Mobile Application Security",
                "Select CSCI 420 Special Topics may count if the CS Undergraduate Director approves."]},
        ],
        "differences": "General = any four upper-level CSCI courses (most flexible). AI/ML = adds a probability/statistics proficiency (MATH 351 or 451) and four courses from an AI/ML/data list, so it is the only 15-credit concentration. Cybersecurity = three fixed courses (CSCI 444, 454, 464) plus one systems/security choice.",
    },
    {
        "id": "cs_ba", "dept": "CSCI", "name": "Computer Science major, B.A.",
        "source": _CAT + "computer-science-ba-computer-science/index.html",
        "credits": "36-37 credits",
        "requirements": [
            "Core: CSCI 141 (4), CSCI 241, CSCI 243 (or MATH 214), CSCI 301, CSCI 303, CSCI 304, CSCI 312",
            "Electives: 15 credits, at least two of them CSCI courses, from any CSCI 300-400 course (excluding CSCI 320, 430, 498) or: BUAD 460, CONS 301, DATA 301, DATA 302, DATA 303, DATA 442, DATA 446, DATA 448, ENGL 465 (Game Studies), GIS 405, GIS 410, GIS 420, LING 380, MATH 323, MATH 351, MATH 413, MATH 414, MATH 424, PHIL 330. Other computing-heavy courses need CS undergraduate director approval.",
            "Writing requirement: met by completing the core.",
        ],
        "tracks": [],
        "differences": "B.A. vs B.S.: the B.A. drops CSCI 423, has no calculus/linear-algebra proficiency and no concentration; instead 15 elective credits that may come from other departments (DATA, GIS, MATH, LING, BUAD, PHIL...). The B.S. goes deeper in core CS.",
    },
    {
        "id": "cs_minor", "dept": "CSCI", "name": "Computer Science minor",
        "source": _CAT + "computer-science-minor/index.html",
        "credits": "18-19 credits",
        "requirements": [
            "Core: CSCI 141, CSCI 241, CSCI 243 (or MATH 214)",
            "9 elective credits from 300-400 level CSCI (excluding CSCI 320, 430, 498); MATH 413 and MATH 414 may count toward part of the 9.",
        ],
        "tracks": [],
        "differences": "Minor = the three gateway courses plus three upper-level CSCI electives; no 300-level core is required.",
    },
    {
        "id": "data_bs", "dept": "DATA", "name": "Data Science major, B.S.",
        "source": _CAT + "data-science-bs-data-science/index.html",
        "credits": "36 credits",
        "requirements": [
            "Core: DATA 101 Reasoning with Generative AI (or CSCI 141), DATA 201 Data in the Age of AI, DATA 202 AI & Data Ethics, DATA 301 Applied Machine Learning, DATA 302 Databases, DATA 303 Data Visualization",
            "Math: DATA 209 Applied Linear Algebra & Calculus (or MATH 109 and MATH 111); DATA 210 Research Design and Statistics (or MATH 352 Statistical Data Analysis)",
            "Capstone: one 400-level DATA course (not DATA 491 or DATA 495; DATA 496 counts for students completing honors). A capstone course cannot also count toward the track.",
            "Track (9 cr): three methods courses, chosen at major declaration (declare between 39 and 54 credits).",
            "Computing proficiency is usually met by DATA 201; writing requirement usually by DATA 202 (petitions go to the Data Science Undergraduate Committee).",
        ],
        "tracks": [
            {"name": "Artificial Intelligence", "lines": [
                "Three of: AAI 301 Designing AI Agents, AAI 302 Agentic Coordination, DATA 405 Trustworthy AI, DATA 440 Special Topics, DATA 441 Advanced Applications of AI, DATA 442 Neural Networks & Deep Learning, DATA 446 Generative AI, DATA 447 Bayesian Reasoning in Data Science, DATA 448 Reinforcement Learning, DATA 451 Artificial Intelligence Systems"]},
            {"name": "Algorithms", "lines": [
                "All of: CSCI 241 Data Structures, CSCI 243 Logic and Discrete Structures (or MATH 214), CSCI 303 Algorithms"]},
            {"name": "Data Application", "lines": [
                "Three DATA courses numbered 340 or higher with significant dataset analysis; DATA 340 and DATA 440 special topics may repeat with different topics; not DATA 491; DATA 495 may count for honors students."]},
            {"name": "Spatial Data Analytics", "lines": [
                "Three of: DATA 431 Spatial Data Discovery, GIS 201 Intro to GIS and Spatial Analysis, GIS 405 Geovisualization & Cartographic Design, GIS 410 Remotely Sensed Imagery and Analysis, GIS 420 Advanced GIS Analysis & Programming"]},
        ],
        "differences": "AI = choose 3 from a list of AI/agent courses (AAI and 400-level DATA). Algorithms = 3 fixed CS courses (CSCI 241, 243/MATH 214, 303), so it needs CSCI 141 first and overlaps with a CS minor. Data Application = any 3 DATA courses 340+ (most flexible). Spatial = 3 from DATA 431 and the GIS sequence.",
    },
    {
        "id": "data_minor", "dept": "DATA", "name": "Data Science minor",
        "source": _CAT + "data-science-minor/index.html",
        "credits": "18 credits",
        "requirements": [
            "Required: DATA 101 (or CSCI 141), DATA 201, DATA 202, and DATA 305 Designing AI Agents (or DATA 301 Applied Machine Learning)",
            "At least two additional approved courses (6 cr) focused on analysis of temporal, spatial or numerical data: DATA 300/400-level (not DATA 480, 481, 491), or approved courses in BIOL (325, 327, 445), BUAD (350-352, 460, 463, 466-469), ECON (308, 331, 407, 408, 412-414), GIS (201, 405, 410, 420), GOVT (301, 302, 307), MATH (309, 323, 332, 351-353, 408, 417, 424, 451, 452, 455, 465), PSYC 302. Others need Data Science curriculum committee approval.",
        ],
        "tracks": [],
        "differences": "Minor = four required DATA courses plus two approved quantitative electives from many departments; no track, no capstone.",
    },
    {
        "id": "columbia_3_2", "dept": "ENGR", "name": "Columbia University 3+2 Combined Plan Pre-Engineering Track",
        "source": "https://www.wm.edu/as/appliedscience/undergraduate/combined-plan/index.php",
        "credits": "Foundational STEM core (MATH, PHYS, CHEM, CSCI, ECON, Writing) + major requirements before transfer (GPA >= 3.30, B or better in math/science)",
        "requirements": [
            "MATH 111, MATH 112 (Calculus I & II), MATH 212 or 213 (Multivariable Calculus)",
            "MATH 211 (Linear Algebra), MATH 302 (Differential Equations)",
            "PHYS 101/101L, PHYS 102/102L (General Physics I & II with Labs)",
            "CHEM 103/103L (General Chemistry I with Lab)",
            "CSCI 141 (Computational Problem Solving / Intro to Python)",
            "ECON 101 or ECON 102 (Microeconomics or Macroeconomics)",
            "COLL 150 or WRIT 101 (College Writing / First-Year Seminar)",
            "Overall cumulative GPA >= 3.30 and Pre-Engineering Math/Science GPA >= 3.30 with B (3.0) or higher on first attempt in all foundational courses",
        ],
        "tracks": [
            {
                "name": "Computer Engineering",
                "lines": [
                    "Requires CSCI 241 (Data Structures) and CSCI 243 (Discrete Structures in CS)",
                    "Recommended: PHYS 251 (Electronics / Experimental Atomic Physics)",
                ],
            },
            {
                "name": "Electrical Engineering",
                "lines": [
                    "Requires PHYS 251 (Electronics) or approved circuits coursework",
                    "Recommended: CSCI 241 (Data Structures)",
                ],
            },
            {
                "name": "Mechanical / Civil Engineering",
                "lines": [
                    "Requires CHEM 103/103L and PHYS 101/102",
                    "Recommended: Multivariable Calculus (MATH 212) and Differential Equations (MATH 302)",
                ],
            },
        ],
        "differences": "Dual-degree articulation: 3 years at William & Mary completing COLL curriculum and foundational STEM courses, followed by 2 years at Columbia University Fu Foundation School of Engineering and Applied Science (SEAS), earning a B.A./B.S. from W&M and a B.S. from Columbia.",
    },
]

# Registrar's undergraduate calendar (dates "subject to change"); one entry per term code.
WM_CALENDAR: Dict[str, Dict[str, Any]] = {
    "202720": {
        "name": "Spring 2027",
        "last_add_drop": "2027-02-05",
        "source": "https://www.wm.edu/offices/registrar/catalogs-calendars-exams/ugcalendar/26-27/",
        "dates": [
            "Advising period (Fall 2026): Oct 19-30, 2026; declare a major/minor by Oct 23 for guaranteed processing before registration",
            "Carts (continuing students): Oct 30 noon - Nov 4 noon, 2026, up to 16 credits; schedules viewable Nov 8",
            "First add/drop: Nov 10, 2026 - Jan 13, 2027 noon; class of 2027 up to 18 credits, others up to 16; opens 7:00am class of 2027, 8:00am 2028, 3:00pm 2029, 4:00pm 2030",
            "Second add/drop: Jan 19 10am - Jan 22 4pm, 2027 (same credit limits)",
            "Final add/drop (all undergraduates, up to 18 credits): Jan 26 3pm - Feb 5 11:59pm, 2027",
            "Classes begin Wed Jan 27, 2027; last day to add/drop Feb 5 (also the deadline for May 2027 graduates to declare a minor or change/add a major)",
            "Withdrawal ('W'): Feb 6 - Mar 29, 2027; pass/fail election (juniors and seniors): Feb 8 - Mar 29",
            "Spring break Mar 13-21; last day of classes Fri May 7; exams May 10-14 and May 17-18; commencement May 20-22, 2027",
            "Looking ahead: Fall 2027 advising Mar 22 - Apr 2; declare for Fall by Mar 26; Fall carts Apr 2-7, 2027",
        ],
    },
}


def term_name(code: str) -> str:
    """W&M term codes are academic-year based: YYYY10 = Fall YYYY-1, YYYY20 = Spring YYYY, YYYY30 = Summer YYYY."""
    code = str(code)
    if code in WM_CALENDAR:
        return WM_CALENDAR[code]["name"]
    year, part = int(code[:4]), code[4:]
    return {"10": f"Fall {year - 1}", "20": f"Spring {year}", "30": f"Summer {year}"}.get(part, code)


def next_term(today: Optional[date] = None) -> str:
    """The fall/spring term a student plans for "next semester".

    The earliest calendar term whose add/drop is still open (so Spring stays current through its add/drop period);
    otherwise Aug-Dec -> Spring of next year, Jan-Jul -> Fall. Summer terms are never "next semester".
    """
    today = today or date.today()
    for code in sorted(WM_CALENDAR):
        if date.fromisoformat(WM_CALENDAR[code]["last_add_drop"]) >= today:
            return code
    # No calendar entry: approximate W&M's add/drop cut-offs (spring ~Feb 10, fall ~Sep 10).
    if today < date(today.year, 2, 11):
        code = f"{today.year}20"      # Spring of this year is still open
    elif today < date(today.year, 9, 11):
        code = f"{today.year + 1}10"  # Fall of this year
    else:
        code = f"{today.year + 1}20"  # Spring of next year
    while code in WM_CALENDAR:  # a calendar term whose add/drop already closed: take the one after it
        code = f"{int(code[:4]) + 1}10" if code.endswith("20") else f"{code[:4]}20"
    return code


def term_context(today: Optional[date] = None, code: str = "") -> str:
    today = today or date.today()
    code = code or next_term(today)
    lines = [f"TERM CONTEXT: today is {today.isoformat()}. The next term (what \"next semester\" means) is "
             f"{term_name(code)} (term code {code})."]
    cal = WM_CALENDAR.get(code)
    if cal:
        lines.append(f"Key dates for {cal['name']} (W&M registrar calendar, subject to change):")
        lines += [f"- {d}" for d in cal["dates"]]
    else:
        lines.append(f"Registration dates for {term_name(code)} are not loaded: do not state specific dates; "
                     "point the student to the registrar's calendar.")
    return "\n".join(lines)


PROGRAM_TRIGGERS = re.compile(
    r"\b(cs|csci|computer|computing|programming|data|tracks?|concentrations?|"
    r"cyber\w*|ai|ml|machine learning|algorithms?|spatial|gis|engineer\w*|columbia|3\+2|combined plan)\b", re.I)
PROGRAMS_MAX = 12000


def programs_context(message: str, completed: Optional[List[Dict[str, Any]]] = None, force: bool = False) -> str:
    """Every CS and Data Science program with its tracks and how they differ, when the question or the student's
    record is about them. Courses the student completed are marked [done]."""
    done = {" ".join(str(c.get("code") or "").upper().split()) for c in (completed or [])}
    if not (force or PROGRAM_TRIGGERS.search(message or "") or {d.split(" ")[0] for d in done} & {"CSCI", "DATA"}):
        return ""

    def mark(text: str) -> str:
        return re.sub(r"\b([A-Z]{3,4} \d{3}[A-Z]?)\b", lambda m: m.group(1) + (" [done]" if m.group(1) in done else ""), text)

    out = [f"W&M PROGRAMS: Computer Science and Data Science ({CATALOG_YEAR} catalog, transcribed {CATALOG_AS_OF}; "
           "cite the catalog year, and tell the student to confirm with their advisor and the degree audit):"]
    for p in WM_PROGRAMS:
        block = [f"\n{p['name']} ({p['credits']}) - {p['source']}"]
        block += [f"- {mark(r)}" for r in p["requirements"]]
        for t in p["tracks"]:
            block.append(f"  Track/concentration: {t['name']}")
            block += [f"    - {mark(x)}" for x in t["lines"]]
        block.append(f"  How the options differ: {p['differences']}")
        text = "\n".join(block)
        if len("\n".join(out)) + 1 + len(text) > PROGRAMS_MAX - 100:  # 100 leaves room for the "omitted" note
            out.append(f"\n[{p['name']} and later programs omitted for length]")
            break
        out.append(text)
    return "\n".join(out)


# --- Schedule Conflict Detector ---
DAY_MAP = {
    "0": "M", "1": "T", "2": "W", "3": "R", "4": "F", "5": "S", "6": "U",
    "M": "M", "T": "T", "W": "W", "R": "R", "F": "F", "S": "S", "U": "U"
}


def _parse_time_minutes(t_val: Any, default_pm: bool = False) -> Optional[int]:
    if t_val is None:
        return None
    s = str(t_val).strip().lower()
    if not s:
        return None
    is_pm = "p" in s or default_pm
    is_am = "a" in s and not is_pm
    try:
        colon_m = re.search(r"(\d{1,2})\s*:\s*(\d{2})", s)
        if colon_m:
            h, m = int(colon_m.group(1)), int(colon_m.group(2))
        else:
            digits_m = re.search(r"\b(\d{1,4})\b", s)
            if not digits_m:
                return None
            digits = digits_m.group(1)
            if len(digits) >= 3:
                h, m = int(digits[:-2]), int(digits[-2:])
            else:
                h, m = int(digits), 0
        if is_pm and h < 12:
            h += 12
        elif is_am and h == 12:
            h = 0
        elif not is_am and not is_pm and h < 8:
            h += 12
        return h * 60 + m
    except Exception:
        return None


def _format_minutes(mins: int) -> str:
    h = mins // 60
    m = mins % 60
    ampm = "am" if h < 12 else "pm"
    display_h = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
    return f"{display_h}:{m:02d}{ampm}"


def extract_meeting_slots(course: Dict[str, Any]) -> List[Dict[str, Any]]:
    slots = []
    raw_mt = course.get("meeting_times")
    if isinstance(raw_mt, str):
        try:
            import json
            raw_mt = json.loads(raw_mt)
        except Exception:
            raw_mt = []
    if isinstance(raw_mt, list) and raw_mt:
        for item in raw_mt:
            if isinstance(item, dict):
                day = DAY_MAP.get(str(item.get("meet_day", "")).upper())
                st = _parse_time_minutes(item.get("start_time"))
                et = _parse_time_minutes(item.get("end_time"))
                if day and st is not None and et is not None and st < et:
                    slots.append({"day": day, "start": st, "end": et})
    if not slots and course.get("meets"):
        meets = str(course.get("meets", "")).strip()
        m = re.match(r"^([MTWRFSU]+)\s+(.+?)\s*[-–]\s*(.+)$", meets, re.I)
        if m:
            days_str, start_str, end_str = m.group(1).upper(), m.group(2).strip(), m.group(3).strip()
            is_end_pm = "p" in end_str.lower()
            et = _parse_time_minutes(end_str)
            st = _parse_time_minutes(start_str, default_pm=is_end_pm and not ("a" in start_str.lower()))
            if st is not None and et is not None:
                if st >= et and is_end_pm and st >= 12 * 60:
                    st -= 12 * 60
                for d_char in days_str:
                    if d_char in DAY_MAP:
                        slots.append({"day": d_char, "start": st, "end": et})
    return slots


def check_schedule_conflicts(courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compares section days and meeting times for pairwise overlaps."""
    conflicts = []
    seen_pairs = set()
    course_slots = [(c, extract_meeting_slots(c)) for c in (courses or [])]
    for i in range(len(course_slots)):
        c_a, slots_a = course_slots[i]
        code_a = c_a.get("code") or f"Course-{i+1}"
        for j in range(i + 1, len(course_slots)):
            c_b, slots_b = course_slots[j]
            code_b = c_b.get("code") or f"Course-{j+1}"
            pair_key = tuple(sorted([code_a, code_b]))
            for s_a in slots_a:
                for s_b in slots_b:
                    if s_a["day"] == s_b["day"]:
                        overlap_start = max(s_a["start"], s_b["start"])
                        overlap_end = min(s_a["end"], s_b["end"])
                        if overlap_start < overlap_end:
                            conflict_key = (pair_key, s_a["day"])
                            if conflict_key not in seen_pairs:
                                seen_pairs.add(conflict_key)
                                time_desc = f"{_format_minutes(s_a['start'])} - {_format_minutes(s_a['end'])}"
                                conflicts.append({
                                    "conflict": True,
                                    "course_a": code_a,
                                    "course_b": code_b,
                                    "day": s_a["day"],
                                    "time": time_desc,
                                    "description": f"{code_a} and {code_b} overlap on {s_a['day']} ({_format_minutes(overlap_start)} - {_format_minutes(overlap_end)})"
                                })
    return conflicts

