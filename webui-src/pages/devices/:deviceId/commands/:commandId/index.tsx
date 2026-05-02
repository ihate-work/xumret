import { Card } from 'primereact/card';
import { Button } from 'primereact/button';
import { Panel } from 'primereact/panel';
import { Tag } from 'primereact/tag';
import { Link } from 'wouter';

export function DeviceCommandPage({ params }: { params: { deviceId: string; commandId: string } }) {
  // TODO: GET /api/ui_v0/devices/:id/commands/:commandId

  return (
    <Card
      title={`Command: ${params.commandId}`}
      subTitle={<Link to={`/devices/${params.deviceId}/commands`}>&larr; commands</Link>}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
        <Tag value="pending" severity="warning" />
        <Button label="Cancel" icon="pi pi-times" severity="danger" size="small" />
      </div>

      <Panel header="Step 1" toggleable>
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
          {/* TODO: per-step stdout/stderr */}
          Loading...
        </pre>
      </Panel>
    </Card>
  );
}
