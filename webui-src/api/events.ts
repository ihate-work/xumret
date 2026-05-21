// SSE consumption for the /api/events stream.
//
// The generated SDK can't model server-sent events (eventStreamApiEventsGet
// is just a GET), so this stays a hand-written EventSource wrapper. Exposed
// as a hook so call sites don't need their own useEffect.

import { useEffect, useRef } from 'react';

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

export type RunStateEvent =
  | RunStateCancelled
  | RunStateCompleted
  | RunStateCreated
  | RunStateFailed
  | RunStateRunning
  | RunStateStepExited
  | RunStateStepStarted
  | RunStateTimedOut;

function subscribe(onState: (ev: RunStateEvent) => void): () => void {
  const es = new EventSource('/api/events');
  es.addEventListener('run_state', (e) => {
    try {
      onState(JSON.parse((e as MessageEvent).data));
    } catch (err) {
      console.error('parse run_state failed', err);
    }
  });
  return () => es.close();
}

/**
 * Subscribe to /api/events for the lifetime of the component.
 * The latest `onState` is always called — the EventSource isn't re-opened
 * when the callback identity changes.
 */
export function useRunEvents(onState: (ev: RunStateEvent) => void): void {
  const ref = useRef(onState);
  ref.current = onState;
  useEffect(() => subscribe((ev) => ref.current(ev)), []);
}
