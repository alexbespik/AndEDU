import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { 
  Terminal, Send, Play, CheckCircle2, AlertTriangle, RefreshCw, 
  Loader2, Sparkles, Upload, BookOpen, Code2, Plus, ArrowDown, 
  ArrowRight, ArrowLeft, Check, Award, Lightbulb, Clock, X, FileText,
  Flame, Save, RotateCcw, Puzzle, Cpu, Zap, CheckCheck, Folder, 
  FolderOpen, ChevronRight, ChevronDown, Split, Copy, ExternalLink, 
  Settings, HelpCircle, Bug, Search, FileCode, CheckSquare, MessageSquare,
  Trash2, FileCheck, Layers, Hash, Calculator, Binary, Compass, Box,
  GraduationCap, HelpCircle as QuestionIcon,
  Volume2, VolumeX, Pause, Square, Mic
} from 'lucide-react';

const STORAGE_KEY = 'andedu_studio_v5';

// ---------------------------------------------------------------------------
// MONOKAI BLACK & FOREST ACCENT PALETTE (Deep Obsidian & Lush Pine)
// ---------------------------------------------------------------------------
const theme = {
  bgApp: '#121212',        // Monokai Black canvas base
  bgPanel: '#1a1a1a',      // Monokai deep charcoal panel
  bgSidebar: '#161616',    // Sleek Monokai Black sidebar
  bgEditor: '#121212',     // Pure Monokai Black editor slate
  bgActivity: '#0d0d0d',   // Ultra-dark activity dock
  bgHeader: '#141414',     // Dark Monokai header
  bgCard: '#1e1e1e',       // Monokai Black card surface
  bgCardAlt: '#262626',    // Elevated card surface
  bgHighlight: '#2f2f2f',  // Active selection / line highlight
  bgInput: '#181818',      // Monokai dark input field
  border: '#282828',       // Subtle dark boundary
  borderActive: '#e5b85c', // Luminous Pine/Collegiate Gold
  borderContrast: '#383838', // Crisp Monokai divider
  borderLight: '#484848',   // Light border accent
  textMain: '#f8f8f2',     // Classic Monokai text white
  textDim: '#a8a8a2',      // Monokai dim text
  textMuted: '#7e8a82',    // Balanced sage muted text
  accent: '#23a55a',       // True Forest Green
  accentGreen: '#23a55a',  // Unmistakable deep Forest Green
  accentForestLight: '#2ecc71', // Bright spring pine highlight
  accentGold: '#e5b85c',   // Luminous Gold
  accentYellow: '#e5b85c', // Luminous Gold
  accentPink: '#f92672',   // Canonical Monokai pink/crimson
  accentBlue: '#66d9ef',   // Canonical Monokai cyan/blue
  accentOrange: '#fd971f', // Canonical Monokai orange
  accentPurple: '#ae81ff', // Canonical Monokai purple
  accentCyan: '#66d9ef',
  success: '#23a55a',
  error: '#f92672',
  warning: '#e5b85c',
  fontMono: '"JetBrains Mono", Menlo, Monaco, "Courier New", monospace'
};

