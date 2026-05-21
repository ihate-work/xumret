import { useState } from 'react';
import { Button } from 'primereact/button';
import { Card } from 'primereact/card';
import { Message } from 'primereact/message';
import { Panel } from 'primereact/panel';
import { Tag } from 'primereact/tag';
import { Link } from 'wouter';

import {
  getRunStateApiRunsSlugStateGet,
  reapRunApiRunsSlugReapPost,
  stopRunApiRunsSlugStopPost,
  useApi,
  useRunEvents,
  type RunStatus,
} from '~/api';

const statusSeverity: Record<RunStatus, 'success' | 'info' | 'warning' | 'danger' | 'secondary'> = {
  completed: 'success',
  running: 'info',
  pending: 'warning',
  failed: 'danger',
  cancelled: 'secondary',
  timed_out: 'danger',
};

const TERMINAL: ReadonlyArray<RunStatus> = ['completed', 'failed', 'cancelled', 'timed_out'];
const isTerminal = (s: RunStatus) => TERMINAL.includes(s);

export function DeviceRunPage({
  params,
}: {
  params: { deviceId: string; slug: string };
}) {
  const { deviceId, slug } = params;
  const [error, setError] = useState<string | null>(null);

  const { data: run, error: fetchErr, mutate } = useApi(
    getRunStateApiRunsSlugStateGet,
    { path: { slug } },
  );

  // SSE delta arrives → revalidate snapshot.
  useRunEvents((ev) => { if (ev.slug === slug) mutate(); });

  const onStop = async () => {
    try {
      await stopRunApiRunsSlugStopPost({ path: { slug }, throwOnError: true });
      await mutate();
    } catch (e) {
      setError(String(e));
    }
  };
  const onReap = async () => {
    try {
      await reapRunApiRunsSlugReapPost({ path: { slug }, throwOnError: true });
    } catch (e) {
      setError(String(e));
    }
  };

  const shownError = error ?? (fetchErr ? String(fetchErr) : null);

  if (!run) {
    return (
      <Card title={`Run: ${slug}`}>
        {shownError
          ? <Message severity="error" text={shownError} />
          : <span>Loading…</span>}
      </Card>
    );
  }

  return (
    <Card
      title={<span>Run <code>{run.slug}</code></span>}
      subTitle={<Link to={`/devices/${deviceId}/runs`}>&larr; runs</Link>}
    >
      {shownError && (
        <Message severity="error" text={shownError} style={{ marginBottom: '0.75rem' }} />
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
        <Tag value={run.status} severity={statusSeverity[run.status]} />
        <span style={{ color: 'var(--text-color-secondary)' }}>
          {run.phone_command.name}
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
        const exited = step.exit_code !== null && step.exit_code !== undefined;
        const header = (
          <span>
            Step {i + 1}: <code>{argv}</code>{' '}
            {step.pid !== null && step.pid !== undefined && (
              <span style={{ color: 'var(--text-color-secondary)' }}>pid {step.pid}</span>
            )}{' '}
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
                <div style={{ color: 'var(--text-color-secondary)', marginBottom: '0.25rem' }}>stdout</div>
                <pre style={{
                  margin: 0, padding: '0.5rem', background: 'var(--surface-ground)',
                  borderRadius: '6px', whiteSpace: 'pre-wrap',
                }}>{step.stdout_tail}</pre>
              </>
            )}
            {step.stderr_tail && (
              <>
                <div style={{ color: 'var(--text-color-secondary)', margin: '0.5rem 0 0.25rem' }}>stderr</div>
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
          {(run.transitions ?? []).map((t, idx) => (
            <li key={idx}>
              <code>{t.type}</code>
              {'step_index' in t && ` step ${t.step_index}`}
              {'pid' in t && ` pid ${t.pid}`}
              {'exit_code' in t && ` exit ${t.exit_code}`}
              {'error' in t && t.error && ` "${t.error}"`}
            </li>
          ))}
        </ol>
      </Panel>
    </Card>
  );
}
