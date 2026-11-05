"""
William & Mary Academic Advising Knowledge Base & Guidelines.

Contains official undergraduate academic advising recommendations, degree progression rules,
COLL curriculum sequencing, proficiency timelines, and major gateway pathways for W&M students.
"""
import re
from typing import Any, Dict, List, Optional, Set

# --- Core Academic Regulations & Policies ---
WM_CORE_POLICIES = """WILLIAM & MARY ACADEMIC REGULATIONS & ADVISING POLICIES:
- Course Load: Standard full-time semester load is 14–16 credits (typically 4 academic courses plus a 1-credit lab or activity).
  - Minimum full-time load: 12 credit hours. Dropping below 12 is an underload and requires approval from the Dean of Students.
  - Maximum standard load: 18 credit hours. Students with GPA < 3.00 and first-semester freshmen cannot overload.
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
- Key Deadlines: Add/Drop period ends at the end of the 10th class day. Course withdrawal ('W' on transcript) ends at the
  end of the 9th week of the semester. Pass/fail is for juniors and seniors only (max 4 courses, 1 per term, electives only).
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
  - Year 1: Start with CSCI 141 (Computational Problem Solving) or CSCI 140. (Students with AP CS A score of 4 or 5 start directly in CSCI 241). Take MATH 111 (Calculus I) and MATH 112 (Calculus II).
  - Year 2: Take CSCI 241 (Data Structures, prereq CSCI 141), then CSCI 243 (Discrete Structures) or MATH 214 (Foundations of Math), and CSCI 301 (Software Development).
  - Math Requirement: MATH 111, 112, 211 (Linear Algebra) are required for the B.S. in Computer Science.
  - Core Upper-level: CSCI 303 (Algorithms, prereqs CSCI 241 and CSCI 243/MATH 214), CSCI 304 (Computer Organization), CSCI 312 (Principles of Programming Languages).
  - Capstone: CSCI 400, CSCI 495-496 (Honors), or an approved senior software capstone satisfies COLL 400."""
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
        "name": "Data Science (B.S. / B.A.)",
        "keywords": ["data", "analytics", "machine learning", "statistics", "data science"],
        "guidelines": """Data Science Pathway:
  - Year 1: DATA 141 (Programming for Data Science) or CSCI 141, along with MATH 111 (Calculus I).
  - Year 2: DATA 201 (Introduction to Data Science), DATA 202 (Programming for Data Science), MATH 211 (Linear Algebra), and MATH 112 (Calculus II).
  - Year 3: DATA 301 (Applied Machine Learning), MATH/APSC applied statistics, and area of application electives."""
    },
    "mathematics": {
        "name": "Mathematics (B.S. / B.A.)",
        "keywords": ["math", "mathematics", "calculus", "algebra", "analysis", "topology", "statistics", "actuarial"],
        "guidelines": """Mathematics Pathway:
  - Year 1: MATH 111 (Calculus I) and MATH 112 (Calculus II). Students with AP Calc BC score of 4 or 5 start at MATH 211.
  - Year 2: MATH 211 (Linear Algebra), MATH 214 (Foundations of Mathematics — the proof-writing gateway course).
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
  - B.S. requires PHYS 107 + 108, MATH 211, CHEM 495-496 (research). B.A. is more flexible.
  - Capstone: CHEM 495-496 (Honors Research) or CHEM 400 (Senior Seminar) satisfies COLL 400."""
    },
    "physics": {
        "name": "Physics (B.S. / B.A.)",
        "keywords": ["physics", "phys", "mechanics", "quantum", "electromagnetism", "thermodynamics", "astrophysics"],
        "guidelines": """Physics Pathway:
  - Year 1: PHYS 101 (General Physics I, calculus-based) or PHYS 107 + 107L. MATH 111 and MATH 112 concurrently.
  - Year 2: PHYS 201 (General Physics II), PHYS 251 (Modern Physics, prereq PHYS 101/107). MATH 211 (Linear Algebra) and MATH 212 (Multivariable Calculus).
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
