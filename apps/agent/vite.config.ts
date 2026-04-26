import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const isTauriBuild = Boolean(process.env.TAURI_ENV_PLATFORM)

export default defineConfig({
  base: isTauriBuild ? './' : '/agent/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      '@surrogate-backend-model': resolve(__dirname, '../../services/surrogate-backend-model')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 4175,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/method-dev': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        timeout: 120000,
        proxyTimeout: 120000,
        rewrite: (path) => path.replace(/^\/method-dev/, '')
      }
    }
  }
})
