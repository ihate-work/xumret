import { useCallback, useEffect, useState } from 'react';
import { Button } from 'primereact/button';
import { Card } from 'primereact/card';
import { Message } from 'primereact/message';
import { Panel } from 'primereact/panel';
import { Tag } from 'primereact/tag';
import { Link } from 'wouter';

import {
  type RunOutputEvent,
  type RunRecord,
  type RunStatus,
  isTerminal,
  getRunState,
  reapRun,
  stopRun,
  subscribeRunEvents,
} from '../../../../../util/runs';

const statusSeverity: Record<RunStatus, 'success' | 'info' | 'warning' | 'danger' | 'secondary'> = {
  completed: 'success',
  running: 'info',
  pending: 'warning',
  failed: 'danger',
  cancelled: 'secondary',
};

export function DeviceRunPage({
  params,
}: {
  params: { deviceId: string; slug: string };
}) {
  const { deviceId, slug } = params;
  const [run, setRun] = useState<RunRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRun(await getRunState(slug));
    } catch (e) {
      setError(String(e));
    }
  }, [slug]);

  useEffect(() => {
    refresh();
    // Event-sourcing-style: snapshot from /state, then merge SSE deltas.
    const close = subscribeRunEvents({
      onState: (ev) => {
        if (ev.slug !== slug) return;
        // Cheap approach: re-fetch on any state delta for this slug.
        refresh();
      },
      onOutput: (ev) => {
        if (ev.slug !== slug) return;
        setRun((prev) => prev ? mergeOutput(prev, ev) : prev);
      },
    });
    return close;
  }, [slug, refresh]);

  const onStop = async () => {
    try { await stopRun(slug); await refresh(); }
    catch (e) { setError(String(e)); }
  };
  const onReap = async () => {
    try { await reapRun(slug); }
    catch (e) { setError(String(e)); }
  };

  if (!run) {
    return (
      <Card title={`Run: ${slug}`}>
        {error
          ? <Message severity="error" text={error} />
          : <span>Loading…</span>}
      </Card>
    );
  }

  return (
    <Card
      title={<span>Run <code>{run.slug}</code></span>}
      subTitle={<Link to={`/devices/${deviceId}/runs`}>&larr; runs</Link>}
    >
      {error && (
        <Message severity="error" text={error} style={{ marginBottom: '0.75rem' }} />
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
        <Tag value={run.status} severity={statusSeverity[run.status]} />
        <span style={{ color: 'var(--text-color-secondary)' }}>
          {run.phone_command.name}{run.phone_command.daemon ? ' (daemon)' : ''}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
          {!isTerminal(run.status) && (
            <Button label="Stop" icon="pi pi-times" severity="danger" size="small" onClick={onStop} />
          )}
          {isTerminal(run.status) && (
            <Button label="Reap" icon="pi pi-trash" severity="secondary" size="small" onClick={onReap} />
          )}
        </div>
      </div>

      {run.error && (
        <Message severity="error" text={run.error} style={{ marginBottom: '0.75rem' }} />
      )}

      {run.steps.map((step, i) => {
        const argv = run.phone_command.steps[i]?.argv.join(' ') ?? '';
        const exited = step.exit_code !== null;
        const header = (
          <span>
            Step {i + 1}: <code>{argv}</code>{' '}
            {step.pid !== null && <span style={{ color: 'var(--text-color-secondary)' }}>pid {step.pid}</span>}{' '}
            {exited && (
              <Tag
                value={`exit ${step.exit_code}`}
                severity={step.exit_code === 0 ? 'success' : 'danger'}
              />
            )}
          </span>
        );
        return (
          <Panel
            key={i}
            header={header}
            toggleable
            style={{ marginBottom: '0.5rem' }}
          >
            {step.stdout_tail && (
              <>
                <div style={{ color: 'var(--text-color-secondary)', marginBottom: '0.25rem' }}>
                  stdout {step.stdout_dropped > 0 && <em>(dropped {step.stdout_dropped})</em>}
                </div>
                <pre style={{
                  margin: 0, padding: '0.5rem', background: 'var(--surface-ground)',
                  borderRadius: '6px', whiteSpace: 'pre-wrap',
                }}>{step.stdout_tail}</pre>
              </>
            )}
            {step.stderr_tail && (
              <>
                <div style={{ color: 'var(--text-color-secondary)', margin: '0.5rem 0 0.25rem' }}>
                  stderr {step.stderr_dropped > 0 && <em>(dropped {step.stderr_dropped})</em>}
                </div>
                <pre style={{
                  margin: 0, padding: '0.5rem', background: 'var(--surface-ground)',
                  borderRadius: '6px', whiteSpace: 'pre-wrap',
                }}>{step.stderr_tail}</pre>
              </>
            )}
            {!step.stdout_tail && !step.stderr_tail && (
              <span style={{ color: 'var(--text-color-secondary)' }}>(no output)</span>
            )}
          </Panel>
        );
      })}

      <Panel header="Transition log" toggleable collapsed style={{ marginTop: '0.75rem' }}>
        <ol style={{ margin: 0, paddingLeft: '1.25rem' }}>
          {run.transitions.map((t, idx) => (
            <li key={idx}>
              <code>{t.type}</code>
              {t.step_index !== undefined && ` step ${t.step_index}`}
              {t.pid !== undefined && ` pid ${t.pid}`}
              {t.exit_code !== undefined && ` exit ${t.exit_code}`}
              {t.error && ` "${t.error}"`}
            </li>
          ))}
        </ol>
      </Panel>
    </Card>
  );
}

const TAIL_CAP = 128 * 1024;

function mergeOutput(rec: RunRecord, ev: RunOutputEvent): RunRecord {
  const steps = rec.steps.map((s, i) => {
    if (i !== ev.step_index) return s;
    const next = { ...s };
    if (ev.fd === 'stdout') {
      if (ev.lines && ev.lines.length) {
        next.stdout_tail = (next.stdout_tail + ev.lines.join('\n') + '\n').slice(-TAIL_CAP);
      }
      if (ev.dropped_lines) next.stdout_dropped += ev.dropped_lines;
      if (ev.dropped_bytes) next.stdout_dropped += ev.dropped_bytes;
    } else {
      if (ev.lines && ev.lines.length) {
        next.stderr_tail = (next.stderr_tail + ev.lines.join('\n') + '\n').slice(-TAIL_CAP);
      }
      if (ev.dropped_lines) next.stderr_dropped += ev.dropped_lines;
      if (ev.dropped_bytes) next.stderr_dropped += ev.dropped_bytes;
    }
    return next;
  });
  return { ...rec, steps };
}
