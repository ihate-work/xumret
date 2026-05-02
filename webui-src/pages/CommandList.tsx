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

const statusSeverity: Record<string, 'success' | 'info' | 'warn' | 'danger' | 'secondary'> = {
  completed: 'success',
  running: 'info',
  pending: 'warn',
  failed: 'danger',
  cancelled: 'secondary',
};

const placeholder: CommandRow[] = [];

export function CommandList({ params }: { params: { id: string } }) {
  const [, navigate] = useLocation();

  return (
    <Card
      title="Commands"
      subTitle={<Link to={`/devices/${params.id}`}>&larr; device</Link>}
    >
      <DataTable
        value={placeholder}
        emptyMessage="No commands yet."
        selectionMode="single"
        onRowSelect={(e) => navigate(`/devices/${params.id}/commands/${e.data.command_id}`)}
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
