// SSE consumption for the /api/events stream.
//
// The generated SDK can't model server-sent events (eventStreamApiEventsGet
// is just a GET), so this stays a hand-written EventSource wrapper. Exposed
// as a hook so call sites don't need their own effect plumbing.

import { useRef } from 'react';
import { useAsyncEffect } from '@jokester/ts-commonutil/lib/react/hook/use-async-effect';

import { createDebugLogger } from '~/util/log';
import type {
  RunStateCancelled,
  RunStateCompleted,
  RunStateCreated,
  RunStateFailed,
  RunStateRunning,
  RunStateStepExited,
  RunStateStepStarted,
  RunStateTimedOut,
} from './generated';

const log = createDebugLogger(import.meta.url);

export type RunStateEvent =
  | RunStateCancelled
  | RunStateCompleted
  | RunStateCreated
  | RunStateFailed
  | RunStateRunning
  | RunStateStepExited
  | RunStateStepStarted
  | RunStateTimedOut;

// Shared fan-out: one EventSource per page, lazily opened on first listener,
// kept alive once opened. All consumers (`useRunEvents`, `watchRunTerminal`)
// register a listener instead of opening their own EventSource — keeps the
// `/api/events` connection count at 1 per page regardless of how many
// concurrent fetchers are watching for terminal events.

type Listener = (ev: RunStateEvent) => void;
const listeners = new Set<Listener>();
let sharedES: EventSource | null = null;

function ensureOpen(): void {
  if (sharedES) return;
  log('open shared');
  const es = new EventSource('/api/events');
  es.addEventListener('run_state', (e) => {
    let ev: RunStateEvent;
    try {
      ev = JSON.parse((e as MessageEvent).data) as RunStateEvent;
    } catch (err) {
      log('parse run_state failed %o', err);
      return;
    }
    log('run_state type=%s slug=%s', ev.type, ev.slug);
    for (const l of listeners) {
      try { l(ev); } catch (err) { log('listener threw %o', err); }
    }
  });
  es.addEventListener('error', () => {
    // EventSource auto-reconnects on transient errors; just log.
    log('eventsource error readyState=%d', es.readyState);
  });
  sharedES = es;
}

function subscribe(onState: Listener): () => void {
  ensureOpen();
  listeners.add(onState);
  return () => { listeners.delete(onState); };
}

/**
 * Subscribe to /api/events for the lifetime of the component.
 * The latest `onState` is always called — the EventSource isn't re-opened
 * when the callback identity changes.
 */
export function useRunEvents(onState: (ev: RunStateEvent) => void): void {
  const ref = useRef(onState);
  ref.current = onState;
  useAsyncEffect(async (_running, released) => {
    const close = subscribe((ev) => ref.current(ev));
    await released;
    close();
  }, []);
}

const TERMINAL_EVENT_TYPES: ReadonlySet<string> = new Set([
  'completed', 'failed', 'cancelled', 'timed_out',
]);
const isTerminalEvent = (t: string | undefined): boolean =>
  t !== undefined && TERMINAL_EVENT_TYPES.has(t);

/**
 * Open a one-shot SSE subscription that resolves when the named slug reaches
 * a terminal state. Returns the matching terminal event.
 *
 * Caller is responsible for opening this *before* submitting the Run to
 * avoid a race where the run completes during the submit RTT.
 */
export function watchRunTerminal(
  slug: string,
  signal?: AbortSignal,
): Promise<RunStateEvent> {
  log('watch slug=%s', slug);
  return new Promise<RunStateEvent>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('aborted', 'AbortError'));
      return;
    }
    const close = subscribe((ev) => {
      if (ev.slug !== slug) return;
      if (isTerminalEvent(ev.type)) {
        cleanup();
        resolve(ev);
      }
    });
    const onAbort = () => {
      cleanup();
      reject(new DOMException('aborted', 'AbortError'));
    };
    const cleanup = () => {
      close();
      signal?.removeEventListener('abort', onAbort);
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}