// ---------------------------------------------------------------------------
// LINUX TUX PENGUIN SHADOW WATERMARK (Centered Linux Emblem)
// ---------------------------------------------------------------------------
const PenguinShadow = ({ size = 320, color = theme.accentGreen }) => {
  // Official Linux Tux Vector Silhouette Path
  const tuxPath = "M12.504 0c-.155 0-.315.008-.48.021-4.226.333-3.105 4.807-3.17 6.298-.076 1.092-.3 1.953-1.05 3.02-.885 1.051-2.127 2.75-2.716 4.521-.278.832-.41 1.684-.287 2.489a.424.424 0 00-.11.135c-.26.268-.45.6-.663.839-.199.199-.485.267-.797.4-.313.136-.658.269-.864.68-.09.189-.136.394-.132.602 0 .199.027.4.055.536.058.399.116.728.04.97-.249.68-.28 1.145-.106 1.484.174.334.535.47.94.601.81.2 1.91.135 2.774.6.926.466 1.866.67 2.616.47.526-.116.97-.464 1.208-.946.587-.003 1.23-.269 2.26-.334.699-.058 1.574.267 2.577.2.025.134.063.198.114.333l.003.003c.391.778 1.113 1.132 1.884 1.071.771-.06 1.592-.536 2.257-1.306.631-.765 1.683-1.084 2.378-1.503.348-.199.629-.469.649-.853.023-.4-.2-.811-.714-1.376v-.097l-.003-.003c-.17-.2-.25-.535-.338-.926-.085-.401-.182-.786-.492-1.046h-.003c-.059-.054-.123-.067-.188-.135a.357.357 0 00-.19-.064c.431-1.278.264-2.55-.173-3.694-.533-1.41-1.465-2.638-2.175-3.483-.796-1.005-1.576-1.957-1.56-3.368.026-2.152.236-6.133-3.544-6.139zm.529 3.405h.013c.213 0 .396.062.584.198.19.135.33.332.438.533.105.259.158.459.166.724 0-.02.006-.04.006-.06v.105a.086.086 0 01-.004-.021l-.004-.024a1.807 1.807 0 01-.15.706.953.953 0 01-.213.335.71.71 0 00-.088-.042c-.104-.045-.198-.064-.284-.133a1.312 1.312 0 00-.22-.066c.05-.06.146-.133.183-.198.053-.128.082-.264.088-.402v-.02a1.21 1.21 0 00-.061-.4c-.045-.134-.101-.2-.183-.333-.084-.066-.167-.132-.267-.132h-.016c-.093 0-.176.03-.262.132a.8.8 0 00-.205.334 1.18 1.18 0 00-.09.4v.019c.002.089.008.179.02.267-.193-.067-.438-.135-.607-.202a1.635 1.635 0 01-.018-.2v-.02a1.772 1.772 0 01.15-.768c.082-.22.232-.406.43-.533a.985.985 0 01.594-.2zm-2.962.059h.036c.142 0 .27.048.399.135.146.129.264.288.344.465.09.199.14.4.153.667v.004c.007.134.006.2-.002.266v.08c-.03.007-.056.018-.083.024-.152.055-.274.135-.393.2.012-.09.013-.18.003-.267v-.015c-.012-.133-.04-.2-.082-.333a.613.613 0 00-.166-.267.248.248 0 00-.183-.064h-.021c-.071.006-.13.04-.186.132a.552.552 0 00-.12.27.944.944 0 00-.023.33v.015c.012.135.037.2.08.334.046.134.098.2.166.268.01.009.02.018.034.024-.07.057-.117.07-.176.136a.304.304 0 01-.131.068 2.62 2.62 0 01-.275-.402 1.772 1.772 0 01-.155-.667 1.759 1.759 0 01.08-.668 1.43 1.43 0 01.283-.535c.128-.133.26-.2.418-.2zm1.37 1.706c.332 0 .733.065 1.216.399.293.2.523.269 1.052.468h.003c.255.136.405.266.478.399v-.131a.571.571 0 01.016.47c-.123.31-.516.643-1.063.842v.002c-.268.135-.501.333-.775.465-.276.135-.588.292-1.012.267a1.139 1.139 0 01-.448-.067 3.566 3.566 0 01-.322-.198c-.195-.135-.363-.332-.612-.465v-.005h-.005c-.4-.246-.616-.512-.686-.71-.07-.268-.005-.47.193-.6.224-.135.38-.271.483-.336.104-.074.143-.102.176-.131h.002v-.003c.169-.202.436-.47.839-.601.139-.036.294-.065.466-.065zm2.8 2.142c.358 1.417 1.196 3.475 1.735 4.473.286.534.855 1.659 1.102 3.024.156-.005.33.018.513.064.646-1.671-.546-3.467-1.089-3.966-.22-.2-.232-.335-.123-.335.59.534 1.365 1.572 1.646 2.757.13.535.16 1.104.021 1.67.067.028.135.06.205.067 1.032.534 1.413.938 1.23 1.537v-.043c-.06-.003-.12 0-.18 0h-.016c.151-.467-.182-.825-1.065-1.224-.915-.4-1.646-.336-1.77.465-.008.043-.013.066-.018.135-.068.023-.139.053-.209.064-.43.268-.662.669-.793 1.187-.13.533-.17 1.156-.205 1.869v.003c-.02.334-.17.838-.319 1.35-1.5 1.072-3.58 1.538-5.348.334a2.645 2.645 0 00-.402-.533 1.45 1.45 0 00-.275-.333c.182 0 .338-.03.465-.067a.615.615 0 00.314-.334c.108-.267 0-.697-.345-1.163-.345-.467-.931-.995-1.788-1.521-.63-.4-.986-.87-1.15-1.396-.165-.534-.143-1.085-.015-1.645.245-1.07.873-2.11 1.274-2.763.107-.065.037.135-.408.974-.396.751-1.14 2.497-.122 3.854a8.123 8.123 0 01.647-2.876c.564-1.278 1.743-3.504 1.836-5.268.048.036.217.135.289.202.218.133.38.333.59.465.21.201.477.335.876.335.039.003.075.006.11.006.412 0 .73-.134.997-.268.29-.134.52-.334.74-.4h.005c.467-.135.835-.402 1.044-.7zm2.185 8.958c.037.6.343 1.245.882 1.377.588.134 1.434-.333 1.791-.765l.211-.01c.315-.007.577.01.847.268l.003.003c.208.199.305.53.391.876.085.4.154.78.409 1.066.486.527.645.906.636 1.14l.003-.007v.018l-.003-.012c-.015.262-.185.396-.498.595-.63.401-1.746.712-2.457 1.57-.618.737-1.37 1.14-2.036 1.191-.664.053-1.237-.2-1.574-.898l-.005-.003c-.21-.4-.12-1.025.056-1.69.176-.668.428-1.344.463-1.897.037-.714.076-1.335.195-1.814.12-.465.308-.797.641-.984l.045-.022zm-10.814.049h.01c.053 0 .105.005.157.014.376.055.706.333 1.023.752l.91 1.664.003.003c.243.533.754 1.064 1.189 1.637.434.598.77 1.131.729 1.57v.006c-.057.744-.48 1.148-1.125 1.294-.645.135-1.52.002-2.395-.464-.968-.536-2.118-.469-2.857-.602-.369-.066-.61-.2-.723-.4-.11-.2-.113-.602.123-1.23v-.004l.002-.003c.117-.334.03-.752-.027-1.118-.055-.401-.083-.71.043-.94.16-.334.396-.4.69-.533.294-.135.64-.202.915-.47h.002v-.002c.256-.268.445-.601.668-.838.19-.201.38-.336.663-.336zm7.159-9.074c-.435.201-.945.535-1.488.535-.542 0-.97-.267-1.28-.466-.154-.134-.28-.268-.373-.335-.164-.134-.144-.333-.074-.333.109.016.129.134.199.2.096.066.215.2.36.333.292.2.68.467 1.167.467.485 0 1.053-.267 1.398-.466.195-.135.445-.334.648-.467.156-.136.149-.267.279-.267.128.016.034.134-.147.332a8.097 8.097 0 01-.69.468zm-1.082-1.583V5.64c-.006-.02.013-.042.029-.05.074-.043.18-.027.26.004.063 0 .16.067.15.135-.006.049-.085.066-.135.066-.055 0-.092-.043-.141-.068-.052-.018-.146-.008-.163-.065zm-.551 0c-.02.058-.113.049-.166.066-.047.025-.086.068-.14.068-.05 0-.13-.02-.136-.068-.01-.066.088-.133.15-.133.08-.031.184-.047.259-.005.019.009.036.03.03.05v.02h.003z";

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none', userSelect: 'none' }}>
      <svg 
        width={size} 
        height={size} 
        viewBox="0 0 24 24" 
        fill={color} 
        xmlns="http://www.w3.org/2000/svg"
        style={{
          filter: 'drop-shadow(0 20px 30px rgba(0, 0, 0, 0.7)) drop-shadow(0 0 35px rgba(35, 165, 90, 0.3))'
        }}
      >
        <path d={tuxPath} />
      </svg>
      <div style={{ 
        marginTop: '12px', 
        fontSize: '12px', 
        fontWeight: 800, 
        letterSpacing: '6px', 
        textTransform: 'uppercase', 
        color: color, 
        opacity: 0.75,
        fontFamily: theme.fontMono 
      }}>
        LINUX
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// DEFAULT CURRICULA: CODE MODE & MATH MODE
// ---------------------------------------------------------------------------
const DEFAULT_CODE_CURRICULUM = {
  course_title: "Control Flow & Algorithm Engineering",
  domain: "Programming & Algorithms",
  mode: "code",
  level_num: 1,
  level_title: "Level 1: Syntax Integrity & Invariant Patterns",
  overview: "Master programming fundamentals: syntax integrity, loop boundary invariants, indented block construction, and isolated execution.",
  chapters: [
    {
      id: 1,
      title: "Chapter 1: Syntax Essentials & Safe Loops",
      summary: "Master compound headers, colon syntax, and safe loop guards without memory crashes.",
      estimated_time_minutes: 20,
      content_markdown: `# Chapter 1: Syntax Essentials & Safe Loops

Welcome to **&edu Studio**. In this chapter, we master fundamental compound syntax and loop safety invariants.

## 1. Syntax Mechanics: The Power of Compound Headers

Compound statement headers (such as \`if\`, \`while\`, \`for\`, \`def\`, \`class\`) require proper delimitation. In languages like Python, this is signified with a trailing colon (\`:\`):

\`\`\`python
# Valid compound statement header
if threshold > 0:
    print("Positive threshold detected")
\`\`\`

### Common Syntax Errors to Avoid:
| Construct | Incorrect Syntax | Valid Syntax | Explanation |
| :--- | :--- | :--- | :--- |
| \`if\` condition | \`if x > 10\` | \`if x > 10:\` | Header requires trailing colon |
| \`while\` loop | \`while True\` | \`while True:\` | Loop header opens block with colon |
| \`def\` function | \`def solve()\` | \`def solve():\` | Function signature terminator |
| Variable Names | \`2nd_val = 10\` | \`val_2 = 10\` | Identifiers cannot begin with numeric digits |

---

## 2. Loop Termination & Invariants

An **invariant** is a state condition that remains true across every iteration. To prevent an endless loop that locks execution:

> [!IMPORTANT]
> The loop control variable must monotonically progress toward the terminating boundary condition.

\`\`\`python
i = 1
while i < 5:
    print(f"Step {i}")
    i += 1
\`\`\`

- [x] Master compound header syntax
- [x] Enforce terminating invariants
- [ ] Complete Chapter 1 exercises
`,
      problems: [
        {
          id: 1,
          chapter_id: 1,
          global_index: 0,
          title: "01_syntax_colon.py",
          difficulty: "Easy",
          type: "syntax_problem",
          mode: "code",
          guiding_question: "Spot and plug in the missing syntax token to complete the if-statement header.",
          concept_hint: "Compound statement headers require a colon ':' before the indented suite.",
          explanation: "In Python, compound statements like `if` require a trailing colon `:` to open an indented block.",
          code_prefix: "x = 42\nif x > 10",
          code_suffix: "\n    print(\"Threshold satisfied\")\n    status = \"OK\"",
          options: [":", ";", " then:", "->"],
          correct_answer: ":",
          test_cases: [
            "[COMPILER] Token ':' registered cleanly.",
            "[STDOUT] Threshold satisfied"
          ]
        },
        {
          id: 2,
          chapter_id: 1,
          global_index: 1,
          title: "02_loop_guard.py",
          difficulty: "Easy",
          type: "slot_plugin",
          mode: "code",
          guiding_question: "Select and plug in the condition that allows the loop to run exactly 4 times and terminate cleanly.",
          concept_hint: "Starting at i = 1 with i += 1 each iteration, find the boundary yielding 4 iterations.",
          explanation: "With `i = 1` and `i += 1`, `i < 5` runs for i = 1, 2, 3, 4 and terminates at i = 5.",
          code_prefix: "i = 1\nwhile ",
          code_suffix: ":\n    print(\"tick\")\n    i += 1",
          options: ["i < 5", "True", "i == 1", "i > 1000000"],
          correct_answer: "i < 5",
          test_cases: [
            "[SIMULATING] while i < 5:",
            "tick", "tick", "tick", "tick",
            "[SUCCESS] Loop terminated cleanly at i=5."
          ]
        },
        {
          id: 3,
          chapter_id: 1,
          global_index: 2,
          title: "03_identifier_quiz.md",
          difficulty: "Easy",
          type: "question",
          mode: "code",
          guiding_question: "Analyze language grammar rules and select the illegal variable identifier.",
          question_text: "According to standard lexical rules, which of the following variable assignments will immediately raise a SyntaxError?",
          concept_hint: "Identifiers can contain letters and underscores, but cannot begin with a number.",
          explanation: "Variable names cannot start with a digit. Therefore, `2nd_score = 98` is illegal.",
          options: ["2nd_score = 98", "score_2nd = 98", "_score_2 = 98", "ScoreSecond = 98"],
          correct_answer: "2nd_score = 98",
          test_cases: [
            "[LEXER] Flagged numeric prefix as SyntaxError [PASS]"
          ]
        }
      ]
    },
    {
      id: 2,
      title: "Chapter 2: Logic Invariants & Block Construction",
      summary: "Construct multi-line indented algorithms and prevent off-by-one errors.",
      estimated_time_minutes: 25,
      content_markdown: `# Chapter 2: Logic Invariants & Block Construction

In this chapter, we bridge the gap between individual syntax tokens and **indented structural logic**.

## 1. Zero-Based Indexing & The Off-By-One Pitfall

Sequences use zero-based indexing. The last valid element is at \`len(items) - 1\`:

\`\`\`python
items = ["alpha", "beta", "gamma"]
# Index:   0        1        2
\`\`\`

---

## 2. Editor Indentation Architecture

Indentations reflect scope nesting. Each block level adds 4 spaces:

\`\`\`python
def filter_positive(numbers):
    results = []
    for n in numbers:
        if n > 0:
            results.append(n)
    return results
\`\`\`
`,
      problems: [
        {
          id: 4,
          chapter_id: 2,
          global_index: 3,
          title: "04_boundary_logic.py",
          difficulty: "Moderate",
          type: "logic_problem",
          mode: "code",
          guiding_question: "Select and plug in the expression that safely retrieves the final element of any list without an IndexError.",
          concept_hint: "Lists are 0-indexed, so the last element is at length minus one.",
          explanation: "Zero-based indexing requires `len(items) - 1` to target the final element.",
          code_prefix: "def get_last_element(items):\n    if not items:\n        return None\n    return items[",
          code_suffix: "]\n\nprint(get_last_element([10, 20, 30, 40]))",
          options: ["len(items) - 1", "len(items)", "len(items) + 1", "0"],
          correct_answer: "len(items) - 1",
          test_cases: [
            "[EXECUTE] get_last_element([10, 20, 30, 40])",
            "[OUTPUT] 40 [PASS]"
          ]
        },
        {
          id: 5,
          chapter_id: 2,
          global_index: 4,
          title: "05_even_sum_blocks.py",
          difficulty: "Moderate",
          type: "block_builder",
          mode: "code",
          guiding_question: "Assemble the code blocks in proper sequential order. Notice that each block inserts as real text into the editor with authentic indentation.",
          concept_hint: "Initialize running total, iterate with for, check modulo (n % 2 == 0), accumulate, and return total.",
          explanation: "The proper sequence initializes total=0 at 4 spaces, loops through nums, filters even values, accumulates, and returns total.",
          blocks_pool: [
            "def sum_even_numbers(nums):",
            "    total = 0",
            "    for n in nums:",
            "        if n % 2 == 0:",
            "            total += n",
            "    return total",
            "        if n % 2 != 0:",
            "            total = n"
          ],
          correct_blocks: [
            "def sum_even_numbers(nums):",
            "    total = 0",
            "    for n in nums:",
            "        if n % 2 == 0:",
            "            total += n",
            "    return total"
          ],
          test_cases: [
            "[TEST 1] sum_even_numbers([1, 2, 3, 4, 5, 6]) == 12 [PASS]",
            "[TEST 2] sum_even_numbers([2, 4, 8]) == 14 [PASS]"
          ]
        }
      ]
    }
  ]
};

const DEFAULT_MATH_CURRICULUM = {
  course_title: "Calculus & Analysis: Limits, Derivatives & Integrals",
  domain: "Pure Mathematics",
  mode: "math",
  level_num: 1,
  level_title: "Level 1: Differential Calculus & Limit Foundations",
  overview: "Master differential and integral calculus through rigorous mathematical equations, derivative operator rules, and step-by-step proof derivations.",
  chapters: [
    {
      id: 1,
      title: "Chapter 1: Limits & The Power Rule",
      summary: "Master the limit definition of the derivative and the polynomial power rule in differential calculus.",
      estimated_time_minutes: 20,
      content_markdown: `# Chapter 1: Limits & The Power Rule

Welcome to **&edu Studio: Mathematics**. In this chapter, we explore foundational differential calculus, rate of change, and algebraic derivation rules.

## 1. The Limit Definition of the Derivative

The derivative of a function $f(x)$ at any point $x$ is defined as the limit of the difference quotient as the increment $h$ approaches zero:

$$f'(x) = \\lim_{h \\to 0} \\frac{f(x + h) - f(x)}{h}$$

If this limit exists, $f(x)$ is differentiable at $x$.

### Fundamental Derivative Rules:
| Function | Derivative Formula | Condition / Restriction |
| :--- | :--- | :--- |
| Constant $c$ | $\\frac{d}{dx}[c] = 0$ | $c \\in \\mathbb{R}$ |
| Power $x^n$ | $\\frac{d}{dx}[x^n] = n x^{n-1}$ | $n \\in \\mathbb{R}$ |
| Exponential $e^x$ | $\\frac{d}{dx}[e^x] = e^x$ | Natural base |
| Logarithm $\\ln(x)$ | $\\frac{d}{dx}[\\ln(x)] = \\frac{1}{x}$ | $x > 0$ |

---

## 2. The Power Rule In Action

For any real exponent $n$, the power rule states:

$$\\frac{d}{dx}[x^n] = n x^{n-1}$$

For example, when $f(x) = x^4$:
1. Exponent: $n = 4$
2. Multiply by exponent: $4 \\cdot x$
3. Decrement exponent by 1: $4 - 1 = 3$
4. Result: $f'(x) = 4x^3$
`,
      problems: [
        {
          id: 1,
          chapter_id: 1,
          global_index: 0,
          title: "01_derivative_power_rule.math",
          difficulty: "Easy",
          type: "slot_plugin",
          mode: "math",
          guiding_question: "Compute the derivative using the power rule: complete the equation for d/dx [x^4].",
          concept_hint: "Remember d/dx [x^n] = n * x^(n - 1). Here n = 4.",
          explanation: "Applying the power rule d/dx [x^4] = 4 * x^(4-1) = 4x^3.",
          code_prefix: "\\frac{d}{dx}\\left[x^4\\right] = ",
          code_suffix: "",
          options: ["4x^3", "3x^4", "4x^5", "\\frac{x^5}{5}"],
          correct_answer: "4x^3",
          test_cases: [
            "[VERIFY] Checking mathematical equivalence...",
            "[IDENTITY] d/dx[x^4] = 4x^3 evaluated to TRUE."
          ]
        },
        {
          id: 2,
          chapter_id: 1,
          global_index: 1,
          title: "02_product_rule_formula.math",
          difficulty: "Easy",
          type: "logic_problem",
          mode: "math",
          guiding_question: "Select the correct expansion of the product rule for differentiating the product of two functions u(x) and v(x).",
          concept_hint: "The product rule is 'first times derivative of second plus second times derivative of first'.",
          explanation: "By Leibniz's product rule, (u * v)' = u'v + uv'. The derivative of a product is NOT simply the product of derivatives u'v'.",
          code_prefix: "\\frac{d}{dx}\\left[u(x) \\cdot v(x)\\right] = ",
          code_suffix: "",
          options: ["u'(x)v(x) + u(x)v'(x)", "u'(x) \\cdot v'(x)", "u'(x)v'(x) - u(x)v(x)", "\\frac{u'(x)}{v'(x)}"],
          correct_answer: "u'(x)v(x) + u(x)v'(x)",
          test_cases: [
            "[CALCULUS_ASSERTION] Product rule differential identity verified."
          ]
        },
        {
          id: 3,
          chapter_id: 1,
          global_index: 2,
          title: "03_trig_limit_quiz.md",
          difficulty: "Moderate",
          type: "question",
          mode: "math",
          guiding_question: "Evaluate the fundamental trigonometric limit as x approaches 0.",
          question_text: "What is the exact value of the foundational calculus limit: $\\lim_{x \\to 0} \\frac{\\sin(x)}{x}$?",
          concept_hint: "Consider the Squeeze Theorem applied to the unit circle as arc angle x approaches 0 radians.",
          explanation: "By the Squeeze Theorem (or L'Hôpital's rule: cos(0)/1), the limit of sin(x)/x as x -> 0 is exactly 1.",
          options: ["1", "0", "\\infty", "\\text{Undefined}"],
          correct_answer: "1",
          test_cases: [
            "[LIMIT_CHECK] lim_{x->0} sin(x)/x evaluated: result is 1."
          ]
        }
      ]
    },
    {
      id: 2,
      title: "Chapter 2: Integration & The Fundamental Theorem",
      summary: "Master definite integrals, antidifferentiation, and area accumulation under curves.",
      estimated_time_minutes: 25,
      content_markdown: `# Chapter 2: Integration & The Fundamental Theorem

Integration represents continuous accumulation: summing an infinite number of infinitesimally thin slices.

## 1. The Fundamental Theorem of Calculus (FTC)

If $f(x)$ is continuous on $[a, b]$ and $F'(x) = f(x)$, then:

$$\\int_a^b f(x) dx = F(b) - F(a)$$

This monumental theorem links **derivatives (slopes)** directly to **integrals (areas)**.

### Integral Table:
| Integrand $f(x)$ | Indefinite Integral $\\int f(x)dx$ |
| :--- | :--- |
| $x^n$ ($n \\neq -1$) | $\\frac{x^{n+1}}{n+1} + C$ |
| $\\frac{1}{x}$ | $\\ln|x| + C$ |
| $e^x$ | $e^x + C$ |
| $\\cos(x)$ | $\\sin(x) + C$ |
`,
      problems: [
        {
          id: 4,
          chapter_id: 2,
          global_index: 3,
          title: "04_definite_integral_step.math",
          difficulty: "Moderate",
          type: "slot_plugin",
          mode: "math",
          guiding_question: "Evaluate the definite integral of 3x^2 from x = 0 to x = 2.",
          concept_hint: "Antiderivative of 3x^2 is x^3. Evaluate at upper bound (2^3) minus lower bound (0^3).",
          explanation: "The antiderivative is F(x) = x^3. Applying FTC: F(2) - F(0) = 2^3 - 0 = 8.",
          code_prefix: "\\int_0^2 3x^2 \\, dx = \\left[ x^3 \\right]_0^2 = ",
          code_suffix: "",
          options: ["8", "12", "6", "4"],
          correct_answer: "8",
          test_cases: [
            "[INTEGRAL_EVALUATION] [x^3]_0^2 = 8 - 0 = 8 [VERIFIED]"
          ]
        },
        {
          id: 5,
          chapter_id: 2,
          global_index: 4,
          title: "05_derivation_steps.math",
          difficulty: "Moderate",
          type: "block_builder",
          mode: "math",
          guiding_question: "Assemble the mathematical steps in sequential order to prove that d/dx [ln(x)] = 1/x using implicit differentiation with y = ln(x).",
          concept_hint: "Start with y = ln(x), exponentiate both sides to get e^y = x, differentiate implicitly with respect to x, then substitute e^y = x back.",
          explanation: "y = ln(x) => e^y = x => d/dx[e^y] = d/dx[x] => e^y * (dy/dx) = 1 => dy/dx = 1/e^y = 1/x.",
          blocks_pool: [
            "\\text{Let } y = \\ln(x) \\quad (x > 0)",
            "e^y = x",
            "\\frac{d}{dx}\\left[e^y\\right] = \\frac{d}{dx}[x]",
            "e^y \\cdot \\frac{dy}{dx} = 1",
            "\\frac{dy}{dx} = \\frac{1}{e^y} = \\frac{1}{x}",
            "\\frac{dy}{dx} = e^x \\cdot \\ln(x)"
          ],
          correct_blocks: [
            "\\text{Let } y = \\ln(x) \\quad (x > 0)",
            "e^y = x",
            "\\frac{d}{dx}\\left[e^y\\right] = \\frac{d}{dx}[x]",
            "e^y \\cdot \\frac{dy}{dx} = 1",
            "\\frac{dy}{dx} = \\frac{1}{e^y} = \\frac{1}{x}"
          ],
          test_cases: [
            "[PROOF_STEP 1] Valid logarithmic definition [PASS]",
            "[PROOF_STEP 2] Correct exponential inversion [PASS]",
            "[PROOF_STEP 3] Chain rule differential verified [PASS]",
            "[PROOF_STEP 4] dy/dx = 1/x Q.E.D. [PASS]"
          ]
        }
      ]
    },
    {
      id: 3,
      title: "Chapter 3: Integration Techniques & Applications",
      summary: "Master substitution, integration by parts, and calculating areas enclosed between curves.",
      estimated_time_minutes: 30,
      content_markdown: `# Chapter 3: Integration Techniques & Applications

When an integrand cannot be antidifferentiated directly using elementary power rules, we deploy two primary transformation strategies: **Integration by Substitution** (the chain rule in reverse) and **Integration by Parts** (the product rule in reverse).

## 1. Integration by Substitution (U-Sub)

If $u = g(x)$, then $du = g'(x) dx$:

$$\\int f(g(x)) g'(x) dx = \\int f(u) du$$

## 2. Integration by Parts (IBP)

Derived from the differential product rule $d(uv) = u\\,dv + v\\,du$:

$$\\int u \\, dv = u v - \\int v \\, du$$

### Strategy Guideline (LIATE Rule for picking $u$):
1. **L**ogarithmic functions ($\\ln(x)$)
2. **I**nverse trigonometric functions ($\\arctan(x)$)
3. **A**lgebraic polynomials ($x^2, 3x$)
4. **T**rigonometric functions ($\\sin(x), \\cos(x)$)
5. **E**xponential functions ($e^x$)

> [!TIP]
> Choose $u$ as the term that simplifies most upon differentiation, and $dv$ as the part easiest to integrate!
`,
      problems: [
        {
          id: 6,
          chapter_id: 3,
          global_index: 5,
          title: "06_u_substitution.math",
          difficulty: "Moderate",
          type: "slot_plugin",
          mode: "math",
          guiding_question: "Evaluate the indefinite integral $\\int 2x e^{x^2} dx$ using the substitution $u = x^2$ where $du = 2x dx$.",
          concept_hint: "Substitute $u = x^2$, integrate $e^u du = e^u + C$, and substitute back.",
          explanation: "With $u = x^2$ and $du = 2x dx$, $\\int 2x e^{x^2} dx = \\int e^u du = e^u + C = e^{x^2} + C$.",
          code_prefix: "\\int 2x e^{x^2} \\, dx = \\int e^u \\, du = ",
          code_suffix: "",
          options: ["e^{x^2} + C", "2e^{x^2} + C", "\\frac{e^{x^2}}{2} + C", "x^2 e^{x^2} + C"],
          correct_answer: "e^{x^2} + C",
          test_cases: [
            "[U_SUB] Variable change u = x^2 verified.",
            "[INTEGRAL] Antiderivative e^{x^2} + C verified via differentiation."
          ]
        },
        {
          id: 7,
          chapter_id: 3,
          global_index: 6,
          title: "07_integration_by_parts_formula.math",
          difficulty: "Moderate",
          type: "logic_problem",
          mode: "math",
          guiding_question: "Select the correct formula for evaluating $\\int x \\cos(x) dx$ using integration by parts with $u = x$ and $dv = \\cos(x) dx$.",
          concept_hint: "Here $du = dx$ and $v = \\sin(x)$. Apply $\\int u dv = uv - \\int v du$.",
          explanation: "Applying $\\int u dv = uv - \\int v du$ gives $x \\sin(x) - \\int \\sin(x) dx = x \\sin(x) + \\cos(x) + C$.",
          code_prefix: "\\int x \\cos(x) \\, dx = ",
          code_suffix: "",
          options: [
            "x \\sin(x) + \\cos(x) + C",
            "x \\cos(x) - \\sin(x) + C",
            "\\frac{x^2}{2} \\sin(x) + C",
            "-x \\sin(x) + \\cos(x) + C"
          ],
          correct_answer: "x \\sin(x) + \\cos(x) + C",
          test_cases: [
            "[IBP_EVAL] d/dx [x sin(x) + cos(x)] = sin(x) + x cos(x) - sin(x) = x cos(x) [VERIFIED]"
          ]
        }
      ]
    }
  ]
};

DEFAULT_CODE_CURRICULUM.problems = DEFAULT_CODE_CURRICULUM.chapters.flatMap(ch => ch.problems);
DEFAULT_MATH_CURRICULUM.problems = DEFAULT_MATH_CURRICULUM.chapters.flatMap(ch => ch.problems);

// ---------------------------------------------------------------------------
// RESILIENT KATEX MATH EQUATION & INLINE FORMULA RENDERER
// ---------------------------------------------------------------------------
const InlineMathText = ({ content, inline = false }) => {
  if (!content) return null;
  // Normalize LaTeX delimiters \[ \] and \( \)
  let text = String(content)
    .replace(/\\\[([\s\S]*?)\\\]/g, '$$$$$1$$$$')
    .replace(/\\\(([\s\S]*?)\\\)/g, '$$$1$$');

  // If contains LaTeX macros like \lim or \frac but no $ delimiters
  if (!text.includes('$') && /\\[a-zA-Z]+/.test(text)) {
    text = text.replace(/(\\[a-zA-Z]+(?:\{[^{}]*\}|\[[^\[\]]*\]|[_\^]\{[^{}]*\}|[_\^][a-zA-Z0-9]|[a-zA-Z0-9\s\+\-\*\/\(\)\=\<\>]+)*\??)/g, (m) => {
      const endsWithQ = m.endsWith('?');
      const inner = endsWithQ ? m.slice(0, -1).trim() : m.trim();
      return `$${inner}$` + (endsWithQ ? '?' : '');
    });
  }

  const parts = [];
  const regex = /(\$\$[\s\S]*?\$\$|\$[^\$\n]+?\$)/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', val: text.substring(lastIndex, match.index) });
    }
    const raw = match[0];
    const isDisplay = raw.startsWith('$$');
    const inner = isDisplay ? raw.slice(2, -2).trim() : raw.slice(1, -1).trim();
    try {
      const html = katex.renderToString(inner, { displayMode: isDisplay, throwOnError: false });
      parts.push({ type: 'math', html, isDisplay });
    } catch (e) {
      parts.push({ type: 'text', val: raw });
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push({ type: 'text', val: text.substring(lastIndex) });
  }

  if (parts.length === 0) {
    return <span>{text}</span>;
  }

  return (
    <span style={{ display: inline ? 'inline' : 'inline-block' }}>
      {parts.map((p, idx) => {
        if (p.type === 'math') {
          return (
            <span
              key={idx}
              className="katex-rendered-wrapper"
              dangerouslySetInnerHTML={{ __html: p.html }}
              style={{
                display: p.isDisplay ? 'block' : 'inline-block',
                margin: p.isDisplay ? '8px 0' : '0 3px',
                verticalAlign: p.isDisplay ? 'baseline' : 'middle',
                color: '#ffffff'
              }}
            />
          );
        }
        return <span key={idx}>{p.val}</span>;
      })}
    </span>
  );
};

