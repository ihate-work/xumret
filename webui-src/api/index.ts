// Public API surface for webui consumers. Hooks below + the re-exported
// mutation functions and types form the complete interface — application
// code should import from './api', never from './api/generated' directly.
//
// SWR hooks are hand-written here instead of using the @hey-api/openapi-ts
// 'swr' plugin: v0.97.1 emits `import type useSWR` and drops path params.
// See openapi-ts.config.ts for the bypass note.

import useSWR, { type SWRConfiguration } from 'swr';

import {
  getRunApiRunsSlugGet,
  getRunStateApiRunsSlugStateGet,
  listDevicesApiDevicesGet,
  listRunsApiRunsGet,
} from './generated';

export {
  eventStreamApiEventsGet,
  reapRunApiRunsSlugReapPost,
  stopRunApiRunsSlugStopPost,
  submitRunApiRunsPost,
} from './generated';
export type {
  CommandStep,
  Device,
  PhoneCommandInput,
  PhoneCommandOutput,
  RunOption,
  RunRecord,
  RunStateCancelled,
  RunStateCompleted,
  RunStateCreated,
  RunStateFailed,
  RunStateRunning,
  RunStateStepExited,
  RunStateStepStarted,
  RunStateTimedOut,
  RunStatus,
  StepState,
  StreamConfig,
  SubmitRequest,
} from './generated';

export function useDevices(config?: SWRConfiguration) {
  return useSWR(
    '/api/devices',
    async () => {
      const { data } = await listDevicesApiDevicesGet({ throwOnError: true });
      return data;
    },
    config,
  );
}

export function useRuns(config?: SWRConfiguration) {
  return useSWR(
    '/api/runs',
    async () => {
      const { data } = await listRunsApiRunsGet({ throwOnError: true });
      return data;
    },
    config,
  );
}

// Pass `slug = null` to disable the fetch (standard SWR conditional-fetch pattern).
export function useRun(slug: string | null, config?: SWRConfiguration) {
  return useSWR(
    slug ? (['/api/runs', slug] as const) : null,
    async ([, s]) => {
      const { data } = await getRunApiRunsSlugGet({ path: { slug: s }, throwOnError: true });
      return data;
    },
    config,
  );
}

export function useRunState(slug: string | null, config?: SWRConfiguration) {
  return useSWR(
    slug ? (['/api/runs', slug, 'state'] as const) : null,
    async ([, s]) => {
      const { data } = await getRunStateApiRunsSlugStateGet({
        path: { slug: s },
        throwOnError: true,
      });
      return data;
    },
    config,
  );
}
