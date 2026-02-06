/**
 * Cookie 封装
 * 统一使用环境变量中的 Path，避免多应用互相覆盖
 */

import { runtimeConfig } from '@/config/runtime';

function encode(value: string): string {
  return encodeURIComponent(value);
}

function decode(value: string): string {
  return decodeURIComponent(value);
}

export function setCookie(name: string, value: string, maxAgeSec?: number): void {
  const maxAgePart = typeof maxAgeSec === 'number'
    ? `; Max-Age=${Math.max(0, Math.floor(maxAgeSec))}`
    : '';
  document.cookie = `${encode(name)}=${encode(value)}; Path=${runtimeConfig.cookiePath}; SameSite=Lax${maxAgePart}`;
}

export function getCookie(name: string): string | null {
  const target = `${encode(name)}=`;
  const cookieList = document.cookie ? document.cookie.split('; ') : [];

  for (const item of cookieList) {
    if (item.startsWith(target)) {
      return decode(item.slice(target.length));
    }
  }

  return null;
}

export function removeCookie(name: string): void {
  setCookie(name, '', 0);
}
