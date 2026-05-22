import { Card } from 'primereact/card';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Message } from 'primereact/message';
import { ProgressSpinner } from 'primereact/progressspinner';
import { useLocation } from 'wouter';
import { listDevicesApiDevicesGet, useApi } from '~/_api';

export function DevicesPage() {
  const [, navigate] = useLocation();
  const { data: devices, error, isLoading } = useApi(listDevicesApiDevicesGet);

  return (
    <Card title="Devices">
      {error && <Message severity="error" text={String(error)} />}
      {isLoading && <ProgressSpinner style={{ width: '2rem', height: '2rem' }} />}
      {devices && (
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
