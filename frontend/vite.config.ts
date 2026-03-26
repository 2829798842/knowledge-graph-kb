/**
 * 模块名称：vite.config
 * 主要功能：配置 Vite 开发服务与 Vitest 测试环境。
 */

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom') || id.includes('@tanstack/react-query')) {
              return 'vendor-react';
            }
            if (id.includes('@tanstack/react-virtual')) {
              return 'vendor-virtual';
            }
            if (id.includes('cytoscape')) {
              return 'vendor-graph';
            }
            return 'vendor';
          }

          if (id.includes('/src/features/knowledge_base/graph_browser/')) {
            return 'panel-graph';
          }
          if (id.includes('/src/features/knowledge_base/query_studio/')) {
            return 'panel-query';
          }
          if (id.includes('/src/features/knowledge_base/import_center/')) {
            return 'panel-import';
          }
          if (id.includes('/src/features/knowledge_base/source_browser/')) {
            return 'panel-source';
          }
          if (id.includes('/src/features/knowledge_base/model_config/')) {
            return 'panel-config';
          }

          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Keep frontend API calls on the same origin during local dev.
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
