/**
 * 运行时配置
 * 统一管理 Portal 挂载相关环境变量
 */

function normalizeRouterBasename(input?: string): string {
  const value = (input || '/').trim();
  if (!value || value === '/') {
    return '/';
  }

  const withLeadingSlash = value.startsWith('/') ? value : `/${value}`;
  return withLeadingSlash.replace(/\/+$/, '');
}

function normalizeStorageNamespace(input?: string): string {
  const value = (input || 'video').trim();
  return value || 'video';
}

function normalizeCookiePath(input?: string): string {
  const value = (input || '/').trim();
  if (!value || value === '/') {
    return '/';
  }

  const withLeadingSlash = value.startsWith('/') ? value : `/${value}`;
  return withLeadingSlash.endsWith('/')
    ? withLeadingSlash
    : `${withLeadingSlash}/`;
}

export function getEmbeddedFlag(): boolean {
  if (import.meta.env.VITE_EMBEDDED === 'true') {
    return true;
  }

  try {
    return window.self !== window.top;
  } catch {
    return true;
  }
}

export const runtimeConfig = {
  routerBasename: normalizeRouterBasename(import.meta.env.VITE_ROUTER_BASENAME),
  embedded: getEmbeddedFlag(),
  storageNamespace: normalizeStorageNamespace(import.meta.env.VITE_STORAGE_NS),
  cookiePath: normalizeCookiePath(import.meta.env.VITE_COOKIE_PATH),
};
