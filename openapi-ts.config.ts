import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: 'webui-src/api/openapi.yaml',
  output: 'webui-src/api/generated',
  // SWR hooks are hand-written in webui-src/api/index.tsx because the 'swr'
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
