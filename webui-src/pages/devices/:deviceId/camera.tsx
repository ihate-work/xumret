import { Column } from 'primereact/column';
import { DataTable } from 'primereact/datatable';
import { Tag } from 'primereact/tag';
import { CardBoundary } from '~/components/CardBoundary';
import { DeviceSubPage } from '~/components/DeviceSubPage';
import { useSlice, SliceBody } from '~/components/Slice';
import { fetchCameras, type CameraInfo } from '~/util/deviceState';

export function CameraPage({ params }: { params: { deviceId: string } }) {
  const cameras = useSlice<CameraInfo[]>(fetchCameras);

  return (
    <DeviceSubPage deviceId={params.deviceId} title="Camera">
      <CardBoundary title="Cameras">
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
      </CardBoundary>
    </DeviceSubPage>
  );
}