const MathFormula = ({ math, inline = false }) => {
  if (!math && math !== '') return null;
  const str = String(math).trim();
  if (!str) return null;

  // Check if string contains mixed text or delimiters
  const hasDelimiters = str.includes('$') || str.includes('\\[') || str.includes('\\(');
  const wordTokens = (str.match(/[A-Za-z]{4,}/g) || []).filter(w => !['frac', 'sqrt', 'cdot', 'times', 'left', 'right', 'text', 'partial', 'alpha', 'beta', 'theta', 'gamma'].includes(w.toLowerCase()));
  const isMixedSentence = wordTokens.length >= 2;

  if (hasDelimiters || isMixedSentence) {
    return <InlineMathText content={str} inline={inline} />;
  }

  // Pure LaTeX formula
  const clean = str.replace(/^\$+|\$+$/g, '').trim();
  try {
    const html = katex.renderToString(clean, {
      displayMode: !inline,
      throwOnError: false
    });
    return (
      <span 
        className="katex-rendered-wrapper"
        dangerouslySetInnerHTML={{ __html: html }} 
        style={{ 
          display: inline ? 'inline-block' : 'block',
          color: theme.textMain,
          verticalAlign: inline ? 'middle' : 'baseline'
        }}
      />
    );
  } catch (e) {
    return <span style={{ fontFamily: theme.fontMono, color: theme.accentBlue }}>{clean}</span>;
  }
};

