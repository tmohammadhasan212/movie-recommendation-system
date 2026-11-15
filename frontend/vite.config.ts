import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://api:8000', changeOrigin: false },
      '/health': { target: 'http://api:8000', changeOrigin: false }
    }
  }
});
