import { useEffect, useState, type ReactNode } from 'react';
import { Card } from 'primereact/card';
import { Column } from 'primereact/column';
import { DataTable } from 'primereact/datatable';
import { Message } from 'primereact/message';
import { ProgressSpinner } from 'primereact/progressspinner';
import { Tag } from 'primereact/tag';
import { Link } from 'wouter';
import {
  fetchBattery,
  fetchCallLog,
  fetchCameras,
  fetchClipboard,
  fetchContacts,
  fetchLocation,
  fetchSmsList,
  fetchTelephony,
  fetchVolume,
  fetchWifi,
  type Battery,
  type CallLogEntry,
  type CameraInfo,
  type Contact,
  type Location,
  type SmsMessage,
  type Telephony,
  type VolumeEntry,
  type Wifi,
} from '~/util/deviceState';

type Slice<T> = { data: T | null; err: string | null };

function useSlice<T>(fetcher: () => Promise<T>): Slice<T> {
  const [state, setState] = useState<Slice<T>>({ data: null, err: null });
  useEffect(() => {
    let cancelled = false;
    fetcher()
      .then((d) => { if (!cancelled) setState({ data: d, err: null }); })
      .catch((e) => { if (!cancelled) setState({ data: null, err: String(e) }); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return state;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
      <span style={{ color: 'var(--text-color-secondary)' }}>{label}</span>
      <span>{children}</span>
    </div>
  );
}

function SliceBody<T>({ slice, render }: { slice: Slice<T>; render: (d: T) => ReactNode }) {
  if (slice.err) return <Message severity="error" text={slice.err} />;
  if (slice.data === null) return <ProgressSpinner style={{ width: '1.5rem', height: '1.5rem' }} />;
  return <>{render(slice.data)}</>;
}

export function DevicePage({ params }: { params: { deviceId: string } }) {
  const battery = useSlice<Battery>(fetchBattery);
  const wifi = useSlice<Wifi>(fetchWifi);
  const location = useSlice<Location>(fetchLocation);
  const telephony = useSlice<Telephony>(fetchTelephony);
  const sms = useSlice<SmsMessage[]>(fetchSmsList);
  const contacts = useSlice<Contact[]>(fetchContacts);
  const callLog = useSlice<CallLogEntry[]>(fetchCallLog);
  const cameras = useSlice<CameraInfo[]>(fetchCameras);
  const clipboard = useSlice<string>(fetchClipboard);
  const volume = useSlice<VolumeEntry[]>(fetchVolume);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <Card
        title={`Device: ${params.deviceId}`}
        subTitle={<Link to="/devices">&larr; all devices</Link>}
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <Card title="Battery">
          <SliceBody slice={battery} render={(b) => (
            <>
              <Field label="Level">{b.percentage}%</Field>
              <Field label="Health"><Tag value={b.health} severity="success" /></Field>
              <Field label="Status">{b.status}</Field>
              <Field label="Plugged">{b.plugged}</Field>
              <Field label="Temperature">{b.temperature} °C</Field>
            </>
          )} />
        </Card>

        <Card title="WiFi">
          <SliceBody slice={wifi} render={(w) => (
            <>
              <Field label="SSID">{w.ssid}</Field>
              <Field label="IP">{w.ip}</Field>
              <Field label="Signal">{w.rssi} dBm</Field>
              <Field label="Speed">{w.link_speed_mbps} Mbps</Field>
              <Field label="Frequency">{w.frequency_mhz} MHz</Field>
            </>
          )} />
        </Card>

        <Card title="Location">
          <SliceBody slice={location} render={(l) => (
            <>
              <Field label="Latitude">{l.latitude}</Field>
              <Field label="Longitude">{l.longitude}</Field>
              <Field label="Altitude">{l.altitude} m</Field>
              <Field label="Accuracy">±{l.accuracy} m</Field>
              <Field label="Provider">{l.provider}</Field>
            </>
          )} />
        </Card>

        <Card title="Telephony">
          <SliceBody slice={telephony} render={(t) => (
            <>
              <Field label="Operator">{t.network_operator_name}</Field>
              <Field label="Network">{t.network_type}</Field>
              <Field label="Data">{t.data_state}</Field>
              <Field label="SIM">{t.sim_state}</Field>
              <Field label="Phone type">{t.phone_type}</Field>
            </>
          )} />
        </Card>
      </div>

      <Card title="SMS">
        <SliceBody slice={sms} render={(rows) => (
          <DataTable value={rows} size="small">
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
        )} />
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <Card title="Contacts">
          <SliceBody slice={contacts} render={(rows) => (
            <DataTable value={rows} size="small">
              <Column field="name" header="Name" />
              <Column field="number" header="Number" />
            </DataTable>
          )} />
        </Card>

        <Card title="Call Log">
          <SliceBody slice={callLog} render={(rows) => (
            <DataTable value={rows} size="small">
              <Column field="name" header="Name" />
              <Column
                field="type"
                header="Type"
                body={(row) => <Tag value={row.type} severity="info" />}
              />
              <Column field="date" header="Date" />
              <Column header="Duration" body={(row) => `${row.duration}s`} />
            </DataTable>
          )} />
        </Card>
      </div>

      <Card title="Cameras">
        <SliceBody slice={cameras} render={(rows) => (
          <DataTable value={rows} size="small">
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
        )} />
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <Card title="Clipboard">
          <SliceBody slice={clipboard} render={(c) => (
            <div style={{
              padding: '0.5rem',
              background: 'var(--surface-ground)',
              borderRadius: '6px',
              fontFamily: 'monospace',
            }}>
              {c}
            </div>
          )} />
        </Card>

        <Card title="Volume">
          <SliceBody slice={volume} render={(rows) => (
            <DataTable value={rows} size="small">
              <Column field="stream" header="Stream" />
              <Column header="Level" body={(row) => `${row.volume} / ${row.max_volume}`} />
            </DataTable>
          )} />
        </Card>
      </div>
    </div>
  );
}
