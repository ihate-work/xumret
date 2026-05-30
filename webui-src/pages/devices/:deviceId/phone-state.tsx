import type { ReactNode } from 'react';
import { Column } from 'primereact/column';
import { DataTable } from 'primereact/datatable';
import { Tag } from 'primereact/tag';
import { CardBoundary } from '~/components/CardBoundary';
import { DeviceSubPage } from '~/components/DeviceSubPage';
import { useSlice, SliceBody } from '~/components/Slice';
import {
  fetchBattery,
  fetchCallLog,
  fetchClipboard,
  fetchLocation,
  fetchTelephony,
  fetchWifi,
  type Battery,
  type CallLogEntry,
  type Location,
  type Telephony,
  type Wifi,
} from '~/util/deviceState';

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
      <span style={{ color: 'var(--text-color-secondary)' }}>{label}</span>
      <span>{children}</span>
    </div>
  );
}

export function PhoneStatePage({ params }: { params: { deviceId: string } }) {
  const battery = useSlice<Battery>(fetchBattery);
  const wifi = useSlice<Wifi>(fetchWifi);
  const location = useSlice<Location>(fetchLocation);
  const telephony = useSlice<Telephony>(fetchTelephony);
  const callLog = useSlice<CallLogEntry[]>(fetchCallLog);
  const clipboard = useSlice<string>(fetchClipboard);

  return (
    <DeviceSubPage deviceId={params.deviceId} title="Phone state">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <CardBoundary title="Battery">
          <SliceBody slice={battery} render={(b) => (
            <>
              <Field label="Level">{b.percentage}%</Field>
              <Field label="Health"><Tag value={b.health} severity="success" /></Field>
              <Field label="Status">{b.status}</Field>
              <Field label="Plugged">{b.plugged}</Field>
              <Field label="Temperature">{b.temperature} °C</Field>
            </>
          )} />
        </CardBoundary>

        <CardBoundary title="WiFi">
          <SliceBody slice={wifi} render={(w) => (
            <>
              <Field label="SSID">{w.ssid}</Field>
              <Field label="IP">{w.ip}</Field>
              <Field label="Signal">{w.rssi} dBm</Field>
              <Field label="Speed">{w.link_speed_mbps} Mbps</Field>
              <Field label="Frequency">{w.frequency_mhz} MHz</Field>
            </>
          )} />
        </CardBoundary>

        <CardBoundary title="Location">
          <SliceBody slice={location} render={(l) => (
            <>
              <Field label="Latitude">{l.latitude}</Field>
              <Field label="Longitude">{l.longitude}</Field>
              <Field label="Altitude">{l.altitude} m</Field>
              <Field label="Accuracy">±{l.accuracy} m</Field>
              <Field label="Provider">{l.provider}</Field>
            </>
          )} />
        </CardBoundary>

        <CardBoundary title="Telephony">
          <SliceBody slice={telephony} render={(t) => (
            <>
              <Field label="Operator">{t.network_operator_name}</Field>
              <Field label="Network">{t.network_type}</Field>
              <Field label="Data">{t.data_state}</Field>
              <Field label="SIM">{t.sim_state}</Field>
              <Field label="Phone type">{t.phone_type}</Field>
            </>
          )} />
        </CardBoundary>
      </div>

      <CardBoundary title="Call Log">
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
      </CardBoundary>

      <CardBoundary title="Clipboard">
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
      </CardBoundary>
    </DeviceSubPage>
  );
}
