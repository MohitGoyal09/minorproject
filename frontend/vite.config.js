import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Override with VITE_PROXY_TARGET when the API is not on the default port:
        //   VITE_PROXY_TARGET=http://127.0.0.1:8011 npm run dev
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})
