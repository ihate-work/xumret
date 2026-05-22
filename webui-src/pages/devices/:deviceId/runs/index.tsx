import { useCallback, useState } from 'react';
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
  listRunsApiRunsGet,
  reapRunApiRunsSlugReapPost,
  stopRunApiRunsSlugStopPost,
  submitRunApiRunsPost,
  useApi,
  useRunEvents,
  type RunRecord,
  type RunStatus,
} from '~/_api';

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

export function DeviceRunsPage({ params }: { params: { deviceId: string } }) {
  const [, navigate] = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [submitOpen, setSubmitOpen] = useState(false);

  const { data: runs, error: fetchErr, mutate } = useApi(listRunsApiRunsGet);

  useRunEvents(() => mutate());

  const onStop = useCallback(async (slug: string) => {
    try {
      await stopRunApiRunsSlugStopPost({ path: { slug }, throwOnError: true });
      await mutate();
    } catch (e) {
      setError(String(e));
    }
  }, [mutate]);

  const onReap = useCallback(async (slug: string) => {
    try {
      await reapRunApiRunsSlugReapPost({ path: { slug }, throwOnError: true });
      await mutate();
    } catch (e) {
      setError(String(e));
    }
  }, [mutate]);

  const shownError = error ?? (fetchErr ? String(fetchErr) : null);

  return (
    <Card
      title="Runs"
      subTitle={<Link to={`/devices/${params.deviceId}`}>&larr; device</Link>}
    >
      {shownError && (
        <Message severity="error" text={shownError} style={{ marginBottom: '0.75rem' }} />
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
        value={runs ?? []}
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
        onSubmitted={() => { setSubmitOpen(false); mutate(); }}
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
    const result = await submitRunApiRunsPost({
      body: {
        phone_command: {
          name: name || 'unnamed',
          steps: [{ argv: parts }],
          run_option: { slug: slug || undefined, mutex_by_slug: mutex },
        },
      },
    });
    if (result.error) {
      if (result.response?.status === 409) {
        setErr('A run with this slug is already active; stop or reap it first.');
      } else {
        setErr(JSON.stringify(result.error));
      }
      return;
    }
    onSubmitted();
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
