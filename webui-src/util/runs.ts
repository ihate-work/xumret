/**
 * API client for the Run lifecycle.
 *
 * Backend: see doc/design-process-management.md and src/xumret/server/api/.
 */

import type { PhoneCommand } from './commands';

export type RunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface StepState {
  pid: number | null;
  exit_code: number | null;
  stdout_tail: string;
  stderr_tail: string;
  stdout_dropped: number;
  stderr_dropped: number;
}

export interface RunStateEvent {
  type:
    | 'created'
    | 'step_started'
    | 'step_exited'
    | 'running'
    | 'completed'
    | 'failed'
    | 'cancelled'
    | 'daemon_started'
    | 'daemon_status'
    | 'daemon_ended';
  slug: string;
  at: number;
  // optional fields per type
  step_index?: number;
  pid?: number;
  exit_code?: number;
  error?: string;
  all_running?: boolean;
  step_running?: boolean[];
}

export interface RunOutputEvent {
  type: 'output';
  slug: string;
  at: number;
  step_index: number;
  fd: 'stdout' | 'stderr';
  lines?: string[];
  bytes?: string; // base64
  dropped_lines?: number;
  dropped_bytes?: number;
}

export interface RunRecord {
  slug: string;
  phone_command: PhoneCommand;
  status: RunStatus;
  created_at: number;
  updated_at: number;
  error: string | null;
  daemon_started: boolean;
  daemon_ended: boolean;
  steps: StepState[];
  transitions: RunStateEvent[];
}

export const TERMINAL_STATUSES: ReadonlyArray<RunStatus> = [
  'completed', 'failed', 'cancelled',
];

export function isTerminal(status: RunStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

// --- HTTP helpers ---

export class SubmitConflictError extends Error {
  constructor(public slug: string, public reason: string) {
    super(`slug "${slug}" conflict: ${reason}`);
    this.name = 'SubmitConflictError';
  }
}

async function _json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail: unknown = undefined;
    try {
      detail = await resp.json();
    } catch {
      // body not JSON
    }
    if (resp.status === 409 && detail && typeof detail === 'object' && 'detail' in detail) {
      const d = (detail as { detail: { slug?: string; reason?: string } }).detail;
      throw new SubmitConflictError(d.slug ?? '', d.reason ?? 'conflict');
    }
    throw new Error(`HTTP ${resp.status}: ${JSON.stringify(detail)}`);
  }
  return resp.json() as Promise<T>;
}

export async function submitRun(phone_command: PhoneCommand): Promise<RunRecord> {
  const resp = await fetch('/api/runs', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ phone_command }),
  });
  return _json<RunRecord>(resp);
}

export async function listRuns(): Promise<RunRecord[]> {
  return _json<RunRecord[]>(await fetch('/api/runs'));
}

export async function getRun(slug: string): Promise<RunRecord> {
  return _json<RunRecord>(await fetch(`/api/runs/${encodeURIComponent(slug)}`));
}

export async function getRunState(slug: string): Promise<RunRecord> {
  return _json<RunRecord>(
    await fetch(`/api/runs/${encodeURIComponent(slug)}/state`),
  );
}

export async function stopRun(slug: string): Promise<RunRecord> {
  return _json<RunRecord>(
    await fetch(`/api/runs/${encodeURIComponent(slug)}/stop`, { method: 'POST' }),
  );
}

export async function reapRun(slug: string): Promise<{ slug: string; reaped: boolean }> {
  return _json(
    await fetch(`/api/runs/${encodeURIComponent(slug)}/reap`, { method: 'POST' }),
  );
}

// --- SSE subscription ---

export interface RunEventHandlers {
  onState?: (ev: RunStateEvent) => void;
  onOutput?: (ev: RunOutputEvent) => void;
  onError?: (err: Event) => void;
}

/** Open the device-wide event stream. Returns a close function. */
export function subscribeRunEvents(handlers: RunEventHandlers): () => void {
  const es = new EventSource('/api/events');
  if (handlers.onState) {
    es.addEventListener('run_state', (e) => {
      try {
        handlers.onState!(JSON.parse((e as MessageEvent).data));
      } catch (err) {
        console.error('parse run_state failed', err);
      }
    });
  }
  if (handlers.onOutput) {
    es.addEventListener('run_output', (e) => {
      try {
        handlers.onOutput!(JSON.parse((e as MessageEvent).data));
      } catch (err) {
        console.error('parse run_output failed', err);
      }
    });
  }
  if (handlers.onError) {
    es.onerror = handlers.onError;
  }
  return () => es.close();
}
