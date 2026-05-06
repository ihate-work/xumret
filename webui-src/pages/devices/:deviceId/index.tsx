import type { ReactNode } from 'react';
import { Card } from 'primereact/card';
import { Column } from 'primereact/column';
import { DataTable } from 'primereact/datatable';
import { Tag } from 'primereact/tag';
import { Link } from 'wouter';

// Dummy data matching DummyExecutor canned responses

const battery = {
  health: 'GOOD',
  percentage: 72,
  plugged: 'UNPLUGGED',
  status: 'DISCHARGING',
  temperature: 28.5,
  current: -423000,
};

const wifi = {
  bssid: '00:11:22:33:44:55',
  frequency_mhz: 5180,
  ip: '192.168.1.42',
  link_speed_mbps: 866,
  rssi: -45,
  ssid: 'HomeNetwork',
  supplicant_state: 'COMPLETED',
};

const location = {
  latitude: 35.6762,
  longitude: 139.6503,
  altitude: 40.0,
  accuracy: 12.3,
  bearing: 0.0,
  speed: 0.0,
  provider: 'gps',
};

const telephony = {
  data_enabled: 'true',
  data_state: 'CONNECTED',
  device_id: '000000000000000',
  device_software_version: '01',
  network_operator: '44010',
  network_operator_name: 'NTT DOCOMO',
  network_type: 'LTE',
  phone_type: 'GSM',
  sim_operator: '44010',
  sim_operator_name: 'NTT DOCOMO',
  sim_state: 'READY',
};

const smsList = [
  {
    threadid: 1,
    type: 'inbox',
    read: true,
    number: '+81-90-1234-5678',
    body: 'Hey, are you free tonight?',
    received: '2026-05-01 18:32:00',
  },
  {
    threadid: 1,
    type: 'sent',
    read: true,
    number: '+81-90-1234-5678',
    body: 'Sure, let me check my schedule',
    received: '2026-05-01 18:35:00',
  },
];

const contacts = [
  { name: 'Alice', number: '+81-90-1234-5678' },
  { name: 'Bob', number: '+81-80-9876-5432' },
];

const callLog = [
  {
    name: 'Alice',
    phone_number: '+81-90-1234-5678',
    type: 'INCOMING',
    date: '2026-05-01 17:00:00',
    duration: '120',
  },
];

const cameras = [
  {
    id: '0',
    facing: 'back',
    jpeg_output_sizes: [
      { width: 4032, height: 3024 },
      { width: 1920, height: 1080 },
    ],
  },
  {
    id: '1',
    facing: 'front',
    jpeg_output_sizes: [
      { width: 3264, height: 2448 },
      { width: 1920, height: 1080 },
    ],
  },
];

const clipboard = 'clipboard contents here';

const volumes = [
  { stream: 'music', volume: 8, max_volume: 15 },
  { stream: 'ring', volume: 5, max_volume: 7 },
  { stream: 'notification', volume: 5, max_volume: 7 },
  { stream: 'alarm', volume: 6, max_volume: 7 },
];

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
      <span style={{ color: 'var(--text-color-secondary)' }}>{label}</span>
      <span>{children}</span>
    </div>
  );
}

export function DevicePage({ params }: { params: { deviceId: string } }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <Card
        title={`Device: ${params.deviceId}`}
        subTitle={<Link to="/devices">&larr; all devices</Link>}
      />

      {/* Phone state — 2×2 grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <Card title="Battery">
          <Field label="Level">{battery.percentage}%</Field>
          <Field label="Health"><Tag value={battery.health} severity="success" /></Field>
          <Field label="Status">{battery.status}</Field>
          <Field label="Plugged">{battery.plugged}</Field>
          <Field label="Temperature">{battery.temperature} °C</Field>
        </Card>

        <Card title="WiFi">
          <Field label="SSID">{wifi.ssid}</Field>
          <Field label="IP">{wifi.ip}</Field>
          <Field label="Signal">{wifi.rssi} dBm</Field>
          <Field label="Speed">{wifi.link_speed_mbps} Mbps</Field>
          <Field label="Frequency">{wifi.frequency_mhz} MHz</Field>
        </Card>

        <Card title="Location">
          <Field label="Latitude">{location.latitude}</Field>
          <Field label="Longitude">{location.longitude}</Field>
          <Field label="Altitude">{location.altitude} m</Field>
          <Field label="Accuracy">±{location.accuracy} m</Field>
          <Field label="Provider">{location.provider}</Field>
        </Card>

        <Card title="Telephony">
          <Field label="Operator">{telephony.network_operator_name}</Field>
          <Field label="Network">{telephony.network_type}</Field>
          <Field label="Data">{telephony.data_state}</Field>
          <Field label="SIM">{telephony.sim_state}</Field>
          <Field label="Phone type">{telephony.phone_type}</Field>
        </Card>
      </div>

      {/* SMS */}
      <Card title="SMS">
        <DataTable value={smsList} size="small">
          <Column
            field="type"
            header="Type"
            body={(row) => (
              <Tag value={row.type} severity={row.type === 'inbox' ? 'info' : 'secondary'} />
            )}
          />
          <Column field="number" header="Number" />
          <Column field="body" header="Message" />
          <Column field="received" header="Time" />
        </DataTable>
      </Card>

      {/* Contacts + Call Log */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <Card title="Contacts">
          <DataTable value={contacts} size="small">
            <Column field="name" header="Name" />
            <Column field="number" header="Number" />
          </DataTable>
        </Card>

        <Card title="Call Log">
          <DataTable value={callLog} size="small">
            <Column field="name" header="Name" />
            <Column
              field="type"
              header="Type"
              body={(row) => <Tag value={row.type} severity="info" />}
            />
            <Column field="date" header="Date" />
            <Column header="Duration" body={(row) => `${row.duration}s`} />
          </DataTable>
        </Card>
      </div>

      {/* Cameras */}
      <Card title="Cameras">
        <DataTable value={cameras} size="small">
          <Column field="id" header="ID" />
          <Column field="facing" header="Facing" body={(row) => <Tag value={row.facing} />} />
          <Column
            header="Resolutions"
            body={(row) =>
              row.jpeg_output_sizes
                .map((s: { width: number; height: number }) => `${s.width}×${s.height}`)
                .join(', ')}
          />
        </DataTable>
      </Card>

      {/* Clipboard + Volume */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <Card title="Clipboard">
          <div style={{
            padding: '0.5rem',
            background: 'var(--surface-ground)',
            borderRadius: '6px',
            fontFamily: 'monospace',
          }}>
            {clipboard}
          </div>
        </Card>

        <Card title="Volume">
          <DataTable value={volumes} size="small">
            <Column field="stream" header="Stream" />
            <Column header="Level" body={(row) => `${row.volume} / ${row.max_volume}`} />
          </DataTable>
        </Card>
      </div>
    </div>
  );
}
