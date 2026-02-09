/**
 * Axios 客户端配置
 * 统一的 HTTP 请求处理
 */

import axios, { type AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { apiConfig } from '@/config/app';
import { useSettingsStore } from '@/stores/settingsStore';

interface ApiErrorPayload {
  message?: string;
  detail?: string;
  code?: string;
  status?: number;
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
    config.headers['X-Request-Id'] = crypto.randomUUID();
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
    // 统一错误处理（优先读取 message，其次 detail）
    const payload = error.response?.data;
    const message = payload?.message || payload?.detail || error.message || '请求失败';
    return Promise.reject(new Error(message));
  }
);

export default apiClient;
