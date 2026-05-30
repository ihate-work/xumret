import { Card } from 'primereact/card';
import { Link } from 'wouter';
import { DeviceSubPage } from '~/components/DeviceSubPage';

interface Tile {
  to: string;
  title: string;
  subTitle: string;
  icon: string;
}

function tiles(deviceId: string): Tile[] {
  const base = `/devices/${deviceId}`;
  return [
    {
      to: `${base}/phone-state`,
      title: 'Phone state',
      subTitle: 'battery, wifi, location, telephony, calls, clipboard',
      icon: 'pi pi-mobile',
    },
    {
      to: `${base}/sms`,
      title: 'SMS',
      subTitle: 'inbox and sent messages',
      icon: 'pi pi-envelope',
    },
    {
      to: `${base}/camera`,
      title: 'Camera',
      subTitle: 'available cameras and capture',
      icon: 'pi pi-camera',
    },
    {
      to: `${base}/volume`,
      title: 'Volume',
      subTitle: 'audio stream levels',
      icon: 'pi pi-volume-up',
    },
    {
      to: `${base}/runs`,
      title: 'Runs',
      subTitle: 'submit and inspect phone commands',
      icon: 'pi pi-bolt',
    },
  ];
}

export function DevicePage({ params }: { params: { deviceId: string } }) {
  return (
    <DeviceSubPage deviceId={params.deviceId}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '1rem',
      }}>
        {tiles(params.deviceId).map((t) => (
          <Link key={t.to} to={t.to} style={{ textDecoration: 'none', color: 'inherit' }}>
            <Card
              title={
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <i className={t.icon} style={{ fontSize: '1.5rem' }} />
                  {t.title}
                </span>
              }
              subTitle={t.subTitle}
              style={{ cursor: 'pointer', height: '100%' }}
            />
          </Link>
        ))}
      </div>
    </DeviceSubPage>
  );
}
