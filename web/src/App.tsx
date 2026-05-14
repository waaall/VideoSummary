/**
 * 应用根组件
 */

import { useEffect, useMemo, Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme as antdTheme, App as AntdApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { MainLayout } from '@/components/Layout/MainLayout';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { runtimeConfig } from '@/config/runtime';
import {
  useSettingsStore,
  getResolvedTheme,
  setupThemeListener,
} from '@/stores/settingsStore';
import { getAntdThemeToken } from '@/config/theme';

// 页面组件（懒加载）
const QuickStartPage = lazy(() =>
  import('@/features/QuickStart/QuickStartPage').then((m) => ({
    default: m.QuickStartPage,
  }))
);
const HistoryPage = lazy(() =>
  import('@/features/History/HistoryPage').then((m) => ({
    default: m.HistoryPage,
  }))
);
const SettingsPage = lazy(() =>
  import('@/features/Settings/SettingsPage').then((m) => ({
    default: m.SettingsPage,
  }))
);

// 页面加载占位
function PageLoader() {
  return <LoadingSpinner size="large" tip="加载中..." />;
}

export default function App() {
  const themeMode = useSettingsStore((state) => state.themeMode);

  // 监听系统主题变化
  useEffect(() => {
    const cleanup = setupThemeListener();
    return cleanup;
  }, []);

  // 计算当前实际主题
  const isDark = getResolvedTheme(themeMode) === 'dark';

  // Ant Design 主题配置
  const antdThemeConfig = useMemo(
    () => ({
      token: getAntdThemeToken(isDark),
      algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    }),
    [isDark]
  );

  return (
    <ConfigProvider theme={antdThemeConfig} locale={zhCN}>
      <AntdApp>
        <ErrorBoundary>
          <BrowserRouter basename={runtimeConfig.routerBasename}>
            <MainLayout embedded={runtimeConfig.embedded}>
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  {/* 快速开始 */}
                  <Route path="/" element={<QuickStartPage />} />

                  {/* 历史任务 */}
                  <Route path="/history" element={<HistoryPage />} />
                  <Route path="/history/:jobId" element={<HistoryPage />} />

                  {/* 设置 */}
                  <Route path="/settings" element={<SettingsPage />} />

                  {/* 404 重定向 */}
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Suspense>
            </MainLayout>
          </BrowserRouter>
        </ErrorBoundary>
      </AntdApp>
    </ConfigProvider>
  );
}
