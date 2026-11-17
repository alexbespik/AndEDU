/** Turns a Pyodide traceback into Socratic process-level scaffolding with exact fault diagnosis. */
export function explainError(raw, script, userLines) {
  if (!raw) return '';
  const lines = raw.split('\n').map((l) => l.trimEnd()).filter(Boolean);
  const last = lines[lines.length - 1] || raw;
  const frames = [...raw.matchAll(/File "<exec>", line (\d+)/g)];
  const n = frames.length ? Number(frames[frames.length - 1][1]) : null;
  const src = n ? (script.split('\n')[n - 1] || '').trim() : '';

  // Classify fault into Socratic Guidance
  let socraticHint = '';
  if (/AssertionError/.test(last) || /AssertionError/.test(raw)) {
    if (/==\s*None|is None|returned None/i.test(raw) || /==\s*None|is None/i.test(src)) {
      socraticHint = 'Missing Return: Your function completed without returning a value (None). Did you compute a result but forget the return statement?';
    } else if (/len\(.*?\)\s*==\s*|differs by 1|off-by-one/i.test(raw) || /len\(.*?\)/i.test(src)) {
      socraticHint = 'Off-by-One Bound: The result differs by an unexpected count. Check your loop boundaries (range(...)): does it include or exclude the endpoint?';
    } else if (/\[\]|\b0\b|""|empty/i.test(src) || /empty|zero/i.test(raw)) {
      socraticHint = 'Boundary Condition: The failure occurred on a boundary input (e.g. empty sequence or 0). Does your algorithm include a base check for empty or zero-sized cases?';
    } else {
      socraticHint = 'Assertion Condition Failed: Compare your function output with the expected condition in the test assertion.';
    }
  } else if (/IndexError/.test(raw)) {
    socraticHint = 'Index Bound Exceeded: You attempted to access an element beyond the sequence boundary. If a list has N elements, valid indices are 0 through N-1.';
  } else if (/TypeError.*(?:can only concatenate|unsupported operand type)/i.test(raw)) {
    socraticHint = 'Type Incompatibility: Attempted an operation between text (str) and numbers. In Python, convert explicitly using str(...) or int(...) before combining.';
  } else if (/RecursionError/.test(raw)) {
    socraticHint = 'Base Case Omission: Infinite recursion occurred. Verify that your base case triggers and that each recursive call makes progress toward the base condition.';
  } else if (/KeyError/.test(raw)) {
    socraticHint = 'Key Not Found: Attempted to access a dictionary key that does not exist. Verify the key exists before lookup or use dict.get(key, default).';
  } else if (/ZeroDivisionError/.test(raw)) {
    socraticHint = 'Zero Division: Division by zero occurred. Verify that your denominator cannot become zero under any input.';
  }

  let baseMsg = '';
  if (/^AssertionError/.test(last) && n && n > userLines) {
    baseMsg = `Failed: ${src}${last.length > 15 ? `\n${last}` : ''}`;
  } else if (n && n <= userLines) {
    baseMsg = `${last}\n(your code, line ${n}: ${src})`;
  } else {
    baseMsg = last;
  }

  return socraticHint ? `${baseMsg}\n\n💡 Socratic Diagnostic: ${socraticHint}` : baseMsg;
}
