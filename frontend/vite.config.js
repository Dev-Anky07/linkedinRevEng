import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      ignored: [
        '**/backend/**',
        '**/secrets/**',
        '**/.pytest_cache/**',
        '**/.venv/**',
      ],
    },
  },
})
