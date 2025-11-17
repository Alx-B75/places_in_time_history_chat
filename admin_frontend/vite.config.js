import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode, command }) => {
  // Default to writing into ../static_frontend for local integration with backend
  // Allow override for Render Static Site by setting VITE_OUT_DIR=dist
  const outDir = process.env.VITE_OUT_DIR || '../static_frontend'
  return {
    plugins: [react()],
    build: {
      outDir,
      emptyOutDir: outDir === 'dist'
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
      fs: { allow: ['..'] }
    }
  }
})