// ---------------------------------------------------------------------------
// SYNTAX HIGHLIGHTING & INDENTATION HELPER
// ---------------------------------------------------------------------------
const PythonToken = ({ token }) => {
  const keywords = new Set([
    'def', 'class', 'if', 'elif', 'else', 'while', 'for', 'in', 'return', 
    'import', 'from', 'as', 'try', 'except', 'finally', 'with', 'pass', 
    'break', 'continue', 'lambda', 'yield', 'raise', 'assert', 'not', 
    'and', 'or', 'is', 'None', 'True', 'False', 'const', 'let', 'var', 'function'
  ]);
  const builtins = new Set([
    'print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict', 'set', 
    'tuple', 'sum', 'min', 'max', 'abs', 'enumerate', 'zip', 'map', 'filter', 'open', 'console', 'log'
  ]);

  if (keywords.has(token)) {
    return <span style={{ color: theme.accentPink, fontWeight: 600 }}>{token}</span>;
  }
  if (builtins.has(token)) {
    return <span style={{ color: theme.accentBlue }}>{token}</span>;
  }
  if (/^["'].*["']$/.test(token)) {
    return <span style={{ color: theme.accentYellow }}>{token}</span>;
  }
  if (/^\d+(\.\d+)?$/.test(token)) {
    return <span style={{ color: theme.accentPurple }}>{token}</span>;
  }
  if (token.startsWith('#') || token.startsWith('//')) {
    return <span style={{ color: theme.textMuted, fontStyle: 'italic' }}>{token}</span>;
  }
  if (/^[()\[\]{}:,=+\-*/<>!&|^%]+$/.test(token)) {
    return <span style={{ color: theme.accentPink }}>{token}</span>;
  }
  return <span style={{ color: theme.textMain }}>{token}</span>;
};

const HighlightedLine = ({ code, lineNum }) => {
  if (!code && code !== '') code = '';
  const indentMatch = code.match(/^[ ]+/);
  const leadingSpaces = indentMatch ? indentMatch[0].length : 0;
  const content = code.slice(leadingSpaces);

  const tokens = content.match(/([A-Za-z_][A-Za-z0-9_]*|#.*|\/\/.*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\d+(?:\.\d+)?|[()\[\]{}:,=+\-*/<>!&|^%]+|\s+)/g) || [content];
  const indentLevels = Math.floor(leadingSpaces / 4);
  const remainingSpaces = leadingSpaces % 4;

  return (
    <div style={{ display: 'flex', alignItems: 'center', minHeight: '22px', fontSize: '13px', lineHeight: '22px' }}>
      <span style={{ 
        width: '42px', 
        textAlign: 'right', 
        paddingRight: '16px', 
        color: theme.textMuted, 
        userSelect: 'none',
        flexShrink: 0,
        fontFamily: theme.fontMono,
        fontSize: '12px'
      }}>
        {lineNum}
      </span>

      <div style={{ display: 'inline-flex', alignItems: 'stretch' }}>
        {Array.from({ length: indentLevels }).map((_, i) => (
          <span key={i} style={{ 
            display: 'inline-block', 
            width: '28px', 
            borderLeft: `1px solid ${theme.border}`, 
            height: '22px', 
            boxSizing: 'border-box' 
          }} />
        ))}
        {remainingSpaces > 0 && (
          <span style={{ display: 'inline-block', width: `${remainingSpaces * 7}px` }} />
        )}
      </div>

      <span style={{ whiteSpace: 'pre', fontFamily: theme.fontMono }}>
        {tokens.map((tok, idx) => (
          /\s+/.test(tok) ? <span key={idx}>{tok}</span> : <PythonToken key={idx} token={tok} />
        ))}
      </span>
    </div>
  );
};

// ---------------------------------------------------------------------------
// GFM MARKDOWN WITH EMBEDDED KATEX FORMULAS
// ---------------------------------------------------------------------------
const VSCodeMarkdown = ({ content }) => {
  // Normalize LaTeX display \[ \] to $$ and inline \( \) to $
  const normalized = (content || '')
    .replace(/\\\[([\s\S]*?)\\\]/g, '$$\n$1\n$$')
    .replace(/\\\(([\s\S]*?)\\\)/g, '$$$1$$');

  return (
    <div className="vscode-markdown" style={{ color: theme.textMain, fontSize: '13px', lineHeight: '1.6' }}>
      <ReactMarkdown 
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          h1: ({ children }) => (
            <h1 style={{ fontSize: '20px', fontWeight: 700, color: theme.textMain, borderBottom: `1px solid ${theme.borderContrast}`, paddingBottom: '6px', margin: '14px 0 10px 0' }}>{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 style={{ fontSize: '16px', fontWeight: 600, color: theme.accentBlue, borderBottom: `1px solid ${theme.border}`, paddingBottom: '4px', margin: '18px 0 8px 0' }}>{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: theme.accentGreen, margin: '14px 0 6px 0' }}>{children}</h3>
          ),
          p: ({ children }) => (
            <p style={{ margin: '8px 0', color: theme.textDim, lineHeight: '1.6' }}>{children}</p>
          ),
          blockquote: ({ children }) => (
            <blockquote style={{ margin: '10px 0', padding: '8px 14px', borderLeft: `3px solid ${theme.accentOrange}`, backgroundColor: theme.bgCardAlt, borderRadius: '0 4px 4px 0', color: theme.accentYellow }}>{children}</blockquote>
          ),
          table: ({ children }) => (
            <div style={{ overflowX: 'auto', margin: '12px 0' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', border: `1px solid ${theme.borderContrast}`, fontSize: '12px', fontFamily: theme.fontMono }}>{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th style={{ backgroundColor: theme.bgCardAlt, border: `1px solid ${theme.borderContrast}`, padding: '7px 10px', textAlign: 'left', color: theme.accentBlue, fontWeight: 600 }}>{children}</th>
          ),
          td: ({ children }) => (
            <td style={{ border: `1px solid ${theme.border}`, padding: '6px 10px', color: theme.textMain }}>{children}</td>
          ),
          code: ({ inline, children }) => {
            if (!inline) {
              return (
                <pre style={{ margin: '10px 0', padding: '12px', backgroundColor: theme.bgPanel, border: `1px solid ${theme.borderContrast}`, borderRadius: '4px', overflowX: 'auto', fontFamily: theme.fontMono, fontSize: '12px', color: theme.textMain }}>
                  <code>{children}</code>
                </pre>
              );
            }
            return (
              <code style={{ backgroundColor: theme.bgCardAlt, border: `1px solid ${theme.borderContrast}`, color: theme.accentYellow, padding: '2px 5px', borderRadius: '3px', fontSize: '11px', fontFamily: theme.fontMono }}>
                {children}
              </code>
            );
          }
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
};

// ---------------------------------------------------------------------------
// MAIN EDU IDE COMPONENT (3-PANEL HIGH-CONTRAST ALIGNMENT)
// ---------------------------------------------------------------------------
const EduIDE = () => {
  // App Mode: 'code' | 'math'
  const [appMode, setAppMode] = useState("code");

  // Ingestion & File Inputs (Multiple Files Support)
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [documentText, setDocumentText] = useState("");
  const [topicInput, setTopicInput] = useState("Python loops: accumulator pattern, iterating over a list, summing positive numbers");
  const [loading, setLoading] = useState(false);
  const [escalating, setEscalating] = useState(false);

  // Curriculum State
  const [curriculum, setCurriculum] = useState(DEFAULT_CODE_CURRICULUM);
  const [activeChapterId, setActiveChapterId] = useState(1);
  const [activeProblemIndex, setActiveProblemIndex] = useState(0);
  const [activeTab, setActiveTab] = useState("editor"); // 'editor' | 'docs'
  const [collapsedChapters, setCollapsedChapters] = useState({});

  // Progression & States
  const [currentLevel, setCurrentLevel] = useState(1);
  const [totalXp, setTotalXp] = useState(0);
  const [completedProblems, setCompletedProblems] = useState({});
  const [problemStates, setProblemStates] = useState({});

  // Pyodide WebAssembly Kernel State
  const pyodideRef = useRef(null);
  const [kernelStatus, setKernelStatus] = useState("loading");
  const [executingCode, setExecutingCode] = useState(false);

  // High-Contrast Terminal Output
  const [terminalOutput, setTerminalOutput] = useState([
    "[SYSTEM] &edu Studio initialized.",
    "[STATUS] Ready. Use Left Ingestion to upload files, switch between Code & Math modes, or assemble exercises."
  ]);

  // Socratic Mentor with Theory-First Briefings
  const briefedProblemsRef = useRef(new Set());
  const [briefLoading, setBriefLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([
    { 
      role: 'model', 
      content: "👋 Welcome to **&edu Studio**! I am your senior Socratic mentor. I will guide you **theory-first**, ask diagnostic check questions, and review your reasoning step-by-step as you progress." 
    }
  ]);
  const [userInput, setUserInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const chapters = curriculum.chapters || [];
  const flatProblems = curriculum.problems || [];
  const currentProblem = flatProblems[activeProblemIndex] || flatProblems[0] || null;
  const currentChapter = chapters.find(c => c.id === (currentProblem?.chapter_id || activeChapterId)) || chapters[0];
  const activeState = problemStates[activeProblemIndex] || {};

  // Resizable Panel Dimensions ("Drag and Drop Walls")
  const [leftWidth, setLeftWidth] = useState(280);
  const [rightWidth, setRightWidth] = useState(340);
  const [terminalHeight, setTerminalHeight] = useState(170);
  const [isDragging, setIsDragging] = useState(null); // 'left' | 'right' | 'terminal' | null

  // ElevenLabs Voiceover Audio Lecture State (Elderly Male Professor)
  const audioPlayerRef = useRef(null);
  const [voiceoverLoading, setVoiceoverLoading] = useState(false);
  const [voiceoverPlaying, setVoiceoverPlaying] = useState(false);
  const [voiceoverSource, setVoiceoverSource] = useState(null); // 'elevenlabs' | 'browser' | 'error' | null
  const [voiceoverScript, setVoiceoverScript] = useState("");
  const [voiceoverError, setVoiceoverError] = useState(null);
  const [selectedVoice, setSelectedVoice] = useState("JBFqnCBsd6RMkjVDRZzb"); // Default: Prof. George (Elderly Male Professor)
  const [showTranscript, setShowTranscript] = useState(false);
  const [elevenApiKey, setElevenApiKey] = useState(() => localStorage.getItem('andedu_elevenlabs_key') || '');

  // Scalable Curriculum Expansion States (Generate More Chapters & Exercises)
  const [targetChapterCount, setTargetChapterCount] = useState("auto"); // "auto" | 3 | 4 | 5
  const [isGeneratingChapter, setIsGeneratingChapter] = useState(false);
  const [isGeneratingProblem, setIsGeneratingProblem] = useState(false);
  const [showAddChapterModal, setShowAddChapterModal] = useState(false);
  const [newChapterTopicInput, setNewChapterTopicInput] = useState("");

  // Smooth Resizing Drag-and-Drop Event Listeners
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return;
      if (isDragging === 'left') {
        const newWidth = Math.max(160, Math.min(e.clientX, window.innerWidth - 380));
        setLeftWidth(newWidth);
      } else if (isDragging === 'right') {
        const newWidth = Math.max(200, Math.min(window.innerWidth - e.clientX, window.innerWidth - 380));
        setRightWidth(newWidth);
      } else if (isDragging === 'terminal') {
        const newHeight = Math.max(60, Math.min(window.innerHeight - e.clientY, window.innerHeight - 180));
        setTerminalHeight(newHeight);
      }
    };

    const handleMouseUp = () => {
      if (isDragging) setIsDragging(null);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  // ---------------------------------------------------------------------------
  // 1. INITIALIZE CLIENT-SIDE PYODIDE WEBASSEMBLY KERNEL
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let isMounted = true;

    const initPyodide = async () => {
      try {
        if (window.loadPyodide) {
          const py = await window.loadPyodide({
            indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"
          });
          if (isMounted) {
            pyodideRef.current = py;
            setKernelStatus("ready");
            setTerminalOutput(prev => [
              ...prev,
              "[PYODIDE KERNEL] ⚡ Client-side WebAssembly Python 3.12 Kernel ready!",
              "[RUNNER] In-browser execution enabled (0ms latency, zero server load)."
            ]);
          }
          return;
        }

        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js";
        script.onload = async () => {
          try {
            const py = await window.loadPyodide({
              indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"
            });
            if (isMounted) {
              pyodideRef.current = py;
              setKernelStatus("ready");
              setTerminalOutput(prev => [
                ...prev,
                "[PYODIDE KERNEL] ⚡ Client-side WebAssembly Python 3.12 Kernel ready!",
                "[RUNNER] In-browser execution enabled (0ms latency, zero server load)."
              ]);
            }
          } catch (e) {
            console.warn("Pyodide init error", e);
            if (isMounted) setKernelStatus("fallback");
          }
        };
        script.onerror = () => {
          if (isMounted) setKernelStatus("fallback");
        };
        document.body.appendChild(script);
      } catch (err) {
        console.warn("Failed to load Pyodide", err);
        if (isMounted) setKernelStatus("fallback");
      }
    };

    initPyodide();
    return () => { isMounted = false; };
  }, []);

  // ---------------------------------------------------------------------------
  // 2. DELIVER THEORY-FIRST MENTOR BRIEFING ON PROBLEM LOAD
  // ---------------------------------------------------------------------------
  const deliverProblemBriefing = async (problem, force = false) => {
    if (!problem) return;
    const problemKey = `${problem.chapter_id || 1}_${problem.id}_${problem.title}`;
    if (!force && briefedProblemsRef.current.has(problemKey)) return;

    briefedProblemsRef.current.add(problemKey);
    setBriefLoading(true);

    try {
      let res;
      const briefBody = JSON.stringify({
        problem,
        chapter: currentChapter,
        mode: appMode,
        level: currentLevel
      });

      try {
        res = await fetch("http://127.0.0.1:8000/api/tutor-brief", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: briefBody
        });
      } catch (e1) {
        res = await fetch("http://localhost:8000/api/tutor-brief", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: briefBody
        });
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setChatHistory(prev => [
        ...prev,
        {
          role: 'model',
          isBriefing: true,
          problemId: problem.id,
          content: data.briefing,
          suggestedActions: [
            "⚡ Give me a hard blank coding challenge",
            "🧩 Give me a partially coded scaffold",
            "Break down the theory deeper",
            "Give me a subtle hint",
            "Why do the distractors fail?"
          ]
        }
      ]);
    } catch (err) {
      // Local fallback briefing: ultra-short, concise, leading
      const isMath = appMode === 'math' || problem.mode === 'math';
      const fallbackBrief = isMath 
        ? `🎯 **Task**: Solve for ${problem.guiding_question || problem.title}.\n\n💡 **Lead**: What differentiation or integration rule applies directly to this term?\n\n❓ **Check**: Does your chosen candidate preserve signs and exponent boundaries?`
        : `🎯 **Task**: Identify the loop invariant condition.\n\n💡 **Lead**: Look at the variable mutation on each iteration step.\n\n❓ **Check**: Which boundary test guarantees the loop terminates without crashing?`;

      setChatHistory(prev => [
        ...prev,
        {
          role: 'model',
          isBriefing: true,
          problemId: problem.id,
          content: fallbackBrief,
          suggestedActions: [
            "⚡ Give me a hard blank coding challenge",
            "🧩 Give me a partially coded scaffold",
            "Explain the lead",
            "Give a subtle hint"
          ]
        }
      ]);
    } finally {
      setBriefLoading(false);
    }
  };

  // Trigger briefing on problem navigation
  useEffect(() => {
    if (currentProblem) {
      deliverProblemBriefing(currentProblem);
    }
  }, [activeProblemIndex, currentProblem?.id, appMode]);

  // ---------------------------------------------------------------------------
  // 3. SWITCH APP MODE (CODE vs MATH)
  // ---------------------------------------------------------------------------
  const handleModeChange = (newMode) => {
    setAppMode(newMode);
    briefedProblemsRef.current.clear();
    if (newMode === 'math') {
      setCurriculum(DEFAULT_MATH_CURRICULUM);
      initProblemStates(DEFAULT_MATH_CURRICULUM);
      setTopicInput("Calculus: Power rule, Product rule, and definite integrals");
      setActiveProblemIndex(0);
      setActiveChapterId(1);
      setTerminalOutput(prev => [
        ...prev,
        "----------------------------------------",
        "[MODE SWITCH] ∑ MATH MODE ACTIVATED.",
        "[FEATURES] LaTeX Equation Slots, Mathematical Derivation Proofs, and Zero Code syntax."
      ]);
    } else {
      setCurriculum(DEFAULT_CODE_CURRICULUM);
      initProblemStates(DEFAULT_CODE_CURRICULUM);
      setTopicInput("Python loops: accumulator pattern, iterating over a list, summing positive numbers");
      setActiveProblemIndex(0);
      setActiveChapterId(1);
      setTerminalOutput(prev => [
        ...prev,
        "----------------------------------------",
        "[MODE SWITCH] ⚡ CODE / PROGRAMMING MODE ACTIVATED.",
        "[FEATURES] Interactive Code Slots, Indented Blocks, and WebAssembly Python Kernel."
      ]);
    }
  };

  const initProblemStates = (curr) => {
    const states = {};
    (curr.problems || []).forEach((prob, idx) => {
      states[idx] = {
        slotChoice: null,
        assembledBlocks: [],
        availableBank: prob.blocks_pool ? [...prob.blocks_pool] : [],
        writtenCode: prob.starter_code || "# Write code here\n",
        evaluation: null,
        quizChoice: null
      };
    });
    setProblemStates(states);
  };

  const updateActiveState = (patch) => {
    setProblemStates(prev => ({
      ...prev,
      [activeProblemIndex]: {
        ...(prev[activeProblemIndex] || {}),
        ...patch
      }
    }));
  };

  // ---------------------------------------------------------------------------
  // 4. MULTI-FILE UPLOAD (FEW FILES OR ANY AMOUNT)
  // ---------------------------------------------------------------------------
  const handleMultiFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setLoading(true);
    setTerminalOutput(prev => [
      ...prev,
      `[INGESTION] Processing ${files.length} uploaded files...`
    ]);

    const formData = new FormData();
    files.forEach(f => formData.append("files", f));

    try {
      let res;
      try {
        res = await fetch("http://127.0.0.1:8000/api/upload-multimodal", {
          method: "POST",
          body: formData,
        });
      } catch (e1) {
        res = await fetch("http://localhost:8000/api/upload-multimodal", {
          method: "POST",
          body: formData,
        });
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const newFilesList = files.map(f => ({ 
        name: f.name, 
        size: (f.size / 1024).toFixed(1) + " KB",
        text: data.extracted_text || "" 
      }));
      const updatedFiles = [...uploadedFiles, ...newFilesList];
      setUploadedFiles(updatedFiles);
      setDocumentText(updatedFiles.map(f => f.text || "").filter(Boolean).join("\n\n"));

      setTerminalOutput(prev => [
        ...prev,
        `[INGESTION SUCCESS] Ingested ${files.length} document(s) (${(data.extracted_text || "").length} characters parsed).`,
        `[READY] Materials loaded. Click 'Synthesize AI Curriculum' to build lessons & tests.`
      ]);
    } catch (err) {
      setTerminalOutput(prev => [
        ...prev,
        `[ERROR] Could not parse uploaded files: ${err.message}`
      ]);
    } finally {
      setLoading(false);
    }
  };

  const removeUploadedFile = (index) => {
    const updatedFiles = uploadedFiles.filter((_, i) => i !== index);
    setUploadedFiles(updatedFiles);
    setDocumentText(updatedFiles.map(f => f.text || "").filter(Boolean).join("\n\n"));
  };

  // ---------------------------------------------------------------------------
  // 5. GENERATION & SOKRATIC CHAT
  // ---------------------------------------------------------------------------
  const handleGenerate = async () => {
    if (!topicInput.trim() && !documentText.trim()) return;

    setLoading(true);
    briefedProblemsRef.current.clear();
    setTerminalOutput([
      `[SYNTHESIS] Reading uploaded study guides & prompt request...`,
      `[SCOPE] ${documentText.length} characters parsed across ${uploadedFiles.length} file(s).`,
      `[AI ARCHITECT] Dynamically sizing lessons and practice problems to cover all concepts...`
    ]);

    try {
      let res;
      const curriculumBody = JSON.stringify({
        user_instruction: topicInput,
        document_text: documentText,
        level: currentLevel,
        mode: appMode,
        target_chapters: targetChapterCount === "auto" ? null : Number(targetChapterCount)
      });
      try {
        res = await fetch("http://127.0.0.1:8000/api/generate-curriculum", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: curriculumBody
        });
      } catch (e1) {
        res = await fetch("http://localhost:8000/api/generate-curriculum", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: curriculumBody
        });
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setCurriculum(data);
      initProblemStates(data);
      const firstChapterId = data.chapters?.[0]?.id || 1;
      setActiveChapterId(firstChapterId);
      setActiveProblemIndex(0);
      setActiveTab("editor");

      setTerminalOutput(prev => [
        ...prev,
        `----------------------------------------`,
        `[CURRICULUM BUILT] ${data.course_title}`,
        `[AI SIZING] Generated ${data.chapters?.length || 0} lessons with ${data.problems?.length || 0} exercises and tests.`,
        `[STATUS] Ready. Study the notes in README.md or begin Chapter 1 exercises!`
      ]);
    } catch (err) {
      console.warn(err);
      setTerminalOutput(prev => [
        ...prev,
        `[NOTICE] Generation network error: ${err.message}. Loaded built-in master track.`
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleMakeHarder = async () => {
    setEscalating(true);
    const nextLevel = currentLevel + 1;
    briefedProblemsRef.current.clear();

    try {
      let res;
      const harderBody = JSON.stringify({
        topic: curriculum.course_title || topicInput,
        current_level: currentLevel,
        document_text: documentText,
        mode: appMode
      });
      try {
        res = await fetch("http://127.0.0.1:8000/api/make-harder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: harderBody
        });
      } catch (e1) {
        res = await fetch("http://localhost:8000/api/make-harder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: harderBody
        });
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setCurrentLevel(nextLevel);
      setTotalXp(prev => prev + 50);
      setCurriculum(data);
      initProblemStates(data);
      setActiveProblemIndex(0);

      setTerminalOutput(prev => [
        ...prev,
        `[TIER ESCALATED] ⚡ Promoted to Level ${nextLevel}! +50 Bonus XP awarded.`,
        `[HARD CHALLENGES] Included blank-space coding challenges and partial scaffold exercises.`
      ]);
    } catch (err) {
      setTerminalOutput(prev => [
        ...prev,
        `[ERROR] Escalation error: ${err.message}`
      ]);
    } finally {
      setEscalating(false);
    }
  };

  // ---------------------------------------------------------------------------
  // 5b. ELEVENLABS ACCESSIBLE LECTURE VOICEOVER (API FROM ENV VARIABLE OR UI KEY)
  // ---------------------------------------------------------------------------
  const handlePlayBrowserFallbackSpeech = () => {
    if (!currentChapter) return;
    const scriptToSpeak = voiceoverScript || `Ah, greetings my student. Welcome to ${currentChapter?.title || 'this lesson'}. Study the core invariants and work through the exercises together.`;
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(scriptToSpeak);
      utterance.rate = 0.92;
      utterance.pitch = 0.85;
      const voices = window.speechSynthesis.getVoices();
      const maleVoice = voices.find(v => /daniel|george|alex|fred|male|oliver|david|guy|uk english male/i.test(v.name));
      if (maleVoice) utterance.voice = maleVoice;
      utterance.onend = () => setVoiceoverPlaying(false);
      utterance.onerror = () => setVoiceoverPlaying(false);
      window.speechSynthesis.speak(utterance);
      setVoiceoverPlaying(true);
      setVoiceoverSource("browser");
      setTerminalOutput(prev => [
        ...prev,
        `[SPEECH FALLBACK] 🔊 Playing via browser speech synthesis (robot voice fallback).`
      ]);
    }
  };

  const handleGenerateVoiceover = async () => {
    if (voiceoverPlaying) {
      handleStopVoiceover();
      return;
    }

    setVoiceoverLoading(true);
    setVoiceoverError(null);
    setTerminalOutput(prev => [
      ...prev,
      `[VOICEOVER] 🎙️ Professor is preparing lecture for: "${currentChapter?.title || 'Lesson'}"...`,
      `[VOICE PROFILE] 👨‍🏫 Voice: ${selectedVoice === 'JBFqnCBsd6RMkjVDRZzb' ? 'Prof. George (Distinguished British Scholar)' : selectedVoice === 'VR6AewLTigWG4xSOukaG' ? 'Prof. Arnold (Crisp American Scholar)' : 'Prof. Daniel (Authoritative Broadcaster)'}...`
    ]);

    try {
      // 1. Attempt backend generation with IPv6/IPv4 automatic fallback
      let res;
      const payloadBody = JSON.stringify({
        chapter_title: currentChapter?.title || "Lesson Overview",
        course_title: curriculum.course_title || "Course Track",
        content_markdown: currentChapter?.content_markdown || "",
        voice_id: selectedVoice || "JBFqnCBsd6RMkjVDRZzb",
        api_key: elevenApiKey.trim() || undefined
      });

      try {
        res = await fetch("http://localhost:8000/api/elevenlabs-voiceover", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payloadBody
        });
      } catch (e1) {
        // Fallback to 127.0.0.1 in case localhost resolved to IPv6 ::1
        res = await fetch("http://127.0.0.1:8000/api/elevenlabs-voiceover", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payloadBody
        });
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();

      let finalAudioBase64 = data.audio_base64;
      let finalVoiceName = data.voice_name || 'Prof. George (Elderly Professor)';
      const returnedScript = data.script || "";
      setVoiceoverScript(returnedScript);

      // 2. If backend did not synthesize audio (e.g. key issue on server), but user provided key in UI
      if (!finalAudioBase64 && elevenApiKey.trim() && returnedScript) {
        setTerminalOutput(prev => [...prev, `[ELEVENLABS DIRECT] 🌐 Calling ElevenLabs API directly with client key...`]);
        try {
          const directRes = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${selectedVoice}`, {
            method: "POST",
            headers: {
              "Accept": "audio/mpeg",
              "Content-Type": "application/json",
              "xi-api-key": elevenApiKey.trim()
            },
            body: JSON.stringify({
              text: returnedScript,
              model_id: "eleven_turbo_v2_5",
              voice_settings: {
                stability: 0.65,
                similarity_boost: 0.8,
                style: 0.15,
                use_speaker_boost: true
              }
            })
          });

          if (directRes.ok) {
            const blob = await directRes.blob();
            const reader = new FileReader();
            finalAudioBase64 = await new Promise((resolve) => {
              reader.onloadend = () => {
                const b64 = reader.result.split(',')[1];
                resolve(b64);
              };
              reader.readAsDataURL(blob);
            });
            finalVoiceName = selectedVoice === 'VR6AewLTigWG4xSOukaG' ? 'Prof. Arnold' : selectedVoice === 'onwK4e9ZLuTAKqWW03F9' ? 'Prof. Daniel' : 'Prof. George';
          } else {
            const errTxt = await directRes.text();
            throw new Error(`ElevenLabs Direct HTTP ${directRes.status}: ${errTxt}`);
          }
        } catch (directErr) {
          console.warn("Direct ElevenLabs error:", directErr);
          setVoiceoverError(directErr.message);
        }
      }

      // 3. Play high-fidelity ElevenLabs neural audio
      if (finalAudioBase64) {
        if (audioPlayerRef.current) {
          audioPlayerRef.current.pause();
        }
        const audio = new Audio("data:audio/mpeg;base64," + finalAudioBase64);
        audioPlayerRef.current = audio;
        audio.onplay = () => setVoiceoverPlaying(true);
        audio.onended = () => setVoiceoverPlaying(false);
        audio.onerror = (e) => {
          console.warn("Audio playback error", e);
          setVoiceoverPlaying(false);
          setVoiceoverError("Audio decoding error in browser.");
        };
        await audio.play();
        setVoiceoverPlaying(true);
        setVoiceoverSource("elevenlabs");
        setVoiceoverError(null);
        setTerminalOutput(prev => [
          ...prev,
          `[ELEVENLABS SUCCESS] 🔊 Playing ElevenLabs neural lecture by ${finalVoiceName}!`,
          `[SPOKEN SCRIPT] "${returnedScript.slice(0, 110)}..."`
        ]);
      } else {
        // Did not produce ElevenLabs audio - NEVER silently play robot voice!
        const errDetail = data.error_detail || data.message || "ElevenLabs returned no audio stream.";
        setVoiceoverError(errDetail);
        setVoiceoverSource("error");
        setTerminalOutput(prev => [
          ...prev,
          `[ELEVENLABS NOTICE] ⚠️ ${errDetail}`,
          `[NOTE] Check backend .env ELEVENLABS_API_KEY. Use button below for browser speech if offline.`
        ]);
      }
    } catch (err) {
      console.warn("Voiceover error:", err);
      const errMsg = `Connection error: ${err.message}. Ensure backend is running at http://localhost:8000`;
      setVoiceoverError(errMsg);
      setVoiceoverSource("error");
      setTerminalOutput(prev => [
        ...prev,
        `[VOICEOVER ERROR] ⚠️ ${errMsg}`
      ]);
    } finally {
      setVoiceoverLoading(false);
    }
  };

  const handleStopVoiceover = () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setVoiceoverPlaying(false);
  };

  // ---------------------------------------------------------------------------
  // 5c. GENERATE ADDITIONAL CHAPTER (SCALE MULTI-CHAPTER SYLLABUS)
  // ---------------------------------------------------------------------------
  const handleGenerateNewChapter = async (customTopic = null) => {
    setIsGeneratingChapter(true);
    const targetTopic = (typeof customTopic === 'string' ? customTopic : newChapterTopicInput).trim();
    const nextChapterNum = (curriculum.chapters || []).length + 1;

    setTerminalOutput(prev => [
      ...prev,
      `----------------------------------------`,
      `[CURRICULUM EXPANSION] 🚀 Synthesizing Chapter ${nextChapterNum}...`,
      targetTopic ? `[TOPIC TARGET] "${targetTopic}"` : `[AI AUTO-SEQUENCE] Determining next advancing conceptual tier...`
    ]);

    try {
      let res;
      const chapterBody = JSON.stringify({
        course_title: curriculum.course_title || "Course Track",
        domain: curriculum.domain || (appMode === 'math' ? "Pure Mathematics" : "Computer Science"),
        mode: appMode,
        level: currentLevel,
        existing_chapters: curriculum.chapters || [],
        chapter_topic: targetTopic,
        target_problems_count: 3
      });
      try {
        res = await fetch("http://127.0.0.1:8000/api/generate-chapter", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: chapterBody
        });
      } catch (e1) {
        res = await fetch("http://localhost:8000/api/generate-chapter", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: chapterBody
        });
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const newChapter = await res.json();

      // Append new chapter and re-index flat problems
      const updatedChapters = [...(curriculum.chapters || []), newChapter];
      let gIdx = 0;
      const updatedFlatProblems = [];
      const updatedProblemStates = { ...problemStates };

      updatedChapters.forEach(ch => {
        ch.problems = (ch.problems || []).map(p => {
          const np = { ...p, chapter_id: ch.id, global_index: gIdx };
          updatedFlatProblems.push(np);
          if (!updatedProblemStates[gIdx]) {
            updatedProblemStates[gIdx] = {
              slotChoice: null,
              assembledBlocks: [],
              availableBank: np.blocks_pool ? [...np.blocks_pool] : [],
              writtenCode: np.starter_code || "# Write code here\n",
              evaluation: null,
              quizChoice: null
            };
          }
          gIdx++;
          return np;
        });
      });

      const updatedCurriculum = {
        ...curriculum,
        chapters: updatedChapters,
        problems: updatedFlatProblems
      };

      setCurriculum(updatedCurriculum);
      setProblemStates(updatedProblemStates);
      setActiveChapterId(newChapter.id);
      const firstNewProbIdx = (curriculum.problems || []).length;
      if (firstNewProbIdx < updatedFlatProblems.length) {
        setActiveProblemIndex(firstNewProbIdx);
      }
      setActiveTab("docs");
      setShowAddChapterModal(false);
      setNewChapterTopicInput("");

      setTerminalOutput(prev => [
        ...prev,
        `[SUCCESS] 📚 Chapter ${newChapter.id} generated: "${newChapter.title}"`,
        `[CONTENT READY] Created ${(newChapter.problems || []).length} interactive exercises + complete study guide.`
      ]);
    } catch (err) {
      console.warn("Failed to generate chapter:", err);
      setTerminalOutput(prev => [
        ...prev,
        `[ERROR] Could not generate new chapter: ${err.message}`
      ]);
    } finally {
      setIsGeneratingChapter(false);
    }
  };

  // ---------------------------------------------------------------------------
  // 5d. GENERATE EXTRA PROBLEM FOR EXISTING CHAPTER
  // ---------------------------------------------------------------------------
  const handleGenerateProblem = async (targetChapterId, requestedType = "auto") => {
    const targetChapter = (curriculum.chapters || []).find(ch => ch.id === targetChapterId) || currentChapter;
    if (!targetChapter) return;

    setIsGeneratingProblem(true);
    const label = requestedType === 'code_blank'
      ? '⚡ HARD BLANK CODING TASK'
      : requestedType === 'code_partial'
        ? '🧩 PARTIALLY CODED SCAFFOLD'
        : 'practice exercise';
    setTerminalOutput(prev => [
      ...prev,
      `[PROBLEM GENERATOR] Generating ${label} for: "${targetChapter.title}"...`
    ]);

    try {
      let res;
      const bodyStr = JSON.stringify({
        chapter_id: targetChapter.id,
        chapter_title: targetChapter.title,
        chapter_summary: targetChapter.summary || "",
        chapter_content: targetChapter.content_markdown || "",
        course_title: curriculum.course_title || "Course Track",
        mode: appMode,
        level: currentLevel,
        problem_type: requestedType
      });

      try {
        res = await fetch("http://127.0.0.1:8000/api/generate-problem", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: bodyStr
        });
      } catch (e1) {
        res = await fetch("http://localhost:8000/api/generate-problem", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: bodyStr
        });
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const newProblem = await res.json();
      injectProblemIntoCurriculum(newProblem, targetChapter.id);
    } catch (err) {
      console.warn("Failed to generate problem:", err);
      setTerminalOutput(prev => [
        ...prev,
        `[ERROR] Could not generate problem: ${err.message}`
      ]);
    } finally {
      setIsGeneratingProblem(false);
    }
  };

  const injectProblemIntoCurriculum = (newProblem, customChapterId = null) => {
    if (!newProblem) return;
    const targetChapter = (curriculum.chapters || []).find(c => c.id === (customChapterId || currentChapter?.id)) || (curriculum.chapters || [])[0];
    if (!targetChapter) return;

    // Check if problem already exists by title
    const existingIdx = (curriculum.problems || []).findIndex(p => p.title === newProblem.title);
    if (existingIdx !== -1) {
      setActiveProblemIndex(existingIdx);
      setActiveTab("editor");
      return;
    }

    const updatedChapters = (curriculum.chapters || []).map(ch => {
      if (ch.id === targetChapter.id) {
        return {
          ...ch,
          problems: [...(ch.problems || []), newProblem]
        };
      }
      return ch;
    });

    let gIdx = 0;
    const updatedFlatProblems = [];
    const updatedProblemStates = { ...problemStates };
    let newProbGlobalIdx = 0;

    updatedChapters.forEach(ch => {
      ch.problems = (ch.problems || []).map(p => {
        const np = { ...p, chapter_id: ch.id, global_index: gIdx };
        if (ch.id === targetChapter.id && (p.title === newProblem.title || p.id === newProblem.id)) {
          newProbGlobalIdx = gIdx;
        }
        updatedFlatProblems.push(np);
        if (!updatedProblemStates[gIdx]) {
          updatedProblemStates[gIdx] = {
            slotChoice: null,
            assembledBlocks: [],
            availableBank: np.blocks_pool ? [...np.blocks_pool] : [],
            writtenCode: np.starter_code !== undefined ? np.starter_code : (np.type === 'code_blank' ? "" : "# Write code here\n"),
            evaluation: null,
            quizChoice: null
          };
        }
        gIdx++;
        return np;
      });
    });

    setCurriculum({
      ...curriculum,
      chapters: updatedChapters,
      problems: updatedFlatProblems
    });
    setProblemStates(updatedProblemStates);
    setActiveChapterId(targetChapter.id);
    setActiveProblemIndex(newProbGlobalIdx);
    setActiveTab("editor");

    setTerminalOutput(prev => [
      ...prev,
      `[TUTOR] 🎯 Tailored exercise ready: "${newProblem.title}" in ${targetChapter.title}.`
    ]);
  };

  // ---------------------------------------------------------------------------
  // 6. RESILIENT ANSWER VALIDATION & INTERACTION (ZERO UNANSWERED PROBLEMS)
  // ---------------------------------------------------------------------------
  const checkIsOptionCorrect = (selected, problem, optIndex) => {
    if (!selected || !problem) return false;
    const correct = (problem.correct_answer || problem.correctAnswer || problem.answer || problem.solution || "").trim();
    const sel = selected.trim();
    if (!correct) return false;

    // 1. Direct exact match
    if (sel === correct) return true;

    // 2. Case-insensitive match
    if (sel.toLowerCase() === correct.toLowerCase()) return true;

    // 3. Strip surrounding backticks, quotes, braces
    const clean = (s) => s.replace(/^[`'"]+|[`'"]+$/g, '').trim();
    if (clean(sel) === clean(correct)) return true;

    // 4. Strip prefix letters/numbers like "A) ", "1. ", "a: "
    const stripPrefix = (s) => s.replace(/^[A-Da-d0-9][\).\s:-]+/, '').trim();
    if (clean(stripPrefix(sel)) === clean(stripPrefix(correct))) return true;
    if (stripPrefix(sel) === correct || sel === stripPrefix(correct)) return true;

    // 5. If correct_answer is a letter ("A", "B", "C", "D") or digit ("0", "1", "2", "3")
    if (optIndex !== undefined && optIndex !== null) {
      const letter = String.fromCharCode(65 + optIndex);
      if (correct.toUpperCase() === letter || correct === String(optIndex)) return true;
    }

    return false;
  };

  const handleSelectSlotOption = (option, optIdx) => {
    if (!currentProblem) return;
    const isCorrect = checkIsOptionCorrect(option, currentProblem, optIdx);

    updateActiveState({
      slotChoice: option,
      evaluation: isCorrect ? 'correct' : 'wrong'
    });

    if (isCorrect) {
      const alreadySolved = completedProblems[activeProblemIndex];
      if (!alreadySolved) {
        setCompletedProblems(prev => ({ ...prev, [activeProblemIndex]: true }));
        setTotalXp(prev => prev + 25);
      }
      setTerminalOutput(prev => [
        ...prev,
        `----------------------------------------`,
        `[SLOT VERIFIED] Inserted '${option}' into space.`,
        ...(currentProblem.test_cases || ["[PASS] Identity satisfied."]),
        `[SUCCESS] 🎉 Correct solution! (+25 XP)`
      ]);

      // Mentor congratulates and reinforces learning
      setChatHistory(prev => [
        ...prev,
        {
          role: 'model',
          content: `🎉 **Excellent Work!** You correctly chose \`${option}\`.\n\n*Why it works*: ${currentProblem.explanation || "This choice satisfies the structural invariant perfectly."}\n\nNotice how understanding the underlying invariant made the choice clear! Ready for the next challenge?`
        }
      ]);
    } else {
      setTerminalOutput(prev => [
        ...prev,
        `[MISMATCH] Inserted '${option}'. Does not satisfy mathematical/logical invariant.`,
        `[HINT] ${currentProblem.concept_hint || "Review the step and re-evaluate."}`
      ]);

      // Mentor leads with guidance
      setChatHistory(prev => [
        ...prev,
        {
          role: 'model',
          content: `🤔 **Let's pause and review**: You selected \`${option}\`. Think about what happens when this expression executes or evaluates. Does it satisfy the boundary condition? *Hint*: ${currentProblem.concept_hint || "Re-check the invariant."}`
        }
      ]);
    }
  };

  const handleSelectQuizChoice = (option, optIdx) => {
    if (!currentProblem) return;
    const isCorrect = checkIsOptionCorrect(option, currentProblem, optIdx);

    updateActiveState({
      quizChoice: option,
      evaluation: isCorrect ? 'correct' : 'wrong'
    });

    const letter = String.fromCharCode(65 + (optIdx || 0));

    if (isCorrect) {
      const alreadySolved = completedProblems[activeProblemIndex];
      if (!alreadySolved) {
        setCompletedProblems(prev => ({ ...prev, [activeProblemIndex]: true }));
        setTotalXp(prev => prev + 25);
      }
      setTerminalOutput(prev => [
        ...prev,
        `----------------------------------------`,
        `[DIAGNOSTIC QUESTION] Selected (${letter}): "${option}"`,
        ...(currentProblem.test_cases || ["[PASS] Conceptual understanding verified."]),
        `[SUCCESS] 🎉 Correct answer! (+25 XP)`
      ]);

      setChatHistory(prev => [
        ...prev,
        {
          role: 'model',
          content: `🎉 **Correct!** Option (${letter}) \`${option}\` is accurate.\n\n*Pedagogical Insight*: ${currentProblem.explanation || "Your conceptual grasp of this principle is verified."}\n\nReady for the next exercise?`
        }
      ]);
    } else {
      setTerminalOutput(prev => [
        ...prev,
        `[MISMATCH] Option (${letter}) "${option}" is not the correct concept choice.`,
        `[HINT] ${currentProblem.concept_hint || "Review the theoretical principles in the chapter notes."}`
      ]);

      setChatHistory(prev => [
        ...prev,
        {
          role: 'model',
          content: `🤔 **Let's rethink this**: You picked (${letter}) \`${option}\`. Consider the underlying definition or edge cases: *${currentProblem.concept_hint || "What invariant or condition does this violate?"}*`
        }
      ]);
    }
  };

  const handleDragStart = (e, option) => {
    e.dataTransfer.setData("text/plain", option);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.getData("text/plain");
    if (dropped) handleSelectSlotOption(dropped, null);
  };

  // ---------------------------------------------------------------------------
  // 7. INTERACTION: BLOCK BUILDER (CODE INDENTATION & MATH DERIVATIONS)
  // ---------------------------------------------------------------------------
  const pushBlockToAssembly = (block, indexInBank) => {
    const currentAssembled = activeState.assembledBlocks || [];
    const currentBank = activeState.availableBank || [];

    const nextAssembled = [...currentAssembled, block];
    const nextBank = currentBank.filter((_, idx) => idx !== indexInBank);

    const corrBlocks = currentProblem.correct_blocks || currentProblem.correctBlocks || [];
    const normalizeLines = (lines) => lines.map(l => (l || "").trimEnd()).filter(Boolean).join("\n");
    const correctSeq = normalizeLines(corrBlocks);
    const userSeq = normalizeLines(nextAssembled);

    let evalStatus = null;
    if (correctSeq && userSeq === correctSeq) {
      evalStatus = 'correct';
      const alreadySolved = completedProblems[activeProblemIndex];
      if (!alreadySolved) {
        setCompletedProblems(prev => ({ ...prev, [activeProblemIndex]: true }));
        setTotalXp(prev => prev + 50);
      }
      setTerminalOutput(prev => [
        ...prev,
        `----------------------------------------`,
        `[STEP-BY-STEP VERIFIED]:`,
        ...nextAssembled,
        `[STATUS] 🎉 Sequence / Proof assembled perfectly! (+50 XP)`
      ]);

      setChatHistory(prev => [
        ...prev,
        {
          role: 'model',
          content: `🏆 **Derivation Complete!** You assembled the steps in exact logical sequence. Notice how each step logically follows from the previous one without skips!`
        }
      ]);
    } else if (corrBlocks.length > 0 && nextAssembled.length >= corrBlocks.length) {
      evalStatus = 'wrong';
      setTerminalOutput(prev => [
        ...prev,
        `[INCORRECT SEQUENCE] Derivation / block order is not valid.`,
        `[HINT] ${currentProblem.concept_hint || "Check prerequisite steps and logical progression."}`
      ]);
    }

    updateActiveState({
      assembledBlocks: nextAssembled,
      availableBank: nextBank,
      evaluation: evalStatus
    });
  };

  const removeBlockFromAssembly = (indexInAssembly) => {
    const currentAssembled = activeState.assembledBlocks || [];
    const currentBank = activeState.availableBank || [];

    const removedBlock = currentAssembled[indexInAssembly];
    const nextAssembled = currentAssembled.filter((_, idx) => idx !== indexInAssembly);
    const nextBank = [...currentBank, removedBlock];

    updateActiveState({
      assembledBlocks: nextAssembled,
      availableBank: nextBank,
      evaluation: null
    });
  };

  // ---------------------------------------------------------------------------
  // 8. REAL PYODIDE KERNEL RUNNER (FRONT-END IN-BROWSER EXECUTION)
  // ---------------------------------------------------------------------------
  const handleRunInPyodideKernel = async (testMode = false) => {
    const code = activeState.writtenCode || currentProblem?.starter_code || "";
    const testCode = testMode ? (currentProblem?.test_code || "") : "";

    setExecutingCode(true);
    setTerminalOutput(prev => [
      ...prev,
      `[KERNEL EXECUTE] Running in Client-Side WebAssembly Python 3.12 Kernel...`
    ]);

    if (pyodideRef.current && kernelStatus === "ready") {
      try {
        pyodideRef.current.runPython(`
import sys
import io
_sys_out = sys.stdout
_sys_err = sys.stderr
sys.stdout = io.StringIO()
sys.stderr = io.StringIO()
`);
        pyodideRef.current.runPython(code);

        let testsPassed = true;
        if (testCode) {
          try {
            pyodideRef.current.runPython(testCode);
            pyodideRef.current.runPython('print("\\n[TEST_REPORT] All assertions passed in WebAssembly kernel!")');
          } catch (assertErr) {
            testsPassed = false;
            pyodideRef.current.runPython(`print("\\n[ASSERTION_ERROR] ${assertErr.message}")`);
          }
        }

        const stdout = pyodideRef.current.runPython("sys.stdout.getvalue()");
        const stderr = pyodideRef.current.runPython("sys.stderr.getvalue()");
        pyodideRef.current.runPython(`
sys.stdout = _sys_out
sys.stderr = _sys_err
`);

        if (testsPassed && testMode) {
          const alreadySolved = completedProblems[activeProblemIndex];
          if (!alreadySolved) {
            setCompletedProblems(prev => ({ ...prev, [activeProblemIndex]: true }));
            setTotalXp(prev => prev + 100);
          }
          updateActiveState({ evaluation: 'correct' });
        }

        setTerminalOutput(prev => [
          ...prev,
          stdout ? `[STDOUT]\n${stdout.trim()}` : "[STDOUT] (No output printed)",
          stderr ? `[STDERR]\n${stderr.trim()}` : "",
          testMode 
            ? (testsPassed ? "[TEST REPORT] ✅ Verified in WebAssembly Kernel! (+100 XP)" : "[TEST REPORT] ❌ Test assertion failed.") 
            : "[STATUS] Execution finished with exit code 0."
        ]);
      } catch (runErr) {
        setTerminalOutput(prev => [
          ...prev,
          `[KERNEL RUNTIME ERROR]\n${runErr.message}`
        ]);
      } finally {
        setExecutingCode(false);
      }
    } else {
      try {
        let res;
        const execBody = JSON.stringify({ code, test_code: testCode });
        try {
          res = await fetch("http://127.0.0.1:8000/api/execute-code", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: execBody
          });
        } catch (e1) {
          res = await fetch("http://localhost:8000/api/execute-code", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: execBody
          });
        }
        const data = await res.json();

        if (data.tests_passed && testMode) {
          const alreadySolved = completedProblems[activeProblemIndex];
          if (!alreadySolved) {
            setCompletedProblems(prev => ({ ...prev, [activeProblemIndex]: true }));
            setTotalXp(prev => prev + 100);
          }
          updateActiveState({ evaluation: 'correct' });
        }

        setTerminalOutput(prev => [
          ...prev,
          data.stdout ? `[STDOUT]\n${data.stdout.trim()}` : "[STDOUT] (No output printed)",
          data.stderr ? `[STDERR]\n${data.stderr.trim()}` : "",
          testMode 
            ? (data.tests_passed ? "[TEST REPORT] ✅ Verified! All assertions passed! (+100 XP)" : "[TEST REPORT] ❌ Test assertion failed.") 
            : "[STATUS] Execution finished."
        ]);
      } catch (err) {
        setTerminalOutput(prev => [...prev, `[ERROR] Execution failed: ${err.message}`]);
      } finally {
        setExecutingCode(false);
      }
    }
  };

  // ---------------------------------------------------------------------------
  // 9. SOKRATIC CHAT HANDLER
  // ---------------------------------------------------------------------------
  const sendMentorQuery = async (queryText) => {
    if (!queryText.trim() || chatLoading) return;
    const msg = queryText.trim();
    setUserInput("");

    // Trigger dynamic problem generation if user clicked blank task or partial scaffold pills
    if (msg.toLowerCase().includes("blank coding") || msg.toLowerCase().includes("blank task") || msg.toLowerCase().includes("blank challenge")) {
      handleGenerateProblem(currentChapter?.id || 1, 'code_blank');
    } else if (msg.toLowerCase().includes("partially coded") || msg.toLowerCase().includes("partial scaffold")) {
      handleGenerateProblem(currentChapter?.id || 1, 'code_partial');
    }

    setChatLoading(true);

    const cleanMsg = msg.trim();
    const newHistory = [...chatHistory, { role: 'user', content: cleanMsg }];
    setChatHistory(newHistory);

    try {
      let res;
      const chatBody = JSON.stringify({
        message: cleanMsg,
        history: newHistory.map(m => ({
          role: m.role || 'user',
          content: m.content || ''
        })),
        puzzle_context: {
          problem: currentProblem,
          chapter: currentChapter,
          mode: appMode,
          level: currentLevel,
          total_solved: Object.keys(completedProblems).length
        }
      });

      try {
        res = await fetch("http://127.0.0.1:8000/api/tutor-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: chatBody
        });
      } catch (e1) {
        res = await fetch("http://localhost:8000/api/tutor-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: chatBody
        });
      }

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const errDetail = errorData.detail 
          ? (typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail))
          : `HTTP ${res.status}`;
        throw new Error(errDetail);
      }

      const data = await res.json();
      setChatHistory(prev => [
        ...prev,
        { role: 'model', content: data.reply || "I am analyzing your reasoning..." }
      ]);

      if (data.mutated_puzzle) {
        injectProblemIntoCurriculum(data.mutated_puzzle);
      }
    } catch (err) {
      setChatHistory(prev => [
        ...prev,
        { role: 'model', content: `Mentor note: ${err.message}` }
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleSendMessage = (e) => {
    e?.preventDefault();
    sendMentorQuery(userInput);
  };

  // ---------------------------------------------------------------------------
  // RENDER CANVAS: MATH EQUATIONS vs CODE LINES
  // ---------------------------------------------------------------------------
  const renderInteractiveCanvas = () => {
    const isMath = (currentProblem?.mode === 'math' || appMode === 'math');
    const slotChoice = activeState.slotChoice;
    const evalStatus = activeState.evaluation;

    // --- A. MATH MODE PLUG-IN ---
    if (isMath && (currentProblem?.type === 'slot_plugin' || currentProblem?.type === 'logic_problem')) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, backgroundColor: 'transparent' }}>
          <div style={{ 
            flex: 1, 
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center', 
            justifyContent: 'center', 
            padding: '30px', 
            gap: '24px' 
          }}>
            <div style={{ 
              backgroundColor: theme.bgCard, 
              border: `2px solid ${evalStatus === 'correct' ? theme.accentGreen : evalStatus === 'wrong' ? theme.accentPink : theme.borderContrast}`, 
              borderRadius: '8px', 
              padding: '24px 32px',
              display: 'flex',
              alignItems: 'center',
              gap: '14px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)'
            }}>
              <MathFormula math={currentProblem.code_prefix} inline={true} />

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                style={{
                  minWidth: '130px',
                  minHeight: '44px',
                  padding: '4px 16px',
                  backgroundColor: slotChoice ? (evalStatus === 'correct' ? '#103522' : '#381519') : theme.bgInput,
                  border: `2px dashed ${evalStatus === 'correct' ? theme.accentGreen : evalStatus === 'wrong' ? theme.accentPink : theme.accentBlue}`,
                  borderRadius: '6px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '18px',
                  fontWeight: 600,
                  color: slotChoice ? theme.textMain : theme.accentBlue,
                  transition: 'all 0.15s ease'
                }}
              >
                {slotChoice ? <MathFormula math={slotChoice} inline={true} /> : "⬚ drop or select term"}
              </div>

              {currentProblem.code_suffix && (
                <MathFormula math={currentProblem.code_suffix} inline={true} />
              )}
            </div>

            <div style={{ fontSize: '11px', color: theme.textMuted }}>
              Click or drag a candidate mathematical term from the palette below into the equation slot.
            </div>
          </div>

          <div style={{ 
            borderTop: `1px solid ${theme.borderContrast}`, 
            backgroundColor: theme.bgPanel, 
            padding: '14px 20px', 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '10px' 
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: theme.accentYellow, textTransform: 'uppercase' }}>
                Mathematical Terms Palette (LaTeX Notation)
              </span>
              {slotChoice && (
                <button 
                  onClick={() => updateActiveState({ slotChoice: null, evaluation: null })}
                  style={{ background: 'none', border: 'none', color: theme.textMuted, cursor: 'pointer', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <RotateCcw size={11} /> Clear Slot
                </button>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px' }}>
              {(currentProblem.options || []).map((opt, idx) => {
                const isSelected = slotChoice === opt;
                return (
                  <div
                    key={idx}
                    draggable
                    onDragStart={(e) => handleDragStart(e, opt)}
                    onClick={() => handleSelectSlotOption(opt, idx)}
                    style={{
                      padding: '10px 14px',
                      backgroundColor: isSelected ? theme.bgHighlight : theme.bgCard,
                      border: isSelected ? `1px solid ${theme.accentGreen}` : `1px solid ${theme.border}`,
                      borderRadius: '4px',
                      cursor: 'grab',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      color: theme.textMain
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ color: theme.accentPink, fontSize: '11px', fontWeight: 700 }}>
                        {String.fromCharCode(65 + idx)}.
                      </span>
                      <MathFormula math={opt} inline={true} />
                    </div>
                    <span style={{ fontSize: '10px', color: theme.textMuted }}>⠿</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      );
    }

    // --- B. MATH MODE PROOF / DERIVATION ASSEMBLY ---
    if (isMath && currentProblem?.type === 'block_builder') {
      const assembled = activeState.assembledBlocks || [];
      const available = activeState.availableBank || [];

      return (
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, backgroundColor: 'transparent' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '11px', color: theme.textMuted, marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              MATHEMATICAL DERIVATION STEPS (Tap steps below to construct derivation from premise to Q.E.D.):
            </div>

            {assembled.length === 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '160px', color: theme.textMuted, border: `1px dashed ${theme.borderContrast}`, borderRadius: '6px' }}>
                Tap derivation steps from the palette below to arrange proof...
              </div>
            ) : (
              assembled.map((step, idx) => (
                <div
                  key={idx}
                  onClick={() => removeBlockFromAssembly(idx)}
                  title="Click step to remove"
                  style={{
                    padding: '10px 16px',
                    backgroundColor: theme.bgCard,
                    border: `1px solid ${theme.border}`,
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ color: theme.accentBlue, fontSize: '11px', fontWeight: 700 }}>Step {idx + 1}</span>
                    <MathFormula math={step} inline={true} />
                  </div>
                  <span style={{ fontSize: '11px', color: theme.textMuted }}>✕ remove</span>
                </div>
              ))
            )}
          </div>

          <div style={{ borderTop: `1px solid ${theme.borderContrast}`, backgroundColor: theme.bgPanel, padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: theme.textMain, textTransform: 'uppercase' }}>
              Scrambled Derivation Steps (Tap to Insert)
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {available.map((step, idx) => (
                <div
                  key={idx}
                  onClick={() => pushBlockToAssembly(step, idx)}
                  style={{
                    backgroundColor: theme.bgCard,
                    border: `1px solid ${theme.borderContrast}`,
                    padding: '8px 14px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <Plus size={12} color={theme.accentBlue} />
                  <MathFormula math={step} inline={true} />
                </div>
              ))}
            </div>
          </div>
        </div>
      );
    }

    // --- C. CODE MODE PLUG-IN CANVAS ---
    if (!isMath && (currentProblem?.type === 'slot_plugin' || currentProblem?.type === 'syntax_problem' || currentProblem?.type === 'logic_problem')) {
      const prefixLines = (currentProblem.code_prefix || "").split("\n");
      const suffixLines = (currentProblem.code_suffix || "").split("\n");
      const lineWithPrefix = prefixLines[prefixLines.length - 1];
      const lineWithSuffix = suffixLines[0];
      const precedingLines = prefixLines.slice(0, prefixLines.length - 1);
      const succeedingLines = suffixLines.slice(1);
      let lineNum = 1;

      return (
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, backgroundColor: 'transparent' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px 0', fontFamily: theme.fontMono }}>
            {precedingLines.map((l, i) => (
              <HighlightedLine key={`pre-${i}`} code={l} lineNum={lineNum++} />
            ))}

            <div style={{ display: 'flex', alignItems: 'center', minHeight: '28px', backgroundColor: theme.bgHighlight, fontSize: '13px' }}>
              <span style={{ width: '42px', textAlign: 'right', paddingRight: '16px', color: theme.textMuted, userSelect: 'none', flexShrink: 0, fontFamily: theme.fontMono, fontSize: '12px' }}>
                {lineNum++}
              </span>

              <span style={{ whiteSpace: 'pre', color: theme.accentBlue, fontFamily: theme.fontMono }}>{lineWithPrefix}</span>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minWidth: '120px',
                  height: '24px',
                  padding: '0 10px',
                  margin: '0 6px',
                  backgroundColor: slotChoice ? (evalStatus === 'correct' ? '#103522' : '#381519') : theme.bgCard,
                  border: `1.5px ${slotChoice ? 'solid' : 'dashed'} ${evalStatus === 'correct' ? theme.accentGreen : evalStatus === 'wrong' ? theme.accentPink : theme.accentBlue}`,
                  borderRadius: '3px',
                  color: slotChoice ? theme.textMain : theme.accentBlue,
                  fontWeight: 600,
                  fontSize: '13px',
                  cursor: 'pointer'
                }}
              >
                {slotChoice ? slotChoice : "⬚ drop or click variant"}
              </div>

              <span style={{ whiteSpace: 'pre', color: theme.accentBlue, fontFamily: theme.fontMono }}>{lineWithSuffix}</span>
            </div>

            {succeedingLines.map((l, i) => (
              <HighlightedLine key={`post-${i}`} code={l} lineNum={lineNum++} />
            ))}
          </div>

          <div style={{ borderTop: `1px solid ${theme.borderContrast}`, backgroundColor: theme.bgPanel, padding: '12px 18px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: theme.textMain, textTransform: 'uppercase' }}>
                Code Options Palette (Drag or Click to Slot)
              </span>
              {slotChoice && (
                <button 
                  onClick={() => updateActiveState({ slotChoice: null, evaluation: null })}
                  style={{ background: 'none', border: 'none', color: theme.textMuted, cursor: 'pointer', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <RotateCcw size={11} /> Reset Slot
                </button>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '8px' }}>
              {(currentProblem.options || []).map((opt, idx) => {
                const isChosen = slotChoice === opt;
                return (
                  <div
                    key={idx}
                    draggable
                    onDragStart={(e) => handleDragStart(e, opt)}
                    onClick={() => handleSelectSlotOption(opt, idx)}
                    style={{
                      padding: '8px 12px',
                      backgroundColor: isChosen ? theme.bgHighlight : theme.bgCard,
                      border: isChosen ? `1px solid ${theme.accentGreen}` : `1px solid ${theme.borderContrast}`,
                      borderRadius: '4px',
                      cursor: 'grab',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontFamily: theme.fontMono,
                      fontSize: '12px',
                      color: isChosen ? theme.accentGreen : theme.textMain
                    }}
                  >
                    <span>{opt}</span>
                    <span style={{ fontSize: '10px', color: theme.textMuted }}>⠿</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      );
    }

    // --- D. CODE MODE BLOCK BUILDER (REAL INDENTATION) ---
    if (!isMath && currentProblem?.type === 'block_builder') {
      const assembled = activeState.assembledBlocks || [];
      const available = activeState.availableBank || [];

      return (
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, backgroundColor: 'transparent' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px 0', fontFamily: theme.fontMono }}>
            {assembled.length === 0 ? (
              <div style={{ padding: '20px', color: theme.textMuted, fontSize: '12px' }}>
                # Tap code blocks from the bank below to insert indented lines...
              </div>
            ) : (
              assembled.map((line, idx) => (
                <div key={idx} onClick={() => removeBlockFromAssembly(idx)} style={{ cursor: 'pointer' }}>
                  <HighlightedLine code={line} lineNum={idx + 1} />
                </div>
              ))
            )}
          </div>

          <div style={{ borderTop: `1px solid ${theme.borderContrast}`, backgroundColor: theme.bgPanel, padding: '12px 18px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: theme.textMain, textTransform: 'uppercase' }}>
              Scrambled Code Bank (Tap to Insert With Indentation)
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {available.map((b, idx) => (
                <div
                  key={idx}
                  onClick={() => pushBlockToAssembly(b, idx)}
                  style={{
                    backgroundColor: theme.bgCard,
                    border: `1px solid ${theme.borderContrast}`,
                    padding: '6px 12px',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontFamily: theme.fontMono,
                    fontSize: '12px',
                    color: theme.accentBlue
                  }}
                >
                  <Plus size={11} style={{ display: 'inline', marginRight: '6px' }} color={theme.accentGreen} />
                  <span style={{ whiteSpace: 'pre' }}>{b}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      );
    }

    // --- E. CONCEPTUAL QUIZ QUESTIONS ---
    if (currentProblem?.type === 'question') {
      const choice = activeState.quizChoice;
      const evalStatus = activeState.evaluation;

      return (
        <div style={{ flex: 1, padding: '24px', backgroundColor: 'transparent', overflowY: 'auto' }}>
          <div style={{ maxWidth: '700px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ backgroundColor: theme.bgCard, border: `1px solid ${theme.borderContrast}`, padding: '16px', borderRadius: '4px' }}>
              <div style={{ fontSize: '11px', color: theme.accentBlue, fontWeight: 700, marginBottom: '6px' }}>
                DIAGNOSTIC QUESTION #{activeProblemIndex + 1}
              </div>
              <div style={{ fontSize: '14px', color: theme.textMain }}>
                {isMath ? <MathFormula math={currentProblem.question_text || currentProblem.guiding_question} /> : (currentProblem.question_text || currentProblem.guiding_question)}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {(currentProblem.options || []).map((opt, idx) => {
                const isSelected = choice === opt;
                return (
                  <div
                    key={idx}
                    onClick={() => handleSelectQuizChoice(opt, idx)}
                    style={{
                      padding: '12px 16px',
                      backgroundColor: isSelected ? theme.bgHighlight : theme.bgCard,
                      border: isSelected ? `1px solid ${theme.accentGreen}` : `1px solid ${theme.border}`,
                      borderRadius: '4px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      color: theme.textMain
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ color: theme.accentPink, fontWeight: 700 }}>{String.fromCharCode(65 + idx)}.</span>
                      {isMath ? <MathFormula math={opt} inline={true} /> : <span>{opt}</span>}
                    </div>
                    {isSelected && evalStatus === 'correct' && <CheckCircle2 size={16} color={theme.accentGreen} />}
                    {isSelected && evalStatus === 'wrong' && <AlertTriangle size={16} color={theme.accentPink} />}
                  </div>
                );
              })}
            </div>

            {choice && (
              <div style={{ backgroundColor: evalStatus === 'correct' ? '#103522' : '#381519', padding: '12px', borderRadius: '4px', border: `1px solid ${evalStatus === 'correct' ? theme.accentGreen : theme.accentPink}` }}>
                <div style={{ fontWeight: 700, color: theme.textMain, marginBottom: '4px' }}>
                  {evalStatus === 'correct' ? 'Verified!' : 'Incorrect'}
                </div>
                <div style={{ fontSize: '12px', color: theme.textDim }}>{currentProblem.explanation}</div>
              </div>
            )}
          </div>
        </div>
      );
    }

    // --- F. FREEFORM CODING (WASM KERNEL EXECUTION) ---
    const isBlankTask = currentProblem?.type === 'code_blank';
    const isPartialTask = currentProblem?.type === 'code_partial';
    const starterDefault = currentProblem?.starter_code !== undefined ? currentProblem.starter_code : (isBlankTask ? "" : "# Implement solution below\n\n");
    const currentCode = activeState.writtenCode !== undefined ? activeState.writtenCode : starterDefault;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, backgroundColor: 'transparent', position: 'relative', zIndex: 1 }}>
        {/* Task Header Banner */}
        <div style={{ 
          padding: '8px 16px', 
          backgroundColor: theme.bgHeader, 
          borderBottom: `1px solid ${theme.borderContrast}`,
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {isBlankTask ? (
              <span style={{ backgroundColor: theme.bgCardAlt, color: theme.accentGold, padding: '3px 8px', borderRadius: '3px', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Zap size={12} color={theme.accentGold} />
                HARD CHALLENGE: BLANK SCRATCHPAD
              </span>
            ) : isPartialTask ? (
              <span style={{ backgroundColor: theme.bgCardAlt, color: theme.accentGreen, padding: '3px 8px', borderRadius: '3px', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Code2 size={12} color={theme.accentGreen} />
                PARTIALLY CODED SCAFFOLD
              </span>
            ) : (
              <span style={{ backgroundColor: theme.bgCardAlt, color: theme.accentBlue, padding: '3px 8px', borderRadius: '3px', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Terminal size={12} color={theme.accentBlue} />
                FREEFORM CODING IDE
              </span>
            )}
            <span style={{ fontSize: '11px', color: theme.textMuted }}>
              {currentProblem?.guiding_question || "Write and verify your algorithmic implementation below."}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button
              onClick={() => updateActiveState({ writtenCode: "" })}
              title="Clear editor to blank space"
              style={{
                backgroundColor: theme.bgCard,
                border: `1px solid ${theme.borderContrast}`,
                color: theme.accentGold,
                padding: '3px 8px',
                borderRadius: '3px',
                fontSize: '10px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <RotateCcw size={10} /> Blank Canvas
            </button>
            <button
              onClick={() => updateActiveState({ writtenCode: currentProblem?.starter_code || "" })}
              title="Reset code to original starter template"
              style={{
                backgroundColor: theme.bgCard,
                border: `1px solid ${theme.borderContrast}`,
                color: theme.textDim,
                padding: '3px 8px',
                borderRadius: '3px',
                fontSize: '10px',
                cursor: 'pointer'
              }}
            >
              Reset Starter
            </button>
          </div>
        </div>

        <textarea
          value={currentCode}
          onChange={(e) => updateActiveState({ writtenCode: e.target.value })}
          placeholder={isBlankTask ? "# Blank Scratchpad: Write your complete code, functions, classes, and loops from scratch..." : "# Enter code here..."}
          spellCheck={false}
          style={{
            flex: 1,
            backgroundColor: 'transparent',
            color: theme.textMain,
            border: 'none',
            outline: 'none',
            padding: '16px',
            fontFamily: theme.fontMono,
            fontSize: '13px',
            lineHeight: '22px',
            resize: 'none'
          }}
        />

        {currentProblem?.test_cases && currentProblem.test_cases.length > 0 && (
          <div style={{ backgroundColor: theme.bgCard, borderTop: `1px solid ${theme.borderContrast}`, padding: '6px 16px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: theme.accentBlue }}>
            <CheckCircle2 size={12} color={theme.accentGreen} />
            <span style={{ fontWeight: 700, color: theme.textMain }}>Target Assertions:</span>
            <span style={{ color: theme.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {currentProblem.test_cases.slice(0, 3).join(" • ")}
            </span>
          </div>
        )}

        <div style={{ borderTop: `1px solid ${theme.borderContrast}`, backgroundColor: theme.bgPanel, padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: '11px', color: theme.accentBlue, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Zap size={12} color={theme.accentGold} />
            <span>WebAssembly Kernel: {kernelStatus === 'ready' ? '⚡ Python 3.12 Ready' : 'Connecting...'}</span>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => handleRunInPyodideKernel(false)}
              disabled={executingCode}
              style={{ backgroundColor: theme.bgCard, color: theme.textMain, border: `1px solid ${theme.borderContrast}`, padding: '6px 12px', borderRadius: '3px', cursor: 'pointer', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Play size={12} color={theme.accentGreen} /> Run Code (Wasm)
            </button>
            <button
              onClick={() => handleRunInPyodideKernel(true)}
              disabled={executingCode}
              style={{ backgroundColor: theme.accentGreen, color: '#ffffff', border: 'none', padding: '6px 14px', borderRadius: '3px', cursor: 'pointer', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Check size={12} /> Run Test Suite
            </button>
          </div>
        </div>
      </div>
    );
  };

  // ---------------------------------------------------------------------------
  // LAYOUT RENDER (HIGH-CONTRAST 3-PANEL ALIGNMENT)
  // ---------------------------------------------------------------------------
  return (
    <div style={{ 
      display: 'flex', 
      height: '100vh', 
      width: '100vw', 
      backgroundColor: theme.bgApp, 
      color: theme.textMain, 
      overflow: 'hidden',
      userSelect: isDragging ? 'none' : 'auto',
      cursor: isDragging === 'left' || isDragging === 'right' ? 'col-resize' : isDragging === 'terminal' ? 'row-resize' : 'default'
    }}>
      
      {/* 1. LEFT PANEL: INGESTION, MODE SWITCHER, CHAPTER TREE (RESIZABLE) */}
      <aside style={{ 
        width: `${leftWidth}px`, 
        minWidth: '160px',
        maxWidth: '650px',
        flexShrink: 0,
        backgroundColor: theme.bgSidebar, 
        display: 'flex', 
        flexDirection: 'column', 
        padding: '14px', 
        overflowY: 'auto',
        gap: '12px'
      }}>
        {/* Brand & Mode Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${theme.border}`, paddingBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: theme.accentGreen }} />
            <span style={{ fontWeight: 700, fontSize: '12px', color: theme.textMain }}>&edu Studio</span>
            <span style={{ fontSize: '9px', backgroundColor: theme.bgCardAlt, color: theme.accentGold, padding: '1px 5px', borderRadius: '3px', fontWeight: 600 }}>William & Mary</span>
          </div>

          <div style={{ display: 'flex', backgroundColor: theme.bgInput, border: `1px solid ${theme.border}`, borderRadius: '4px', padding: '2px' }}>
            <button
              onClick={() => handleModeChange('code')}
              style={{
                backgroundColor: appMode === 'code' ? theme.accentGreen : 'transparent',
                color: appMode === 'code' ? '#ffffff' : theme.textDim,
                border: 'none',
                padding: '3px 8px',
                borderRadius: '3px',
                fontSize: '11px',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              ⚡ Code
            </button>
            <button
              onClick={() => handleModeChange('math')}
              style={{
                backgroundColor: appMode === 'math' ? theme.accentGreen : 'transparent',
                color: appMode === 'math' ? '#ffffff' : theme.textDim,
                border: 'none',
                padding: '3px 8px',
                borderRadius: '3px',
                fontSize: '11px',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              ∑ Math
            </button>
          </div>
        </div>

        {/* Multi-File Upload Input (Few or Any Amount) */}
        <div>
          <label style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            gap: '8px', 
            padding: '10px', 
            backgroundColor: theme.bgCard, 
            border: `1px dashed ${theme.accentBlue}`, 
            borderRadius: '4px', 
            cursor: 'pointer', 
            fontSize: '11px', 
            color: theme.accentBlue 
          }}>
            <Upload size={13} />
            <span>Upload Few or Any Files</span>
            <input 
              type="file" 
              multiple 
              accept=".pdf,.docx,.ipynb,.txt,.md,.py,.png,.jpg,.jpeg,.webp" 
              onChange={handleMultiFileUpload} 
              style={{ display: 'none' }} 
            />
          </label>

          {uploadedFiles.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '8px' }}>
              {uploadedFiles.map((f, i) => (
                <div key={i} style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'space-between', 
                  backgroundColor: theme.bgCardAlt, 
                  border: `1px solid ${theme.border}`, 
                  padding: '4px 8px', 
                  borderRadius: '3px', 
                  fontSize: '11px',
                  color: theme.textMain
                }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '200px' }}>
                    {f.name}
                  </span>
                  <X size={12} color={theme.accentPink} style={{ cursor: 'pointer' }} onClick={() => removeUploadedFile(i)} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Topic Input */}
        <div>
          <div style={{ fontSize: '10px', fontWeight: 700, color: theme.textDim, textTransform: 'uppercase', marginBottom: '4px' }}>
            {appMode === 'math' ? 'Target Math Field' : 'Target Programming Topic'}
          </div>
          <textarea
            value={topicInput}
            onChange={(e) => setTopicInput(e.target.value)}
            rows={2}
            placeholder={appMode === 'math' ? "Calculus, Derivatives, Matrix algebra..." : "Python, C++, Rust, Algorithms..."}
            style={{ 
              width: '100%', 
              backgroundColor: theme.bgInput, 
              color: theme.textMain, 
              border: `1px solid ${theme.borderContrast}`, 
              padding: '8px', 
              borderRadius: '4px', 
              fontSize: '11px', 
              fontFamily: theme.fontMono, 
              resize: 'none', 
              boxSizing: 'border-box' 
            }}
          />
        </div>

        {/* Desired Curriculum Scale / Chapter Count */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '10px', color: theme.textMuted, margin: '2px 0 4px 0' }}>
          <span>Course Scale:</span>
          <div style={{ display: 'flex', gap: '3px' }}>
            {['auto', 3, 4, 5].map((cnt) => (
              <button
                key={cnt}
                onClick={() => setTargetChapterCount(cnt)}
                style={{
                  backgroundColor: targetChapterCount === cnt ? theme.accentGreen : theme.bgCard,
                  color: targetChapterCount === cnt ? '#ffffff' : theme.textDim,
                  border: `1px solid ${targetChapterCount === cnt ? theme.accentGreen : theme.border}`,
                  borderRadius: '2px',
                  padding: '2px 6px',
                  fontSize: '9px',
                  fontWeight: targetChapterCount === cnt ? 700 : 400,
                  cursor: 'pointer'
                }}
              >
                {cnt === 'auto' ? 'Auto' : `${cnt} Ch`}
              </button>
            ))}
          </div>
        </div>

        {/* Generate / Level Up Controls */}
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            onClick={handleGenerate}
            disabled={loading}
            style={{ 
              flex: 1, 
              backgroundColor: theme.accentGreen, 
              color: '#ffffff', 
              border: 'none', 
              padding: '8px', 
              borderRadius: '4px', 
              fontSize: '11px', 
              fontWeight: 700, 
              cursor: 'pointer', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              gap: '6px' 
            }}
          >
            {loading ? <Loader2 size={12} className="animate-spin" color="#ffffff" /> : <Play size={12} color="#ffffff" />}
            Synthesize AI Curriculum
          </button>
          <button
            onClick={handleMakeHarder}
            disabled={escalating}
            title="Escalate Tier (Level Up)"
            style={{ 
              backgroundColor: theme.bgCard, 
              border: `1px solid ${theme.border}`, 
              color: theme.textMain, 
              padding: '8px 12px', 
              borderRadius: '4px', 
              cursor: 'pointer' 
            }}
          >
            {escalating ? <Loader2 size={12} className="animate-spin" /> : <Flame size={12} color={theme.accentOrange} />}
          </button>
        </div>

        {/* Elderly Male Professor Audio Lecture (ElevenLabs Neural Voice) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', backgroundColor: theme.bgCard, border: `1px solid ${theme.borderContrast}`, borderRadius: '5px', padding: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: theme.accentGreen, display: 'flex', alignItems: 'center', gap: '5px' }}>
              <GraduationCap size={14} color={theme.accentGreen} />
              <span>Professor Audio Lecture</span>
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <select
                value={selectedVoice}
                onChange={(e) => setSelectedVoice(e.target.value)}
                title="Select Professor Voice (ElevenLabs)"
                style={{
                  backgroundColor: theme.bgInput,
                  color: theme.textMain,
                  border: `1px solid ${theme.border}`,
                  borderRadius: '3px',
                  fontSize: '9px',
                  padding: '2px 4px',
                  cursor: 'pointer',
                  outline: 'none',
                  maxWidth: '120px'
                }}
              >
                <option value="JBFqnCBsd6RMkjVDRZzb">Prof. George (British)</option>
                <option value="VR6AewLTigWG4xSOukaG">Prof. Arnold (American)</option>
                <option value="onwK4e9ZLuTAKqWW03F9">Prof. Daniel (Broadcaster)</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <button
              onClick={handleGenerateVoiceover}
              disabled={voiceoverLoading}
              title="Listen to conversational audio lecture by elderly male professor"
              style={{
                flex: 1,
                backgroundColor: voiceoverPlaying ? '#17482d' : theme.accentGreen,
                color: voiceoverPlaying ? theme.accentGreen : '#ffffff',
                border: `1px solid ${voiceoverPlaying ? theme.accentGreen : 'transparent'}`,
                padding: '8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                transition: 'all 0.15s ease'
              }}
            >
              {voiceoverLoading ? (
                <Loader2 size={13} className="animate-spin" color={voiceoverPlaying ? theme.accentGreen : '#ffffff'} />
              ) : voiceoverPlaying ? (
                <Volume2 size={13} color={theme.accentGreen} className="animate-pulse" />
              ) : (
                <Mic size={13} color="#ffffff" />
              )}
              <span>{voiceoverLoading ? 'Synthesizing Audio...' : voiceoverPlaying ? 'Professor Speaking...' : '🎙️ Listen to Lecture'}</span>
            </button>

            {voiceoverPlaying && (
              <button
                onClick={handleStopVoiceover}
                title="Stop voiceover lecture"
                style={{
                  backgroundColor: '#4a2128',
                  border: `1px solid ${theme.accentPink}`,
                  color: theme.accentPink,
                  padding: '8px 10px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <Square size={11} color={theme.accentPink} />
              </button>
            )}

            {voiceoverScript && (
              <button
                onClick={() => setShowTranscript(prev => !prev)}
                title="Toggle spoken lecture transcript"
                style={{
                  backgroundColor: showTranscript ? theme.bgHighlight : theme.bgCardAlt,
                  border: `1px solid ${theme.border}`,
                  color: showTranscript ? theme.textMain : theme.textDim,
                  padding: '8px 9px',
                  borderRadius: '4px',
                  fontSize: '10px',
                  cursor: 'pointer'
                }}
              >
                <FileText size={12} />
              </button>
            )}
          </div>

          {/* ElevenLabs Error & Fallback Banner */}
          {voiceoverError && (
            <div style={{
              backgroundColor: '#4a2128',
              border: `1px solid ${theme.accentPink}`,
              borderRadius: '4px',
              padding: '6px 8px',
              fontSize: '10px',
              color: '#f8f8f2',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div style={{ color: theme.accentPink, fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <AlertTriangle size={11} /> ElevenLabs Connection Notice:
              </div>
              <div style={{ fontSize: '9px', color: '#ffb3ba' }}>{voiceoverError}</div>
              <button
                onClick={handlePlayBrowserFallbackSpeech}
                style={{
                  alignSelf: 'flex-start',
                  backgroundColor: theme.bgCardAlt,
                  border: `1px solid ${theme.accentOrange}`,
                  color: theme.accentOrange,
                  borderRadius: '3px',
                  padding: '3px 7px',
                  fontSize: '9px',
                  cursor: 'pointer',
                  marginTop: '2px'
                }}
              >
                🤖 Play Offline Browser Speech Fallback
              </button>
            </div>
          )}

          {/* Collapsible Professor Transcript Drawer */}
          {showTranscript && voiceoverScript && (
            <div style={{
              backgroundColor: theme.bgPanel,
              border: `1px solid ${theme.border}`,
              borderRadius: '4px',
              padding: '8px 10px',
              fontSize: '10px',
              lineHeight: '1.5',
              color: theme.textDim,
              maxHeight: '120px',
              overflowY: 'auto',
              fontStyle: 'italic'
            }}>
              <div style={{ fontSize: '9px', fontWeight: 700, color: theme.accentBlue, marginBottom: '3px', fontStyle: 'normal' }}>
                👨‍🏫 PROFESSOR'S SPOKEN LECTURE TRANSCRIPT:
              </div>
              "{voiceoverScript}"
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '9px', color: theme.textMuted }}>
            <span>Engine: ElevenLabs Neural TTS</span>
            {voiceoverSource && (
              <span style={{ 
                color: voiceoverSource === 'elevenlabs' ? theme.accentGreen : voiceoverSource === 'browser' ? theme.accentOrange : theme.accentPink, 
                fontWeight: 600 
              }}>
                {voiceoverSource === 'elevenlabs' ? '● ElevenLabs Neural' : voiceoverSource === 'browser' ? '● Browser Speech Engine' : '● ElevenLabs Error'}
              </span>
            )}
          </div>
        </div>

        {/* Chapters & Problem Explorer with Dynamic Chapter Generation */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontSize: '10px', fontWeight: 700, color: theme.accentYellow, textTransform: 'uppercase' }}>
              Multi-Chapter Syllabus ({chapters.length} Chapters)
            </div>
            <button
              onClick={() => setShowAddChapterModal(prev => !prev)}
              disabled={isGeneratingChapter}
              title="Generate a new chapter to expand this curriculum"
              style={{
                backgroundColor: showAddChapterModal ? theme.accentGreen : theme.bgCardAlt,
                color: showAddChapterModal ? '#ffffff' : theme.accentGreen,
                border: `1px solid ${theme.accentGreen}`,
                borderRadius: '3px',
                padding: '2px 7px',
                fontSize: '10px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <Plus size={11} /> Chapter
            </button>
          </div>

          {/* Expandable New Chapter Generator Panel */}
          {showAddChapterModal && (
            <div style={{ backgroundColor: theme.bgCard, border: `1px solid ${theme.accentGreen}`, borderRadius: '5px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '7px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: theme.accentGreen, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>➕ Generate Next Chapter</span>
                <button onClick={() => setShowAddChapterModal(false)} style={{ background: 'none', border: 'none', color: theme.textMuted, cursor: 'pointer' }}><X size={12} /></button>
              </div>

              <input
                type="text"
                value={newChapterTopicInput}
                onChange={(e) => setNewChapterTopicInput(e.target.value)}
                placeholder="Topic (or leave blank to auto-sequence):"
                style={{
                  backgroundColor: theme.bgInput,
                  border: `1px solid ${theme.border}`,
                  color: theme.textMain,
                  padding: '6px 8px',
                  borderRadius: '3px',
                  fontSize: '11px',
                  outline: 'none'
                }}
                onKeyDown={(e) => { if (e.key === 'Enter') handleGenerateNewChapter(); }}
              />

              <div style={{ fontSize: '9px', color: theme.textMuted }}>Suggested Follow-up Chapters:</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                {(appMode === 'math' ? [
                  "Limits at Infinity", "Integration by Parts", "Taylor Series", "Multivariable Derivatives"
                ] : [
                  "Object-Oriented Design", "Binary Trees & BST", "Dynamic Programming", "Async & Concurrency"
                ]).map((pill, pIdx) => (
                  <button
                    key={pIdx}
                    onClick={() => handleGenerateNewChapter(pill)}
                    disabled={isGeneratingChapter}
                    style={{
                      backgroundColor: theme.bgCardAlt,
                      border: `1px solid ${theme.border}`,
                      color: theme.accentBlue,
                      borderRadius: '3px',
                      padding: '2px 6px',
                      fontSize: '9px',
                      cursor: 'pointer'
                    }}
                  >
                    + {pill}
                  </button>
                ))}
              </div>

              <div style={{ display: 'flex', gap: '6px', marginTop: '2px' }}>
                <button
                  onClick={() => handleGenerateNewChapter()}
                  disabled={isGeneratingChapter}
                  style={{
                    flex: 1,
                    backgroundColor: theme.accentGreen,
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '3px',
                    padding: '6px 10px',
                    fontSize: '11px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '5px'
                  }}
                >
                  {isGeneratingChapter ? <Loader2 size={12} className="animate-spin" color="#ffffff" /> : <Sparkles size={12} color="#ffffff" />}
                  <span>{isGeneratingChapter ? 'Synthesizing...' : '⚡ Generate Chapter'}</span>
                </button>
                <button
                  onClick={() => setShowAddChapterModal(false)}
                  style={{
                    backgroundColor: theme.bgCardAlt,
                    color: theme.textDim,
                    border: `1px solid ${theme.border}`,
                    borderRadius: '3px',
                    padding: '6px 10px',
                    fontSize: '11px',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {chapters.map(ch => {
            const isCollapsed = collapsedChapters[ch.id];
            const isChActive = currentProblem?.chapter_id === ch.id;

            return (
              <div key={ch.id} style={{ backgroundColor: theme.bgCard, border: `1px solid ${isChActive ? theme.accentGreen : theme.borderContrast}`, borderRadius: '4px' }}>
                <div 
                  onClick={() => setCollapsedChapters(prev => ({ ...prev, [ch.id]: !prev[ch.id] }))}
                  style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 600, color: theme.textMain, overflow: 'hidden' }}>
                    {isCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ch.title}</span>
                  </div>

                  <div style={{ display: 'flex', gap: '3px', flexShrink: 0 }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleGenerateProblem(ch.id, 'code_blank'); }}
                      disabled={isGeneratingProblem}
                      title={`Generate a Hard Blank Coding Task for ${ch.title}`}
                      style={{
                        backgroundColor: theme.bgCardAlt,
                        border: `1px solid ${theme.borderContrast}`,
                        color: theme.accentGold,
                        borderRadius: '3px',
                        padding: '2px 5px',
                        fontSize: '9px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px'
                      }}
                    >
                      <Zap size={8} color={theme.accentGold} />
                      <span>Blank</span>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleGenerateProblem(ch.id, 'code_partial'); }}
                      disabled={isGeneratingProblem}
                      title={`Generate a Partially Coded Scaffold for ${ch.title}`}
                      style={{
                        backgroundColor: theme.bgCardAlt,
                        border: `1px solid ${theme.borderContrast}`,
                        color: theme.accentGreen,
                        borderRadius: '3px',
                        padding: '2px 5px',
                        fontSize: '9px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px'
                      }}
                    >
                      <Plus size={8} color={theme.accentGreen} />
                      <span>Partial</span>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleGenerateProblem(ch.id, 'auto'); }}
                      disabled={isGeneratingProblem}
                      title={`Generate an Extra Practice Drill for ${ch.title}`}
                      style={{
                        backgroundColor: theme.bgCardAlt,
                        border: `1px solid ${theme.borderContrast}`,
                        color: theme.accentBlue,
                        borderRadius: '3px',
                        padding: '2px 5px',
                        fontSize: '9px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px'
                      }}
                    >
                      <span>Drill</span>
                    </button>
                  </div>
                </div>

                {!isCollapsed && (
                  <div style={{ padding: '0 8px 6px 18px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <div 
                      onClick={() => { setActiveChapterId(ch.id); setActiveTab("docs"); }}
                      style={{ padding: '4px 6px', fontSize: '11px', color: (activeTab === 'docs' && activeChapterId === ch.id) ? theme.accentYellow : theme.textDim, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                      <FileText size={12} /> README.md (Notes)
                    </div>

                    {(ch.problems || []).map(p => {
                      const isCurr = p.global_index === activeProblemIndex && activeTab === 'editor';
                      const isDone = completedProblems[p.global_index];

                      return (
                        <div
                          key={p.id}
                          onClick={() => { setActiveProblemIndex(p.global_index); setActiveChapterId(ch.id); setActiveTab("editor"); }}
                          style={{
                            padding: '4px 6px',
                            backgroundColor: isCurr ? theme.bgHighlight : 'transparent',
                            color: isCurr ? theme.accentYellow : theme.textDim,
                            fontSize: '11px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            borderRadius: '2px'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                            {appMode === 'math' ? <Calculator size={11} color={theme.accentBlue} /> : <Code2 size={11} color={theme.accentGreen} />}
                            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.title}</span>
                          </div>
                          {isDone && <Check size={11} color={theme.accentGreen} />}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Evaluation Feedback Badge */}
        {activeState.evaluation && (
          <div style={{ 
            padding: '10px', 
            borderRadius: '4px', 
            backgroundColor: activeState.evaluation === 'correct' ? '#103522' : '#381519', 
            border: `1px solid ${activeState.evaluation === 'correct' ? theme.accentGreen : theme.accentPink}`, 
            fontSize: '11px' 
          }}>
            <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', color: activeState.evaluation === 'correct' ? theme.accentGreen : theme.accentPink }}>
              {activeState.evaluation === 'correct' ? <CheckCircle2 size={13} color={theme.accentGreen} /> : <AlertTriangle size={13} color={theme.accentPink} />}
              {activeState.evaluation === 'correct' ? 'Verified Solution!' : 'Invariant Mismatch'}
            </div>
            <span style={{ color: theme.textMain }}>
              {(appMode === 'math' || currentProblem?.mode === 'math') ? <MathFormula math={currentProblem?.explanation} inline={true} /> : currentProblem?.explanation}
            </span>
          </div>
        )}
      </aside>

      {/* LEFT DIVIDER WALL (DRAG TO RESIZE LEFT SIDEBAR) */}
      <div
        onMouseDown={() => setIsDragging('left')}
        title="Drag wall to resize Left Sidebar"
        style={{
          width: '6px',
          cursor: 'col-resize',
          backgroundColor: isDragging === 'left' ? theme.accentGreen : theme.bgCardAlt,
          borderLeft: `1px solid ${theme.borderContrast}`,
          borderRight: `1px solid ${theme.borderContrast}`,
          userSelect: 'none',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'background-color 0.15s ease',
          zIndex: 10
        }}
      >
        <div style={{ width: '2px', height: '24px', backgroundColor: isDragging === 'left' ? theme.bgApp : theme.textMuted, borderRadius: '1px' }} />
      </div>

      {/* 2. CENTER PANEL: TABS, WORKSPACE CANVAS & TERMINAL (FLEX: 1) */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: '300px', overflow: 'hidden' }}>
        
        {/* Editor Tabs Bar */}
        <div style={{ height: '36px', backgroundColor: theme.bgHeader, display: 'flex', alignItems: 'center', borderBottom: `1px solid ${theme.borderContrast}` }}>
          <div 
            onClick={() => setActiveTab("editor")}
            style={{ 
              height: '100%', 
              padding: '0 16px', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px', 
              fontSize: '12px', 
              cursor: 'pointer',
              backgroundColor: activeTab === 'editor' ? theme.bgEditor : 'transparent',
              borderTop: activeTab === 'editor' ? `2px solid ${theme.accentGreen}` : 'none',
              color: activeTab === 'editor' ? theme.textMain : theme.textMuted,
              fontWeight: 600
            }}
          >
            {appMode === 'math' ? <Calculator size={13} color={theme.accentBlue} /> : <Code2 size={13} color={theme.accentGreen} />}
            <span>{currentProblem?.title || "exercise"}</span>
            <span style={{ fontSize: '9px', backgroundColor: theme.bgCardAlt, padding: '1px 5px', borderRadius: '2px', color: theme.accentYellow, fontWeight: 600 }}>
              {currentProblem?.type?.toUpperCase()}
            </span>
          </div>

          <div 
            onClick={() => setActiveTab("docs")}
            style={{ 
              height: '100%', 
              padding: '0 16px', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px', 
              fontSize: '12px', 
              cursor: 'pointer',
              backgroundColor: activeTab === 'docs' ? theme.bgEditor : 'transparent',
              borderTop: activeTab === 'docs' ? `2px solid ${theme.accentGreen}` : 'none',
              color: activeTab === 'docs' ? theme.textMain : theme.textMuted,
              fontWeight: 600
            }}
          >
            <BookOpen size={13} color={theme.accentYellow} />
            <span>README.md (Theory)</span>
          </div>

          <div style={{ marginLeft: 'auto', paddingRight: '14px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '11px', color: theme.accentGreen, fontWeight: 700 }}>
              XP: {totalXp}
            </span>
            <span style={{ fontSize: '11px', color: theme.accentYellow, backgroundColor: theme.bgCardAlt, padding: '2px 8px', borderRadius: '3px', border: `1px solid ${theme.border}` }}>
              Tier {currentLevel}
            </span>
          </div>
        </div>

        {/* Guided Roadmap & Problem Statement Bar */}
        <div style={{ padding: '10px 16px', backgroundColor: theme.bgPanel, borderBottom: `1px solid ${theme.border}`, display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontSize: '13px', color: theme.textMain, fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: theme.accentPink }}>#{activeProblemIndex + 1}</span>
              <span>{(appMode === 'math' || currentProblem?.mode === 'math') ? <MathFormula math={currentProblem?.guiding_question} inline={true} /> : currentProblem?.guiding_question}</span>
            </div>

            <button
              onClick={() => deliverProblemBriefing(currentProblem, true)}
              disabled={briefLoading}
              style={{
                backgroundColor: theme.bgCard,
                border: `1px solid ${theme.borderContrast}`,
                color: theme.accentBlue,
                padding: '4px 10px',
                borderRadius: '3px',
                fontSize: '11px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              {briefLoading ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} color={theme.accentBlue} />}
              <span>Review Mentor Briefing</span>
            </button>
          </div>

          {/* 3-Step Guided Learning Path */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px', color: theme.textMuted }}>
            <span style={{ color: theme.accentYellow, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <GraduationCap size={12} /> 1. Theory First
            </span>
            <span>&gt;</span>
            <span style={{ color: activeState.slotChoice || (activeState.assembledBlocks || []).length > 0 ? theme.accentGreen : theme.textMain, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Compass size={12} /> 2. Formulate Invariant
            </span>
            <span>&gt;</span>
            <span style={{ color: activeState.evaluation === 'correct' ? theme.accentGreen : theme.textMuted, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <CheckSquare size={12} /> 3. Verify Solution
            </span>
          </div>
        </div>

        {/* Main Canvas Area */}
        <div style={{ flex: 1, position: 'relative', display: 'flex', flexDirection: 'column', overflow: 'hidden', backgroundColor: theme.bgEditor }}>
          {/* Centered Linux Tux Penguin Shadow Watermark in Middle of Canvas */}
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              pointerEvents: 'none',
              userSelect: 'none',
              zIndex: 0,
              opacity: 0.18,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: theme.accentGreen
            }}
          >
            <PenguinShadow size={320} color={theme.accentGreen} />
          </div>

          <div style={{ position: 'relative', zIndex: 1, flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {activeTab === 'docs' ? (
              <div style={{ flex: 1, padding: '24px 30px', overflowY: 'auto', backgroundColor: 'transparent' }}>
                <div style={{ maxWidth: '800px', margin: '0 auto' }}>
                  <div style={{ marginBottom: '16px', padding: '12px 16px', backgroundColor: theme.bgCard, border: `1px solid ${theme.borderContrast}`, borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                      <div style={{ fontSize: '11px', color: theme.accentYellow, fontWeight: 700, textTransform: 'uppercase' }}>
                        Lesson Study Guide • {currentChapter?.title}
                      </div>
                      <div style={{ fontSize: '12px', color: theme.textDim, marginTop: '2px' }}>
                        {currentChapter?.summary || "Comprehensive theoretical foundations and worked examples."}
                      </div>
                    </div>
                    <div style={{ fontSize: '11px', color: theme.accentBlue, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Clock size={12} /> {currentChapter?.estimated_time_minutes || 20}m est. • {(currentChapter?.problems || []).length} exercises
                    </div>
                  </div>

                  {/* Professorial Lesson Action Bar */}
                  <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
                    <button
                      onClick={handleGenerateVoiceover}
                      disabled={voiceoverLoading}
                      style={{
                        backgroundColor: voiceoverPlaying ? '#17482d' : theme.bgCardAlt,
                        color: theme.accentGreen,
                        border: `1px solid ${voiceoverPlaying ? theme.accentGreen : theme.borderContrast}`,
                        padding: '6px 12px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      {voiceoverLoading ? <Loader2 size={12} className="animate-spin" color={theme.accentGreen} /> : voiceoverPlaying ? <Volume2 size={12} className="animate-pulse" color={theme.accentGreen} /> : <Mic size={12} color={theme.accentGreen} />}
                      <span>{voiceoverLoading ? 'Synthesizing...' : voiceoverPlaying ? 'Lecture Playing...' : '🎙️ Listen to Professor Lecture'}</span>
                    </button>

                    <button
                      onClick={() => handleGenerateProblem(currentChapter?.id || 1, 'code_blank')}
                      disabled={isGeneratingProblem}
                      style={{
                        backgroundColor: theme.bgCardAlt,
                        color: theme.accentGold,
                        border: `1px solid ${theme.borderContrast}`,
                        padding: '6px 12px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <Zap size={12} color={theme.accentGold} />
                      <span>+ Blank Code (Hard)</span>
                    </button>

                    <button
                      onClick={() => handleGenerateProblem(currentChapter?.id || 1, 'code_partial')}
                      disabled={isGeneratingProblem}
                      style={{
                        backgroundColor: theme.bgCardAlt,
                        color: theme.accentGreen,
                        border: `1px solid ${theme.borderContrast}`,
                        padding: '6px 12px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <Code2 size={12} color={theme.accentGreen} />
                      <span>+ Partial Scaffold</span>
                    </button>

                    <button
                      onClick={() => handleGenerateProblem(currentChapter?.id || 1, 'auto')}
                      disabled={isGeneratingProblem}
                      style={{
                        backgroundColor: theme.bgCardAlt,
                        color: theme.accentBlue,
                        border: `1px solid ${theme.borderContrast}`,
                        padding: '6px 12px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      {isGeneratingProblem ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                      <span>+ Extra Drill</span>
                    </button>

                    <button
                      onClick={() => setShowAddChapterModal(true)}
                      style={{
                        backgroundColor: theme.bgCardAlt,
                        color: theme.accentYellow,
                        border: `1px solid ${theme.borderContrast}`,
                        padding: '6px 12px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <Sparkles size={12} color={theme.accentYellow} />
                      <span>Generate Next Chapter</span>
                    </button>
                  </div>

                  <VSCodeMarkdown content={currentChapter?.content_markdown || "# Notes"} />

                  <div style={{ marginTop: '32px', paddingTop: '20px', borderTop: `1px solid ${theme.borderContrast}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <button
                      onClick={() => setShowAddChapterModal(true)}
                      style={{
                        backgroundColor: theme.bgCardAlt,
                        color: theme.accentYellow,
                        border: `1px solid ${theme.borderContrast}`,
                        padding: '10px 16px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}
                    >
                      <Plus size={14} />
                      <span>Generate Next Chapter in Syllabus</span>
                    </button>

                    <button
                      onClick={() => {
                        const firstProb = (currentChapter?.problems || [])[0];
                        if (firstProb && firstProb.global_index !== undefined) {
                          setActiveProblemIndex(firstProb.global_index);
                        }
                        setActiveTab("editor");
                      }}
                      style={{
                        backgroundColor: theme.accentGreen,
                        color: '#ffffff',
                        border: 'none',
                        padding: '10px 20px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}
                    >
                      <span>Start Chapter Exercises & Tests</span>
                      <ChevronRight size={14} color="#ffffff" />
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              renderInteractiveCanvas()
            )}
          </div>
        </div>

        {/* TERMINAL DIVIDER WALL (DRAG TO RESIZE SANDBOX CONSOLE) */}
        <div
          onMouseDown={() => setIsDragging('terminal')}
          title="Drag wall to resize Sandbox Terminal Console"
          style={{
            height: '6px',
            cursor: 'row-resize',
            backgroundColor: isDragging === 'terminal' ? theme.accentGreen : theme.bgCardAlt,
            borderTop: `1px solid ${theme.borderContrast}`,
            borderBottom: `1px solid ${theme.borderContrast}`,
            userSelect: 'none',
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background-color 0.15s ease',
            zIndex: 10
          }}
        >
          <div style={{ height: '2px', width: '28px', backgroundColor: isDragging === 'terminal' ? theme.bgApp : theme.textMuted, borderRadius: '1px' }} />
        </div>

        {/* Bottom Sandbox Terminal Console (Resizable Height) */}
        <div style={{ height: `${terminalHeight}px`, minHeight: '60px', maxHeight: '500px', backgroundColor: theme.bgPanel, display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
          <div style={{ height: '26px', backgroundColor: theme.bgActivity, display: 'flex', alignItems: 'center', padding: '0 12px', gap: '8px', borderBottom: `1px solid ${theme.border}` }}>
            <Terminal size={12} color={theme.accentGreen} />
            <span style={{ fontSize: '11px', color: theme.textMain, fontWeight: 700 }}>
              {appMode === 'math' ? 'MATHEMATICAL LOG & VERIFICATION' : 'SANDBOX EXECUTION CONSOLE (PYODIDE WASM)'}
            </span>
          </div>
          <div style={{ padding: '8px 14px', overflowY: 'auto', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '3px', fontFamily: theme.fontMono }}>
            {terminalOutput.map((l, i) => (
              <span key={i} style={{ 
                color: l.includes('[ERROR]') || l.includes('FAIL') || l.includes('[MISMATCH]') || l.includes('Exception')
                  ? theme.accentPink 
                  : l.includes('[SUCCESS]') || l.includes('[VERIFIED]') || l.includes('PASS') 
                    ? theme.accentGreen 
                    : l.includes('[MODE SWITCH]') || l.includes('[ELEVENLABS') || l.includes('[PYODIDE') 
                      ? theme.accentBlue 
                      : l.includes('[NOTICE]') || l.includes('[WARNING]')
                        ? theme.accentYellow
                        : theme.textDim 
              }}>
                {l}
              </span>
            ))}
          </div>
        </div>

      </main>

      {/* RIGHT DIVIDER WALL (DRAG TO RESIZE SOCRATIC MENTOR PANEL) */}
      <div
        onMouseDown={() => setIsDragging('right')}
        title="Drag wall to resize Socratic Mentor Panel"
        style={{
          width: '6px',
          cursor: 'col-resize',
          backgroundColor: isDragging === 'right' ? theme.accentGreen : theme.bgCardAlt,
          borderLeft: `1px solid ${theme.borderContrast}`,
          borderRight: `1px solid ${theme.borderContrast}`,
          userSelect: 'none',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'background-color 0.15s ease',
          zIndex: 10
        }}
      >
        <div style={{ width: '2px', height: '24px', backgroundColor: isDragging === 'right' ? theme.accentGold : theme.textMuted, borderRadius: '1px' }} />
      </div>

      {/* 3. RIGHT PANEL: SOCRATIC MENTOR (THEORY-FIRST PEDAGOGICAL LEADERSHIP) (RESIZABLE) */}
      <section style={{ 
        width: `${rightWidth}px`, 
        minWidth: '200px', 
        maxWidth: '750px', 
        flexShrink: 0, 
        backgroundColor: theme.bgSidebar, 
        display: 'flex', 
        flexDirection: 'column' 
      }}>
        <div style={{ height: '36px', padding: '0 14px', borderBottom: `1px solid ${theme.borderContrast}`, display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: theme.bgHeader }}>
          <Sparkles size={14} color={theme.accentYellow} />
          <span style={{ fontSize: '12px', fontWeight: 700, color: theme.textMain }}>Socratic Mentor</span>
          <span style={{ marginLeft: 'auto', fontSize: '10px', color: theme.accentGreen }}>● Leading Session</span>
        </div>

        {/* Chat History with Active Briefings & Guided Action Pills */}
        <div style={{ flex: 1, padding: '14px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '12px' }}>
          {chatHistory.map((msg, i) => (
            <div 
              key={i} 
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                backgroundColor: msg.role === 'user' ? theme.bgCardAlt : theme.bgCard,
                color: theme.textMain,
                padding: '10px 14px',
                borderRadius: '6px',
                maxWidth: '94%',
                lineHeight: '1.5',
                border: msg.role === 'model' ? `1px solid ${msg.isBriefing ? theme.accentGreen : theme.borderContrast}` : `1px solid ${theme.border}`
              }}
            >
              {msg.isBriefing && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', fontWeight: 700, color: theme.accentYellow, textTransform: 'uppercase', marginBottom: '6px', borderBottom: `1px solid ${theme.border}`, paddingBottom: '4px' }}>
                  <GraduationCap size={13} color={theme.accentYellow} />
                  <span>Problem Briefing & Theory</span>
                </div>
              )}

              <VSCodeMarkdown content={msg.content} />

              {/* Guided Prompt Action Pills */}
              {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '6px', borderTop: `1px solid ${theme.border}`, paddingTop: '8px' }}>
                  {msg.suggestedActions.map((action, actionIdx) => (
                    <button
                      key={actionIdx}
                      onClick={() => sendMentorQuery(action)}
                      style={{
                        backgroundColor: theme.bgCardAlt,
                        border: `1px solid ${theme.borderContrast}`,
                        color: theme.accentBlue,
                        padding: '3px 8px',
                        borderRadius: '3px',
                        fontSize: '10px',
                        cursor: 'pointer',
                        transition: 'all 0.1s ease'
                      }}
                    >
                      {action}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          {chatLoading && <div style={{ color: theme.accentYellow, fontSize: '11px', fontStyle: 'italic' }}>Mentor is reviewing theory & reasoning...</div>}
        </div>

        {/* Chat Input */}
        <form onSubmit={handleSendMessage} style={{ padding: '10px', borderTop: `1px solid ${theme.borderContrast}`, display: 'flex', gap: '6px', backgroundColor: theme.bgHeader }}>
          <input
            type="text"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            placeholder="Ask mentor: 'Why does option B fail?', 'Explain invariant'..."
            style={{ 
              flex: 1, 
              backgroundColor: theme.bgInput, 
              border: `1px solid ${theme.borderContrast}`, 
              color: theme.textMain, 
              padding: '7px 10px', 
              borderRadius: '4px', 
              fontSize: '12px', 
              fontFamily: 'inherit',
              outline: 'none'
            }}
          />
          <button type="submit" style={{ backgroundColor: theme.accentGreen, border: 'none', color: '#ffffff', borderRadius: '4px', padding: '0 12px', cursor: 'pointer', fontWeight: 700 }}>
            <Send size={13} color="#ffffff" />
          </button>
        </form>
      </section>

    </div>
  );
};

export default EduIDE;