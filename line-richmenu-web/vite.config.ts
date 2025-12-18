import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

// Vite config
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 將前端的 API 呼叫代理到 Node server
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist'
  }
});
