import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env variables from frontend directory and root directory
  const env = {
    ...loadEnv(mode, '..', ''),
    ...loadEnv(mode, process.cwd(), ''),
  }

  const backendTarget =
    env.VITE_API_BASE_URL ||
    env.VITE_API_URL ||
    env.BACKEND_URL ||
    'https://answer-writing-evaluation.onrender.com'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})

