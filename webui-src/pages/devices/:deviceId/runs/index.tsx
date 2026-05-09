import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Button } from 'primereact/button';
import { Card } from 'primereact/card';
import { Column } from 'primereact/column';
import { DataTable } from 'primereact/datatable';
import { Dialog } from 'primereact/dialog';
import { InputSwitch } from 'primereact/inputswitch';
import { InputText } from 'primereact/inputtext';
import { Message } from 'primereact/message';
import { Tag } from 'primereact/tag';
import { Link, useLocation } from 'wouter';

import {
  type RunRecord,
  type RunStatus,
  isTerminal,
  listRuns,
  reapRun,
  stopRun,
  subscribeRunEvents,
  submitRun,
  SubmitConflictError,
} from '../../../../util/runs';

const statusSeverity: Record<RunStatus, 'success' | 'info' | 'warning' | 'danger' | 'secondary'> = {
  completed: 'success',
  running: 'info',
  pending: 'warning',
  failed: 'danger',
  cancelled: 'secondary',
};

export function DeviceRunsPage({ params }: { params: { deviceId: string } }) {
  const [, navigate] = useLocation();
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const refreshing = useRef(false);

  const refresh = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      setRuns(await listRuns());
    } catch (e) {
      setError(String(e));
    } finally {
      refreshing.current = false;
    }
  }, []);

  useEffect(() => {
    refresh();
    const close = subscribeRunEvents({ onState: () => refresh() });
    return close;
  }, [refresh]);

  const onStop = useCallback(async (slug: string) => {
    try { await stopRun(slug); await refresh(); }
    catch (e) { setError(String(e)); }
  }, [refresh]);

  const onReap = useCallback(async (slug: string) => {
    try { await reapRun(slug); await refresh(); }
    catch (e) { setError(String(e)); }
  }, [refresh]);

  return (
    <Card
      title="Runs"
      subTitle={<Link to={`/devices/${params.deviceId}`}>&larr; device</Link>}
    >
      {error && (
        <Message severity="error" text={error} style={{ marginBottom: '0.75rem' }} />
      )}

      <div style={{ marginBottom: '0.75rem' }}>
        <Button
          label="Submit"
          icon="pi pi-plus"
          size="small"
          onClick={() => setSubmitOpen(true)}
        />
      </div>

      <DataTable
        value={runs}
        emptyMessage="No runs yet."
        selectionMode="single"
        onRowSelect={(e) => navigate(`/devices/${params.deviceId}/runs/${e.data.slug}`)}
      >
        <Column field="phone_command.name" header="Name" />
        <Column field="slug" header="Slug" />
        <Column
          field="status"
          header="Status"
          body={(row: RunRecord) => (
            <Tag value={row.status} severity={statusSeverity[row.status]} />
          )}
        />
        <Column
          header="Actions"
          body={(row: RunRecord) => (
            <div style={{ display: 'flex', gap: '0.25rem' }}>
              {!isTerminal(row.status) && (
                <Button
                  label="Stop" icon="pi pi-times" size="small" severity="danger"
                  onClick={(e) => { e.stopPropagation(); onStop(row.slug); }}
                />
              )}
              {isTerminal(row.status) && (
                <Button
                  label="Reap" icon="pi pi-trash" size="small" severity="secondary"
                  onClick={(e) => { e.stopPropagation(); onReap(row.slug); }}
                />
              )}
            </div>
          )}
        />
      </DataTable>

      <SubmitDialog
        open={submitOpen}
        onClose={() => setSubmitOpen(false)}
        onSubmitted={() => { setSubmitOpen(false); refresh(); }}
      />
    </Card>
  );
}

function SubmitDialog({
  open, onClose, onSubmitted,
}: {
  open: boolean;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const [name, setName] = useState('echo');
  const [argv, setArgv] = useState('echo hello');
  const [daemon, setDaemon] = useState(false);
  const [slug, setSlug] = useState('');
  const [mutex, setMutex] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async () => {
    setErr(null);
    const parts = argv.trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) {
      setErr('argv is required');
      return;
    }
    try {
      await submitRun({
        name: name || 'unnamed',
        steps: [{ argv: parts }],
        connections: [],
        daemon,
        run_option: { slug: slug || null, mutex_by_slug: mutex },
      });
      onSubmitted();
    } catch (e) {
      if (e instanceof SubmitConflictError) {
        setErr('A run with this slug is already active; stop or reap it first.');
      } else {
        setErr(String(e));
      }
    }
  };

  return (
    <Dialog header="Submit run" visible={open} onHide={onClose} style={{ width: '32rem' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <Field label="Name">
          <InputText value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="argv">
          <InputText value={argv} onChange={(e) => setArgv(e.target.value)} />
        </Field>
        <Field label="Daemon">
          <InputSwitch checked={daemon} onChange={(e) => setDaemon(!!e.value)} />
        </Field>

        <details>
          <summary style={{ cursor: 'pointer', color: 'var(--text-color-secondary)' }}>
            Advanced
          </summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
            <Field label="Slug (blank → auto-gen)">
              <InputText value={slug} onChange={(e) => setSlug(e.target.value)} />
            </Field>
            <Field label="Mutex by slug">
              <InputSwitch checked={mutex} onChange={(e) => setMutex(!!e.value)} />
            </Field>
          </div>
        </details>

        {err && <Message severity="error" text={err} />}

        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <Button label="Cancel" severity="secondary" onClick={onClose} />
          <Button label="Submit" icon="pi pi-check" onClick={onSubmit} />
        </div>
      </div>
    </Dialog>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
      <span style={{ minWidth: '10rem', color: 'var(--text-color-secondary)' }}>{label}</span>
      {children}
    </div>
  );
}
