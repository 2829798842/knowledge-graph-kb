/**
 * 模块名称：vite.config
 * 主要功能：配置 Vite 开发服务与 Vitest 测试环境。
 */

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setup_tests.ts',
    globals: true,
  },
});
