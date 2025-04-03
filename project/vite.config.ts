import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  server: {
    proxy: {
      // Proxy API requests to the backend server during development
      '/ask': {
        target: 'http://localhost:8000', // Your FastAPI backend URL
        changeOrigin: true,
        // rewrite: (path) => path.replace(/^\/api/, '') // Only needed if you add /api prefix in fetch
      }
    }
  },
});
