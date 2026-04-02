import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('pixi.js') || id.includes('pixi-viewport')) {
              return 'vendor-pixi';
            }
            if (
              id.includes('d3-force') ||
              id.includes('d3-dispatch') ||
              id.includes('d3-timer') ||
              id.includes('d3-quadtree')
            ) {
              return 'vendor-d3';
            }
            return 'vendor';
          }

          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setup_tests.ts',
    globals: true,
  },
});
