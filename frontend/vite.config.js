import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Servidor de desarrollo de Vite para el panel de administración.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
  },
})
