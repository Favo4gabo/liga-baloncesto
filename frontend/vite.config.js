import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Servidor de desarrollo de Vite para el panel de administración.
// Las llamadas a /api se reenvían al backend para que frontend y API compartan
// origen y la cookie de sesión (SameSite=Lax) funcione con localhost, 127.0.0.1
// o la IP de red.
const apiTarget = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:5000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
