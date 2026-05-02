import { Card } from 'primereact/card';
import { Button } from 'primereact/button';
import { Panel } from 'primereact/panel';
import { InputTextarea } from 'primereact/inputtextarea';
import { Link } from 'wouter';
import { useState } from 'react';

export function DeviceState({ params }: { params: { id: string } }) {
  const [commandInput, setCommandInput] = useState('');

  const handleSubmit = () => {
    if (!commandInput.trim()) return;
    // TODO: POST /api/ui_v0/devices/:id/commands
    setCommandInput('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <Card
        title={`Device: ${params.id}`}
        subTitle={<Link to="/devices">&larr; all devices</Link>}
      >
        <Panel header="State" toggleable>
          <p>Loading state...</p>
          {/* TODO: GET /api/ui_v0/devices/:id/state */}
        </Panel>
      </Card>

      <Card title="Submit command">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <InputTextarea
            value={commandInput}
            onChange={(e) => setCommandInput(e.target.value)}
            placeholder="termux-battery-status"
            rows={3}
            autoResize
          />
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button label="Run" icon="pi pi-play" onClick={handleSubmit} />
            <Link to={`/devices/${params.id}/commands`}>
              <Button label="Command history" icon="pi pi-list" severity="secondary" />
            </Link>
          </div>
        </div>
      </Card>
    </div>
  );
}
