import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // Local/Docker builds write straight into the API's static directory so a
    // single process serves everything. Static hosts (Vercel) set
    // BUILD_OUT_DIR=dist because they take the folder as deployment output.
    outDir: process.env.BUILD_OUT_DIR ?? '../backend/static',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
