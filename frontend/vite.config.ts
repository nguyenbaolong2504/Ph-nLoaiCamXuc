import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Read only the backend address into this server-side config. Database secrets
  // stay in the root .env and are never injected into the browser bundle.
  // npm start/build run in frontend/, so ../ is the repository root.
  const env = loadEnv(mode, '..', '');
  const backend = env.VITE_API_TARGET || `http://127.0.0.1:${env.APP_PORT || '8010'}`;
  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1', port: 5173, strictPort: true,
      proxy: { '/api': backend, '/ws': { target: backend.replace(/^http/, 'ws'), ws: true } },
    },
  };
});
