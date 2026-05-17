import { useEffect, useState } from 'react';
import { Card } from 'primereact/card';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Message } from 'primereact/message';
import { ProgressSpinner } from 'primereact/progressspinner';
import { useLocation } from 'wouter';
import { listDevices, type Device } from '~/util/devices';

export function DevicesPage() {
  const [, navigate] = useLocation();
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listDevices()
      .then((d) => { if (!cancelled) setDevices(d); })
      .catch((e) => { if (!cancelled) setErr(String(e)); });
    return () => { cancelled = true; };
  }, []);

  return (
    <Card title="Devices">
      {err && <Message severity="error" text={err} />}
      {!err && devices === null && <ProgressSpinner style={{ width: '2rem', height: '2rem' }} />}
      {devices !== null && (
        <DataTable
          value={devices}
          selectionMode="single"
          onRowSelect={(e) => navigate(`/devices/${e.data.id}`)}
        >
          <Column field="name" header="Name" />
          <Column field="id" header="ID" />
        </DataTable>
      )}
    </Card>
  );
}
