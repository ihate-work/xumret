import { Card } from 'primereact/card';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Tag } from 'primereact/tag';
import { useLocation } from 'wouter';

interface Device {
  id: string;
  name: string;
  status: 'online' | 'offline';
}

const placeholder: Device[] = [
  { id: 'phone-1', name: 'Pixel 7', status: 'online' },
];

export function DeviceList() {
  const [, navigate] = useLocation();

  return (
    <Card title="Devices">
      <DataTable
        value={placeholder}
        selectionMode="single"
        onRowSelect={(e) => navigate(`/devices/${e.data.id}`)}
      >
        <Column field="name" header="Name" />
        <Column field="id" header="ID" />
        <Column
          field="status"
          header="Status"
          body={(row: Device) => (
            <Tag value={row.status} severity={row.status === 'online' ? 'success' : 'danger'} />
          )}
        />
      </DataTable>
    </Card>
  );
}
