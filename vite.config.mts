import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vite';

const DEV_PHONE_HOST = '127.0.0.1';
const DEV_PHONE_API_PORT = 8080;
const DEV_PHONE_API_TARGET = `http://${DEV_PHONE_HOST}:${DEV_PHONE_API_PORT}`;

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
