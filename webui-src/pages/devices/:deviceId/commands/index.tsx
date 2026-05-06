import { Card } from 'primereact/card';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Tag } from 'primereact/tag';
import { Link, useLocation } from 'wouter';

interface CommandRow {
  command_id: string;
  name: string;
  status: string;
  created_at: string;
}

const statusSeverity: Record<string, 'success' | 'info' | 'warning' | 'danger' | 'secondary'> = {
  completed: 'success',
  running: 'info',
  pending: 'warning',
  failed: 'danger',
  cancelled: 'secondary',
};

const placeholder: CommandRow[] = [];

export function DeviceCommandsPage({ params }: { params: { deviceId: string } }) {
  const [, navigate] = useLocation();

  return (
    <Card
      title="Commands"
      subTitle={<Link to={`/devices/${params.deviceId}`}>&larr; device</Link>}
    >
      <DataTable
        value={placeholder}
        emptyMessage="No commands yet."
        selectionMode="single"
        onRowSelect={(e) => navigate(`/devices/${params.deviceId}/commands/${e.data.command_id}`)}
      >
        <Column field="name" header="Name" />
        <Column
          field="status"
          header="Status"
          body={(row: CommandRow) => (
            <Tag value={row.status} severity={statusSeverity[row.status] ?? 'info'} />
          )}
        />
        <Column field="created_at" header="Created" />
      </DataTable>
    </Card>
  );
}
