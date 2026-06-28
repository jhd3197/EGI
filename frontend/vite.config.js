import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During `npm run dev` the API lives on the Python server (port 3000).
// We proxy the API routes so the app can use same-origin relative URLs
// (e.g. fetch('/persons')) in both dev and production.
const API_TARGET = process.env.EGI_API_TARGET || 'http://localhost:3000'
const apiRoutes = ['/persons', '/sync', '/import', '/health', '/uploads', '/operations']

export default defineConfig({
  plugins: [react()],
  // Relative base so the built assets work when FastAPI serves dist/ at the domain root.
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // Keep the bundle compatible with the Android 11 (API 30) emulator WebView
    // (~Chrome 83) so the PWA mounts reliably in instrumented/smoke tests.
    target: ['es2020', 'chrome80', 'edge88', 'firefox78', 'safari14'],
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      apiRoutes.map((r) => [r, { target: API_TARGET, changeOrigin: true }])
    ),
  },
})
