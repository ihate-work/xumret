/**
 * Device state fetchers built on top of the Run lifecycle.
 *
 * There is no dedicated "/api/devices/:id/battery" endpoint by design —
 * obtaining device state is just a regular PhoneCommand whose stdout the UI
 * parses. This module wraps that pattern: submit a one-shot termux-* command,
 * poll until terminal, parse JSON from stdout_tail.
 *
 * Run lifecycle, slug semantics, and the submit decision matrix (including
 * how `slug`, `mutex_by_slug`, and `cache_for` compose) are documented in
 * [doc/design-process-management.md](../../doc/design-process-management.md).
 * Each fetcher below declares a stable `slug` so the server can dedupe
 * repeated submissions, and a `cache_for` window so the same record is
 * served back without re-running termux-* on every UI render. Mutex is left
 * off so concurrent components share an in-flight refresh instead of 409ing.
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

interface FetchOptions {
  slug: string;
  cacheFor: number;
}

function captureCommand(name: string, argv: string[], opt: FetchOptions): PhoneCommandInput {
  return {
    name,
    steps: [{ argv, stdout_stream: { mode: 'lines', capture: true } }],
    run_option: { slug: opt.slug, cache_for: opt.cacheFor },
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

async function runOnce(name: string, argv: string[], opt: FetchOptions): Promise<RunRecord> {
  const { data: initial } = await submitRunApiRunsPost({
    body: { phone_command: captureCommand(name, argv, opt) },
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

async function runAndParse<T>(name: string, argv: string[], opt: FetchOptions): Promise<T> {
  const rec = await runOnce(name, argv, opt);
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

async function runAndCaptureRaw(name: string, argv: string[], opt: FetchOptions): Promise<string> {
  const rec = await runOnce(name, argv, opt);
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

// Per-fetcher cache windows. Tuned by how fast the underlying state moves
// vs. how cheap the termux-* call is. Tighter where the user expects a
// freshly-refreshed value; looser where state is near-constant.
export const fetchBattery = () =>
  runAndParse<Battery>('battery-status', ['termux-battery-status'],
    { slug: 'battery-status', cacheFor: 5 });

export const fetchWifi = () =>
  runAndParse<Wifi>('wifi-info', ['termux-wifi-connectioninfo'],
    { slug: 'wifi-info', cacheFor: 10 });

export const fetchLocation = () =>
  runAndParse<Location>('location', ['termux-location'],
    { slug: 'location', cacheFor: 5 });

export const fetchTelephony = () =>
  runAndParse<Telephony>('telephony', ['termux-telephony-deviceinfo'],
    { slug: 'telephony', cacheFor: 30 });

export const fetchSmsList = () =>
  runAndParse<SmsMessage[]>('sms-list', ['termux-sms-list'],
    { slug: 'sms-list', cacheFor: 30 });

export const fetchContacts = () =>
  runAndParse<Contact[]>('contact-list', ['termux-contact-list'],
    { slug: 'contact-list', cacheFor: 300 });

export const fetchCallLog = () =>
  runAndParse<CallLogEntry[]>('call-log', ['termux-call-log'],
    { slug: 'call-log', cacheFor: 30 });

export const fetchCameras = () =>
  runAndParse<CameraInfo[]>('camera-info', ['termux-camera-info'],
    { slug: 'camera-info', cacheFor: 600 });

export const fetchClipboard = () =>
  runAndCaptureRaw('clipboard-get', ['termux-clipboard-get'],
    { slug: 'clipboard-get', cacheFor: 2 });

export const fetchVolume = () =>
  runAndParse<VolumeEntry[]>('volume', ['termux-volume'],
    { slug: 'volume', cacheFor: 10 });
