/**
 * 用户设置状态管理
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ThemeMode } from '@/config/theme';
import {
  apiConfig,
  defaultThresholds,
  defaultLLMConfig,
  defaultTranscribeConfig,
} from '@/config';

// LLM 配置类型
interface LLMConfig {
  model: string;
  maxTokens: number;
  prompt?: string;
}

// 转录配置类型
interface TranscribeConfig {
  model: string;
  language: string;
  needWordTimeStamp: boolean;
}

// 阈值配置类型
interface Thresholds {
  subtitleCoverageMin: number;
  transcriptTokenPerMinMin: number;
  audioRmsMaxForSilence: number;
}

interface SettingsState {
  // 主题设置
  themeMode: ThemeMode;

  // API 配置
  apiBaseUrl: string;

  // 阈值配置
  thresholds: Thresholds;

  // LLM 配置
  llmConfig: LLMConfig;

  // 转录配置
  transcribeConfig: TranscribeConfig;

  // Actions
  setThemeMode: (mode: ThemeMode) => void;
  setApiBaseUrl: (url: string) => void;
  updateThresholds: (thresholds: Partial<Thresholds>) => void;
  updateLLMConfig: (config: Partial<LLMConfig>) => void;
  updateTranscribeConfig: (config: Partial<TranscribeConfig>) => void;
  resetToDefaults: () => void;
}

// 默认设置状态
const defaultState = {
  themeMode: 'system' as ThemeMode,
  apiBaseUrl: apiConfig.baseUrl,
  thresholds: {
    subtitleCoverageMin: defaultThresholds.subtitleCoverageMin,
    transcriptTokenPerMinMin: defaultThresholds.transcriptTokenPerMinMin,
    audioRmsMaxForSilence: defaultThresholds.audioRmsMaxForSilence,
  },
  llmConfig: {
    model: defaultLLMConfig.model,
    maxTokens: defaultLLMConfig.maxTokens,
    prompt: defaultLLMConfig.prompt,
  },
  transcribeConfig: {
    model: defaultTranscribeConfig.model,
    language: defaultTranscribeConfig.language,
    needWordTimeStamp: defaultTranscribeConfig.needWordTimeStamp,
  },
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

      updateThresholds: (thresholds) =>
        set((state) => ({
          thresholds: { ...state.thresholds, ...thresholds },
        })),

      updateLLMConfig: (config) =>
        set((state) => ({
          llmConfig: { ...state.llmConfig, ...config },
        })),

      updateTranscribeConfig: (config) =>
        set((state) => ({
          transcribeConfig: { ...state.transcribeConfig, ...config },
        })),

      resetToDefaults: () => set(defaultState),
    }),
    {
      name: 'video-summary-settings',
      // 只持久化部分状态
      partialize: (state) => ({
        themeMode: state.themeMode,
        apiBaseUrl: state.apiBaseUrl,
        thresholds: state.thresholds,
        llmConfig: state.llmConfig,
        transcribeConfig: state.transcribeConfig,
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
