import { Route, Switch, Redirect } from 'wouter';
import { DeviceList } from './pages/DeviceList';
import { DeviceState } from './pages/DeviceState';
import { CommandList } from './pages/CommandList';
import { CommandDetail } from './pages/CommandDetail';

export function App() {
  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', padding: '1rem' }}>
      <Switch>
        <Route path="/devices" component={DeviceList} />
        <Route path="/devices/:id" component={DeviceState} />
        <Route path="/devices/:id/commands" component={CommandList} />
        <Route path="/devices/:id/commands/:commandId" component={CommandDetail} />
        <Route><Redirect to="/devices" /></Route>
      </Switch>
    </div>
  );
}
