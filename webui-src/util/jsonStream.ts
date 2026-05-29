/**
 * Yield each top-level JSON value parsed from `text`.
 *
 * Handles three shapes interchangeably:
 *   - one JSON value (possibly multi-line, pretty-printed)
 *   - JSON Lines: one value per line, newline-separated
 *   - any whitespace-separated sequence of JSON values
 *
 * Each yielded value is the result of `JSON.parse` on a structurally-scanned
 * slice — i.e. supports the full JSON grammar, not a fragile regex.
 *
 * Throws `SyntaxError` on malformed or truncated input. The error message
 * includes the byte offset where scanning gave up.
 */
export function* iterJsonValues(text: string): Generator<unknown> {
  let i = 0;
  while (i < text.length) {
    while (i < text.length && isWhitespace(text.charCodeAt(i))) i++;
    if (i >= text.length) return;
    const start = i;
    i = scanValueEnd(text, i);
    yield JSON.parse(text.slice(start, i));
  }
}

/** Eager variant of {@link iterJsonValues} — collects every value into an array. */
export function parseJsonValues(text: string): unknown[] {
  return Array.from(iterJsonValues(text));
}

function isWhitespace(code: number): boolean {
  // JSON whitespace per RFC 8259: space, tab, LF, CR.
  return code === 0x20 || code === 0x09 || code === 0x0a || code === 0x0d;
}

function scanValueEnd(text: string, start: number): number {
  const c = text[start];
  if (c === '{' || c === '[') return scanContainer(text, start);
  if (c === '"') return scanString(text, start);
  return scanPrimitive(text, start);
}

function scanString(text: string, start: number): number {
  let i = start + 1;
  while (i < text.length) {
    const c = text[i];
    if (c === '\\') { i += 2; continue; }
    if (c === '"') return i + 1;
    i++;
  }
  throw new SyntaxError(`unterminated string at offset ${start}`);
}

function scanContainer(text: string, start: number): number {
  let depth = 0;
  let i = start;
  let inString = false;
  while (i < text.length) {
    const c = text[i];
    if (inString) {
      if (c === '\\') { i += 2; continue; }
      if (c === '"') inString = false;
      i++;
      continue;
    }
    if (c === '"') { inString = true; i++; continue; }
    if (c === '{' || c === '[') depth++;
    else if (c === '}' || c === ']') {
      depth--;
      if (depth === 0) return i + 1;
    }
    i++;
  }
  throw new SyntaxError(`unterminated ${text[start] === '{' ? 'object' : 'array'} at offset ${start}`);
}

function scanPrimitive(text: string, start: number): number {
  // Number / true / false / null run until whitespace or a structural delimiter.
  let i = start;
  while (i < text.length) {
    const c = text[i];
    if (c === ' ' || c === '\t' || c === '\n' || c === '\r'
        || c === ',' || c === '}' || c === ']') {
      return i;
    }
    i++;
  }
  return i;
}
