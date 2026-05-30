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
  getStepStdoutApiRunsSlugStepsStepIndexStdoutGet,
  submitRunApiRunsPost,
  watchRunTerminal,
  type PhoneCommandInput,
  type RunRecord,
  type RunStatus,
} from '~/_api';
import { createDebugLogger } from '~/util/log';
import { parseJsonValues } from '~/util/jsonStream';

const log = createDebugLogger(import.meta.url);

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

function timeoutPromise(ms: number, slug: string, signal: AbortSignal): Promise<never> {
  return new Promise<never>((_, reject) => {
    const t = setTimeout(() => reject(
      new Error(`run ${slug} did not finish within ${ms}ms`),
    ), ms);
    signal.addEventListener('abort', () => clearTimeout(t), { once: true });
  });
}

async function runOnce(
  name: string,
  argv: string[],
  opt: FetchOptions,
  signal?: AbortSignal,
): Promise<RunRecord> {
  const t0 = performance.now();
  const slug = opt.slug;

  // Subscribe to SSE *before* submitting so we don't miss the terminal event
  // due to a race between the submit RTT and the run completing.
  const watchAc = new AbortController();
  const onOuterAbort = () => watchAc.abort();
  signal?.addEventListener('abort', onOuterAbort, { once: true });
  const terminalP = watchRunTerminal(slug, watchAc.signal);
  terminalP.catch(() => {}); // suppress unhandled rejection on cache-hit path

  try {
    const { data: initial } = await submitRunApiRunsPost({
      body: { phone_command: captureCommand(name, argv, opt) },
      throwOnError: true,
      signal,
    });

    let rec: RunRecord;
    if (isTerminal(initial.status)) {
      // Server returning a terminal record from submit = served from cache_for.
      log('%s cache-hit slug=%s status=%s', name, slug, initial.status);
      rec = initial;
    } else {
      log('%s spawn slug=%s', name, slug);
      await Promise.race([terminalP, timeoutPromise(DEFAULT_TIMEOUT_MS, slug, watchAc.signal)]);
      const r = await getRunApiRunsSlugGet({ path: { slug }, throwOnError: true, signal });
      rec = r.data;
    }
    log('%s done slug=%s status=%s in %dms',
      name, slug, rec.status, Math.round(performance.now() - t0));
    if (rec.status !== 'completed') {
      throw new Error(`${name} ${rec.status}${rec.error ? `: ${rec.error}` : ''}`);
    }
    return rec;
  } finally {
    watchAc.abort();
    signal?.removeEventListener('abort', onOuterAbort);
  }
}

// Termux-api commands sometimes "succeed" at the process level (exit 0,
// Run.status='completed') but report a domain-level failure in-band as
// `{"error": "..."}` on stdout — e.g. when an Android permission is denied.
// Recognize that shape so the card UI gets a useful message instead of a
// type cast lying about the payload (cf. doc/wits.md device-side gap).
function extractInBandError(parsed: unknown): string | null {
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
  const obj = parsed as Record<string, unknown>;
  const msg = obj.error ?? obj.API_ERROR;
  return typeof msg === 'string' ? msg : null;
}

async function fetchFullStdout(
  slug: string,
  stepIndex: number,
  signal?: AbortSignal,
): Promise<string> {
  // Use the dedicated streaming endpoint, not `Run.steps[i].stdout_tail` —
  // the latter is a 128 KiB tail for live observation, the former is the
  // full captured payload. See doc/design-process-management.md.
  const { data } = await getStepStdoutApiRunsSlugStepsStepIndexStdoutGet({
    path: { slug, step_index: stepIndex },
    throwOnError: true,
    signal,
  });
  return data;
}

async function runAndParse<T>(
  name: string,
  argv: string[],
  opt: FetchOptions,
  signal?: AbortSignal,
): Promise<T> {
  await runOnce(name, argv, opt, signal);
  const stdout = await fetchFullStdout(opt.slug, 0, signal);
  if (!stdout) {
    throw new Error(`${name} produced no stdout`);
  }
  let values: unknown[];
  try {
    values = parseJsonValues(stdout);
  } catch (e) {
    log('%s parse failed len=%d head=%j tail=%j',
      name, stdout.length, stdout.slice(0, 200), stdout.slice(-200));
    throw new Error(`${name} stdout is not JSON: ${(e as Error).message}`);
  }
  if (values.length === 0) {
    throw new Error(`${name} produced no JSON values`);
  }
  // Single value: termux-* commands typically emit one object/array.
  // Multi value: a process emitting JSONL — surface the array of values.
  const parsed = values.length === 1 ? values[0] : values;
  const inBandError = extractInBandError(parsed);
  if (inBandError !== null) {
    log('%s in-band error: %s', name, inBandError);
    throw new Error(`${name}: ${inBandError}`);
  }
  return parsed as T;
}

async function runAndCaptureRaw(
  name: string,
  argv: string[],
  opt: FetchOptions,
  signal?: AbortSignal,
): Promise<string> {
  await runOnce(name, argv, opt, signal);
  const stdout = await fetchFullStdout(opt.slug, 0, signal);
  // Trim trailing newline appended by termux-* commands.
  return stdout.replace(/\n$/, '');
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
export const fetchBattery = (signal?: AbortSignal) =>
  runAndParse<Battery>('battery-status', ['termux-battery-status'],
    { slug: 'battery-status', cacheFor: 5 }, signal);

export const fetchWifi = (signal?: AbortSignal) =>
  runAndParse<Wifi>('wifi-info', ['termux-wifi-connectioninfo'],
    { slug: 'wifi-info', cacheFor: 10 }, signal);

export const fetchLocation = (signal?: AbortSignal) =>
  runAndParse<Location>('location', ['termux-location'],
    { slug: 'location', cacheFor: 5 }, signal);

export const fetchTelephony = (signal?: AbortSignal) =>
  runAndParse<Telephony>('telephony', ['termux-telephony-deviceinfo'],
    { slug: 'telephony', cacheFor: 30 }, signal);

export const fetchSmsList = (signal?: AbortSignal) =>
  runAndParse<SmsMessage[]>('sms-list', ['termux-sms-list'],
    { slug: 'sms-list', cacheFor: 30 }, signal);

export const fetchCallLog = (signal?: AbortSignal) =>
  runAndParse<CallLogEntry[]>('call-log', ['termux-call-log'],
    { slug: 'call-log', cacheFor: 30 }, signal);

export const fetchCameras = (signal?: AbortSignal) =>
  runAndParse<CameraInfo[]>('camera-info', ['termux-camera-info'],
    { slug: 'camera-info', cacheFor: 600 }, signal);

export const fetchClipboard = (signal?: AbortSignal) =>
  runAndCaptureRaw('clipboard-get', ['termux-clipboard-get'],
    { slug: 'clipboard-get', cacheFor: 2 }, signal);

export const fetchVolume = (signal?: AbortSignal) =>
  runAndParse<VolumeEntry[]>('volume', ['termux-volume'],
    { slug: 'volume', cacheFor: 10 }, signal);
