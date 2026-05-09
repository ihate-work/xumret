import { Route, Switch, Redirect } from 'wouter';
import { DevicesPage } from './pages/devices/index';
import { DevicePage } from './pages/devices/:deviceId/index';
import { DeviceRunsPage } from './pages/devices/:deviceId/runs/index';
import { DeviceRunPage } from './pages/devices/:deviceId/runs/:slug/index';

export function App() {
  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', padding: '1rem' }}>
      <Switch>
        <Route path="/devices" component={DevicesPage} />
        <Route path="/devices/:deviceId" component={DevicePage} />
        <Route path="/devices/:deviceId/runs" component={DeviceRunsPage} />
        <Route path="/devices/:deviceId/runs/:slug" component={DeviceRunPage} />
        <Route><Redirect to="/devices" /></Route>
      </Switch>
    </div>
  );
}
