import { Route, Switch, Redirect } from 'wouter';
import { DevicesPage } from './pages/devices/index';
import { DevicePage } from './pages/devices/:deviceId/index';
import { DeviceCommandsPage } from './pages/devices/:deviceId/commands/index';
import { DeviceCommandPage } from './pages/devices/:deviceId/commands/:commandId/index';

export function App() {
  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', padding: '1rem' }}>
      <Switch>
        <Route path="/devices" component={DevicesPage} />
        <Route path="/devices/:deviceId" component={DevicePage} />
        <Route path="/devices/:deviceId/commands" component={DeviceCommandsPage} />
        <Route path="/devices/:deviceId/commands/:commandId" component={DeviceCommandPage} />
        <Route><Redirect to="/devices" /></Route>
      </Switch>
    </div>
  );
}
