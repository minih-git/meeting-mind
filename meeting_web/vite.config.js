import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '')

  return {
    base: env.VITE_APP_BASE || '/',
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 9529,
      allowedHosts: true,   
      cors: true,
      headers: {
        'Access-Control-Allow-Origin': '*'
      },
      proxy: {
        '/api': {
          target: 'http://localhost:9528',
          changeOrigin: true,
          secure: false,
        },
        '/ws': {
          target: 'ws://localhost:9528',
          ws: true,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/ws/, '') // 可选：重写路径
        },
      }
    }
  }
})
