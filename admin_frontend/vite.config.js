import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../static_frontend',
    emptyOutDir: false
  },
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/ops': 'http://localhost:8000',
      '/static': 'http://localhost:8000',
      '/guest/start': 'http://localhost:8000',
      '/guest/ask': 'http://localhost:8000',
  '/guest/upgrade': 'http://localhost:8000',
      '/figures': 'http://localhost:8000',
      '/threads': 'http://localhost:8000',
      '/ask': 'http://localhost:8000',
      // ensure user-scoped routes like /user/favorites proxy to backend in dev
      '/user': 'http://localhost:8000'
    },
    fs: { allow: [".."] },
    historyApiFallback: true
  }
})