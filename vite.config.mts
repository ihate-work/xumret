import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vite';

// REMOTE_ADDR overrides the API proxy target (host:port or full URL). Set it
// from Makefile.var → `make webui-dev` to point the dev server at a remote
// xumret instance. Falls back to localhost:8080.
const remoteAddr = process.env.REMOTE_ADDR || '127.0.0.1:8080';
const DEV_PHONE_API_TARGET = /^https?:\/\//.test(remoteAddr)
  ? remoteAddr
  : `http://${remoteAddr}`;
console.log(`[vite] proxying /api → ${DEV_PHONE_API_TARGET}`);

export default defineConfig({
  root: path.join(__dirname, 'webui-src'),
  resolve: {
    alias: {
      '~': path.join(__dirname, 'webui-src'),
    },
  },
  build: {
    sourcemap: true,
    outDir: path.join(__dirname, 'webui-assets'),
    emptyOutDir: true,
    target: 'es2022',
  },
  server: {
    proxy: {
      '/api': {
        target: DEV_PHONE_API_TARGET,
      },
    },
  },
  plugins: [
    react(),
  ],
});
