/**
 * Device state fetchers built on top of the Run lifecycle.
 *
 * There is no dedicated "/api/devices/:id/battery" endpoint by design —
 * obtaining device state is just a regular PhoneCommand whose stdout the UI
 * parses. This module wraps that pattern: submit a one-shot termux-* command,
 * poll until terminal, parse JSON from stdout_tail.
 *
 * TODO: each call here re-runs the command. When stale-while-revalidate
 * support lands in RunOption (see executor/models.py), pass a cache_for value
 * here so cheap polls (battery, wifi) are cached server-side.
 */

import {
  getRunApiRunsSlugGet,
  submitRunApiRunsPost,
  type PhoneCommandInput,
  type RunRecord,
  type RunStatus,
} from '~/_api';

const POLL_INTERVAL_MS = 200;
const DEFAULT_TIMEOUT_MS = 15_000;
const TERMINAL: ReadonlyArray<RunStatus> = ['completed', 'failed', 'cancelled', 'timed_out'];
const isTerminal = (s: RunStatus) => TERMINAL.includes(s);

function captureCommand(name: string, argv: string[]): PhoneCommandInput {
  return {
    name,
    steps: [{ argv, stdout_stream: { mode: 'lines', capture: true } }],
  };
}

async function waitForTerminal(slug: string, timeoutMs: number): Promise<RunRecord> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const { data: rec } = await getRunApiRunsSlugGet({
      path: { slug }, throwOnError: true,
    });
    if (isTerminal(rec.status)) return rec;
    if (Date.now() > deadline) {
      throw new Error(`run ${slug} did not finish within ${timeoutMs}ms`);
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }
}

async function runOnce(name: string, argv: string[]): Promise<RunRecord> {
  const { data: initial } = await submitRunApiRunsPost({
    body: { phone_command: captureCommand(name, argv) },
    throwOnError: true,
  });
  const rec = isTerminal(initial.status)
    ? initial
    : await waitForTerminal(initial.slug, DEFAULT_TIMEOUT_MS);
  if (rec.status !== 'completed') {
    throw new Error(`${name} ${rec.status}${rec.error ? `: ${rec.error}` : ''}`);
  }
  return rec;
}

async function runAndParse<T>(name: string, argv: string[]): Promise<T> {
  const rec = await runOnce(name, argv);
  const tail = rec.steps[0]?.stdout_tail ?? '';
  if (!tail) {
    throw new Error(`${name} produced no stdout`);
  }
  try {
    return JSON.parse(tail) as T;
  } catch (e) {
    throw new Error(`${name} stdout is not JSON: ${(e as Error).message}`);
  }
}

async function runAndCaptureRaw(name: string, argv: string[]): Promise<string> {
  const rec = await runOnce(name, argv);
  // Trim trailing newline appended by the run-output joiner.
  return (rec.steps[0]?.stdout_tail ?? '').replace(/\n$/, '');
}

// --- typed slices ---

export interface Battery {
  health: string;
  percentage: number;
  plugged: string;
  status: string;
  temperature: number;
  current: number;
}

export interface Wifi {
  bssid: string;
  frequency_mhz: number;
  ip: string;
  link_speed_mbps: number;
  rssi: number;
  ssid: string;
  supplicant_state: string;
}

export interface Location {
  latitude: number;
  longitude: number;
  altitude: number;
  accuracy: number;
  bearing: number;
  speed: number;
  provider: string;
}

export interface Telephony {
  data_enabled: string;
  data_state: string;
  device_id: string;
  device_software_version: string;
  network_operator: string;
  network_operator_name: string;
  network_type: string;
  phone_type: string;
  sim_operator: string;
  sim_operator_name: string;
  sim_state: string;
}

export interface SmsMessage {
  threadid: number;
  type: string;
  read: boolean;
  number: string;
  body: string;
  received: string;
}

export interface Contact {
  name: string;
  number: string;
}

export interface CallLogEntry {
  name: string;
  phone_number: string;
  type: string;
  date: string;
  duration: string;
}

export interface CameraInfo {
  id: string;
  facing: string;
  jpeg_output_sizes: { width: number; height: number }[];
}

export interface VolumeEntry {
  stream: string;
  volume: number;
  max_volume: number;
}

export const fetchBattery = () =>
  runAndParse<Battery>('battery-status', ['termux-battery-status']);

export const fetchWifi = () =>
  runAndParse<Wifi>('wifi-info', ['termux-wifi-connectioninfo']);

export const fetchLocation = () =>
  runAndParse<Location>('location', ['termux-location']);

export const fetchTelephony = () =>
  runAndParse<Telephony>('telephony', ['termux-telephony-deviceinfo']);

export const fetchSmsList = () =>
  runAndParse<SmsMessage[]>('sms-list', ['termux-sms-list']);

export const fetchContacts = () =>
  runAndParse<Contact[]>('contact-list', ['termux-contact-list']);

export const fetchCallLog = () =>
  runAndParse<CallLogEntry[]>('call-log', ['termux-call-log']);

export const fetchCameras = () =>
  runAndParse<CameraInfo[]>('camera-info', ['termux-camera-info']);

export const fetchClipboard = () =>
  runAndCaptureRaw('clipboard-get', ['termux-clipboard-get']);

export const fetchVolume = () =>
  runAndParse<VolumeEntry[]>('volume', ['termux-volume']);
