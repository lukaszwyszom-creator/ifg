import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const devApiTarget = process.env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8000';
const devPort = Number(process.env.PORT || 3000);

/** Przekierowuje /login → /ui/login (basename aplikacji). */
function uiPathRedirect() {
  return {
    name: 'ui-path-redirect',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const raw = req.url ?? '/';
        const path = raw.split('?')[0] || '/';
        const query = raw.includes('?') ? raw.slice(raw.indexOf('?')) : '';

        if (path.startsWith('/ui') || path.startsWith('/api') || path.startsWith('/@')) {
          next();
          return;
        }

        if (path.includes('.') && !path.endsWith('/')) {
          next();
          return;
        }

        const target = path === '/' ? '/ui/login' : `/ui${path.startsWith('/') ? path : `/${path}`}`;
        res.writeHead(302, { Location: `${target}${query}`, 'Cache-Control': 'no-store' });
        res.end();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), uiPathRedirect()],
  base: '/ui/',
  server: {
    host: '0.0.0.0',
    port: devPort,
    strictPort: true,
    hmr: {
      host: '192.168.1.50',
      clientPort: 3000,
      protocol: 'ws',
    },
    proxy: {
      '/api': {
        target: devApiTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
