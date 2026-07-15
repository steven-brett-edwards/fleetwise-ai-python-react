import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Dev proxy: forward /api to the local FastAPI backend so the frontend
      // can assume same-origin. Matches prod (StaticFiles mount on FastAPI).
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/main.tsx', // bootstrap only; the route wiring is pinned by App.test.tsx
        'src/vite-env.d.ts',
        'src/testing/**',
        'src/test-setup.ts',
        'src/**/*.test.{ts,tsx}',
      ],
      // Enforced floor, mirroring the backend's 90% ratchet: `npm test`
      // (which CI runs) fails if new code arrives untested.
      thresholds: { statements: 90, branches: 90, functions: 90, lines: 90 },
    },
  },
})
