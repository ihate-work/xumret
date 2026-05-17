/**
 * Device list client. Mirrors src/xumret/protocol/device.py.
 *
 * In single mode the backend returns a single device whose id/name is the
 * server's hostname. The id is what the UI routes on (/devices/:id).
 */

export interface Device {
  id: string;
  name: string;
}

export async function listDevices(): Promise<Device[]> {
  const resp = await fetch('/api/devices');
  if (!resp.ok) {
    throw new Error(`GET /api/devices: HTTP ${resp.status}`);
  }
  return resp.json();
}
