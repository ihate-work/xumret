import createDebug, { type Debugger } from 'debug';

// log.ts lives at <root>/util/log.ts. Resolving '../' against this file's
// own URL yields the frontend-root URL — `file:///…/webui-src/` under Node,
// `http://host:port/` under Vite dev. We strip that prefix from each caller
// URL to derive the namespace. Doing it dynamically means renaming the
// frontend root (e.g. webui-src → ui) needs no edit here.
const ROOT = new URL('../', import.meta.url);

/**
 * Create a `debug` Debugger whose namespace is derived from the call-site file.
 * Intended for use as a file-global constant (one or many per file):
 *
 *   const log = createDebugLogger(import.meta.url);
 *   const logFetch = createDebugLogger(import.meta.url, 'fetch');
 *   const logCache = createDebugLogger(import.meta.url, 'cache');
 *
 * `import.meta.url` for `<root>/pages/devices/index.tsx` yields
 * `xumret:pages:devices:index`; passing `suffix='fetch'` extends it to
 * `xumret:pages:devices:index:fetch`. Toggle output in the browser with
 * `localStorage.debug = 'xumret:*'` (or any glob the `debug` package accepts).
 */
export function createDebugLogger(importer: string, suffix?: string): Debugger {
  const base = toNamespace(importer);
  return createDebug(suffix ? `${base}:${suffix}` : base);
}

function toNamespace(importer: string): string {
  let rel: string;
  try {
    const { pathname } = new URL(importer);
    rel = pathname.startsWith(ROOT.pathname)
      ? pathname.slice(ROOT.pathname.length)
      : pathname.replace(/^\//, '');
  } catch {
    // Plain (non-URL) path: best-effort strip of the root directory's name.
    const rootDir = ROOT.pathname.replace(/\/$/, '').split('/').pop() ?? '';
    const idx = rootDir ? importer.indexOf(`${rootDir}/`) : -1;
    rel = idx >= 0 ? importer.slice(idx + rootDir.length + 1) : importer;
  }
  const ns = rel.replace(/\.[^./]+$/, '').split('/').filter(Boolean).join(':');
  // Collapse runs of colons: Wouter route params (':deviceId') would otherwise
  // produce '::' when joined with the path separator.
  return `xumret:${ns}`.replace(/:+/g, ':');
}
