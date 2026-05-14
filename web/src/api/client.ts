/**
 * Axios 客户端配置
 * 统一的 HTTP 请求处理
 */

import axios, { type AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { apiConfig } from '@/config/app';
import { useSettingsStore } from '@/stores/settingsStore';

interface ApiErrorPayload {
  message?: unknown;
  detail?: unknown;
  errors?: unknown;
  code?: unknown;
  status?: unknown;
}

const ABSOLUTE_URL_PATTERN = /^([a-z][a-z\d+\-.]*:)?\/\//i;

function normalizeBaseUrl(input: string): string {
  const value = input.trim();
  if (!value) {
    return '';
  }
  return value.replace(/\/+$/, '');
}

function joinUrl(baseUrl: string, endpoint: string): string {
  if (!endpoint) {
    return endpoint;
  }
  if (ABSOLUTE_URL_PATTERN.test(endpoint)) {
    return endpoint;
  }

  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return normalizedBaseUrl
    ? `${normalizedBaseUrl}${normalizedEndpoint}`
    : normalizedEndpoint;
}

function detectClientPlatform(): 'web' | 'desktop' {
  if (typeof window === 'undefined') {
    return 'web';
  }
  const tauriWindow = window as Window & {
    __TAURI__?: unknown;
    __TAURI_INTERNALS__?: unknown;
  };
  return tauriWindow.__TAURI__ || tauriWindow.__TAURI_INTERNALS__
    ? 'desktop'
    : 'web';
}

function createRequestId(): string {
  const cryptoApi = globalThis.crypto;

  if (cryptoApi?.randomUUID) {
    return cryptoApi.randomUUID();
  }

  if (cryptoApi?.getRandomValues) {
    const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'));
    return [
      hex.slice(0, 4).join(''),
      hex.slice(4, 6).join(''),
      hex.slice(6, 8).join(''),
      hex.slice(8, 10).join(''),
      hex.slice(10, 16).join(''),
    ].join('-');
  }

  return `req-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function normalizeErrorText(value: unknown): string | undefined {
  if (typeof value === 'string') {
    const text = value.trim();
    return text || undefined;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const text = normalizeErrorText(item);
      if (text) {
        return text;
      }
    }
    return undefined;
  }

  if (value && typeof value === 'object') {
    const payload = value as Record<string, unknown>;
    const preferred =
      normalizeErrorText(payload.message) ??
      normalizeErrorText(payload.detail) ??
      normalizeErrorText(payload.msg) ??
      normalizeErrorText(payload.reason) ??
      normalizeErrorText(payload.type);
    if (preferred) {
      return preferred;
    }

    try {
      const serialized = JSON.stringify(value);
      return serialized === '{}' ? undefined : serialized;
    } catch {
      return undefined;
    }
  }

  return undefined;
}

// 创建 axios 实例
const apiClient = axios.create({
  timeout: apiConfig.timeout,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const { apiBaseUrl, authToken, requestTimeout } = useSettingsStore.getState();
    const effectiveBaseUrl = normalizeBaseUrl(apiBaseUrl || apiConfig.baseUrl);

    if (config.url) {
      config.url = joinUrl(effectiveBaseUrl, config.url);
      config.baseURL = undefined;
    }
    if (requestTimeout) {
      config.timeout = requestTimeout;
    }
    if (authToken) {
      config.headers.Authorization = `Bearer ${authToken}`;
    }

    // 统一接入规范请求头
    config.headers['X-Request-Id'] = createRequestId();
    config.headers['X-Client-Platform'] = detectClientPlatform();
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<ApiErrorPayload>) => {
    const payload = error.response?.data;
    const message =
      normalizeErrorText(payload?.message) ??
      normalizeErrorText(payload?.detail) ??
      normalizeErrorText(payload?.errors) ??
      normalizeErrorText(error.response?.statusText) ??
      normalizeErrorText(error.message) ??
      '请求失败';
    return Promise.reject(new Error(message));
  }
);

export default apiClient;
