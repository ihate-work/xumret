import { Route, Switch, Redirect } from 'wouter';
import { DevicesPage } from './pages/devices/index';
import { DevicePage } from './pages/devices/:deviceId/index';
import { PhoneStatePage } from './pages/devices/:deviceId/phone-state';
import { SmsPage } from './pages/devices/:deviceId/sms';
import { CameraPage } from './pages/devices/:deviceId/camera';
import { VolumePage } from './pages/devices/:deviceId/volume';
import { DeviceRunsPage } from './pages/devices/:deviceId/runs/index';
import { DeviceRunPage } from './pages/devices/:deviceId/runs/:slug/index';

export function App() {
  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', padding: '1rem' }}>
      <Switch>
        <Route path="/devices" component={DevicesPage} />
        <Route path="/devices/:deviceId" component={DevicePage} />
        <Route path="/devices/:deviceId/phone-state" component={PhoneStatePage} />
        <Route path="/devices/:deviceId/sms" component={SmsPage} />
        <Route path="/devices/:deviceId/camera" component={CameraPage} />
        <Route path="/devices/:deviceId/volume" component={VolumePage} />
        <Route path="/devices/:deviceId/runs" component={DeviceRunsPage} />
        <Route path="/devices/:deviceId/runs/:slug" component={DeviceRunPage} />
        <Route><Redirect to="/devices" /></Route>
      </Switch>
    </div>
  );
}
