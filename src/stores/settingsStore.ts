/**
 * 用户设置状态管理
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ThemeMode } from '@/config/theme';
import { apiConfig, defaultUiSettings } from '@/config/app';

interface SettingsState {
  // 主题设置
  themeMode: ThemeMode;

  // API 配置
  apiBaseUrl: string;
  apiKey: string;

  // 请求行为
  pollingInterval: number;
  requestTimeout: number;

  // 上传配置（前端校验）
  uploadMaxFileSizeMb: number;

  // Actions
  setThemeMode: (mode: ThemeMode) => void;
  setApiBaseUrl: (url: string) => void;
  setApiKey: (key: string) => void;
  setPollingInterval: (interval: number) => void;
  setRequestTimeout: (timeout: number) => void;
  setUploadMaxFileSizeMb: (sizeMb: number) => void;
  resetToDefaults: () => void;
}

// 默认设置状态
const defaultState = {
  themeMode: 'system' as ThemeMode,
  apiBaseUrl: apiConfig.baseUrl,
  apiKey: '',
  pollingInterval: defaultUiSettings.pollingInterval,
  requestTimeout: defaultUiSettings.requestTimeout,
  uploadMaxFileSizeMb: defaultUiSettings.uploadMaxFileSizeMb,
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      ...defaultState,

      setThemeMode: (mode) => {
        set({ themeMode: mode });
        // 更新 DOM 属性
        applyTheme(mode);
      },

      setApiBaseUrl: (url) => set({ apiBaseUrl: url }),
      setApiKey: (key) => set({ apiKey: key }),
      setPollingInterval: (interval) => set({ pollingInterval: interval }),
      setRequestTimeout: (timeout) => set({ requestTimeout: timeout }),
      setUploadMaxFileSizeMb: (sizeMb) => set({ uploadMaxFileSizeMb: sizeMb }),

      resetToDefaults: () => {
        set(defaultState);
        applyTheme(defaultState.themeMode);
      },
    }),
    {
      name: 'video-summary-settings',
      partialize: (state) => ({
        themeMode: state.themeMode,
        apiBaseUrl: state.apiBaseUrl,
        apiKey: state.apiKey,
        pollingInterval: state.pollingInterval,
        requestTimeout: state.requestTimeout,
        uploadMaxFileSizeMb: state.uploadMaxFileSizeMb,
      }),
    }
  )
);

/**
 * 应用主题到 DOM
 */
function applyTheme(mode: ThemeMode) {
  const root = document.documentElement;

  if (mode === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
  } else {
    root.setAttribute('data-theme', mode);
  }
}

/**
 * 获取当前实际主题（解析 system）
 */
export function getResolvedTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return mode;
}

/**
 * 监听系统主题变化
 */
export function setupThemeListener() {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

  const handleChange = () => {
    const { themeMode } = useSettingsStore.getState();
    if (themeMode === 'system') {
      applyTheme('system');
    }
  };

  mediaQuery.addEventListener('change', handleChange);
  return () => mediaQuery.removeEventListener('change', handleChange);
}

/**
 * 获取当前上传大小限制（字节）
 */
export function getUploadMaxFileSizeBytes() {
  const { uploadMaxFileSizeMb } = useSettingsStore.getState();
  const sizeMb = Number.isFinite(uploadMaxFileSizeMb) && uploadMaxFileSizeMb > 0
    ? uploadMaxFileSizeMb
    : defaultUiSettings.uploadMaxFileSizeMb;
  return Math.round(sizeMb * 1024 * 1024);
}
