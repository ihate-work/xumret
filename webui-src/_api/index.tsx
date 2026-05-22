// Public API surface for webui consumers. The `useApi` hook + the re-exported
// mutation functions and types form the complete interface — application
// code should import from './api', never from './api/generated' directly.
//
// Note on SWR: we don't use the @hey-api/openapi-ts 'swr' plugin —
// v0.97.1 emits `import type useSWR` and drops path params. See
// openapi-ts.config.ts for the bypass note.

import { createContext, useContext, type ReactNode } from 'react';
import useSWR, { type SWRConfiguration, type SWRResponse } from 'swr';

import type { Client } from './generated/client';
import { client as defaultClient } from './generated/client.gen';

export * from './generated';
export * from './events';
export type { Client } from './generated/client';

// Context: lets a subtree override the HTTP client (tests, mocks, alternate
// base URLs). Default is the generated singleton, so most apps never need
// ApiProvider.
const ClientContext = createContext<Client>(defaultClient);

export function ApiProvider({ client, children }: { client: Client; children: ReactNode }) {
  return <ClientContext.Provider value={client}>{children}</ClientContext.Provider>;
}

// useApi(fn, args?, config?)
//
//   `Args<TFn>` extracts the SDK function's args bag (path/query/body/headers)
//   and strips the internal `client` / `throwOnError` we always provide.
//   `Data<TFn>` unwraps the SDK function's `data` field; `NonNullable` strips
//   the `data?:` optional that SDK fns ship with (we always set throwOnError).
//
//   Cache key is `[fn.name, args]` — SDK function names are stable, unique
//   per endpoint, and serializable.  No URL strings at the call site.
//
//   Pass `args = null` to disable the fetch (standard SWR conditional pattern).

type SdkFn = (options: any) => Promise<{ data?: unknown }>;
type Args<TFn extends SdkFn> = Omit<NonNullable<Parameters<TFn>[0]>, 'client' | 'throwOnError'>;
type Data<TFn extends SdkFn> = NonNullable<Awaited<ReturnType<TFn>>['data']>;

export function useApi<TFn extends SdkFn>(
  fn: TFn,
  args?: Args<TFn> | null,
  config?: SWRConfiguration<Data<TFn>>,
): SWRResponse<Data<TFn>> {
  const client = useContext(ClientContext);
  return useSWR<Data<TFn>>(
    args === null ? null : ([fn.name, args] as const),
    async () => {
      const res = await fn({ ...(args ?? {}), client, throwOnError: true });
      return res.data as Data<TFn>;
    },
    config,
  );
}
