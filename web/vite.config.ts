import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

function normalizeBasePath(input?: string): string {
  const value = (input || '/').trim();
  if (!value || value === '/') {
    return '/';
  }

  const withLeadingSlash = value.startsWith('/') ? value : `/${value}`;
  return withLeadingSlash.endsWith('/')
    ? withLeadingSlash
    : `${withLeadingSlash}/`;
}

function normalizeStorageNamespace(input?: string): string {
  const value = (input || 'video').trim();
  return value || 'video';
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const base = normalizeBasePath(env.VITE_BASE_PATH);
  const storageNamespace = normalizeStorageNamespace(env.VITE_STORAGE_NS);
  const devApiProxyTarget = (env.VITE_DEV_API_PROXY_TARGET || 'http://localhost:8765').trim();

  const injectRuntimeValuesPlugin = {
    name: 'inject-runtime-values',
    transformIndexHtml(html: string) {
      return html.replace(/__APP_STORAGE_NS__/g, storageNamespace);
    },
  };

  return {
    base,
    plugins: [react(), injectRuntimeValuesPlugin],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: devApiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
