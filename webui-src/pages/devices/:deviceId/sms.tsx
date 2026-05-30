import { Column } from 'primereact/column';
import { DataTable } from 'primereact/datatable';
import { Tag } from 'primereact/tag';
import { CardBoundary } from '~/components/CardBoundary';
import { DeviceSubPage } from '~/components/DeviceSubPage';
import { useSlice, SliceBody } from '~/components/Slice';
import { fetchSmsList, type SmsMessage } from '~/util/deviceState';

export function SmsPage({ params }: { params: { deviceId: string } }) {
  const sms = useSlice<SmsMessage[]>(fetchSmsList);

  return (
    <DeviceSubPage deviceId={params.deviceId} title="SMS">
      <CardBoundary title="SMS">
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
      </CardBoundary>
    </DeviceSubPage>
  );
}
