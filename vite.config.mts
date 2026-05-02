import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  root: path.join(__dirname, 'webui-src'),
  build: {
    sourcemap: true,
    outDir: path.join(__dirname, 'webui-assets'),
    emptyOutDir: true,
    target: 'es2022',
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
      },
      '/ws': {
        target: 'http://localhost:8000',
        ws: true,
      },
    },
  },
  plugins: [
    tailwindcss(),
    react(),
  ],
});
