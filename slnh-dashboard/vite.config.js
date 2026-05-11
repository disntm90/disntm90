import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/disntm90/',
  build: {
    rollupOptions: {
      external: ['react', 'react-dom', 'recharts'],
      output: {
        globals: {
          react: 'React',
          'react-dom': 'ReactDOM',
          recharts: 'Recharts',
        },
      },
    },
  },
})
