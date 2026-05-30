import { Column } from 'primereact/column';
import { DataTable } from 'primereact/datatable';
import { CardBoundary } from '~/components/CardBoundary';
import { DeviceSubPage } from '~/components/DeviceSubPage';
import { useSlice, SliceBody } from '~/components/Slice';
import { fetchVolume, type VolumeEntry } from '~/util/deviceState';

export function VolumePage({ params }: { params: { deviceId: string } }) {
  const volume = useSlice<VolumeEntry[]>(fetchVolume);

  return (
    <DeviceSubPage deviceId={params.deviceId} title="Volume">
      <CardBoundary title="Volume">
        <SliceBody slice={volume} render={(rows) => (
          <DataTable value={rows} size="small">
            <Column field="stream" header="Stream" />
            <Column header="Level" body={(row) => `${row.volume} / ${row.max_volume}`} />
          </DataTable>
        )} />
      </CardBoundary>
    </DeviceSubPage>
  );
}
