/**
 * Axios 客户端配置
 * 统一的 HTTP 请求处理
 */

import axios, { type AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { apiConfig } from '@/config/app';
import { useSettingsStore } from '@/stores/settingsStore';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: apiConfig.baseUrl,
  timeout: apiConfig.timeout,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const { apiBaseUrl, apiKey, requestTimeout } = useSettingsStore.getState();

    if (apiBaseUrl) {
      config.baseURL = apiBaseUrl;
    }
    if (requestTimeout) {
      config.timeout = requestTimeout;
    }
    if (apiKey) {
      config.headers['x-api-key'] = apiKey;
    }

    // 添加请求 ID 用于追踪
    config.headers['X-Request-ID'] = crypto.randomUUID();
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<{ detail?: string }>) => {
    // 统一错误处理
    const message = error.response?.data?.detail || error.message || '请求失败';
    return Promise.reject(new Error(message));
  }
);

export default apiClient;
