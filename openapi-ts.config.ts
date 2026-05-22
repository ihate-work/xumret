import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: 'webui-src/_api/openapi.yaml',
  output: 'webui-src/_api/generated',
  // SWR hooks are hand-written in webui-src/_api/index.tsx because the 'swr'
  // plugin in v0.97.1 emits `import type useSWR` (unusable at runtime) and
  // does not thread path params through. Re-enable once a fix ships.
  plugins: [
    '@hey-api/typescript',
    {
      name: '@hey-api/sdk',
      operations: { strategy: 'flat' },
    },
    '@hey-api/client-fetch',
    'zod',
  ],
});
