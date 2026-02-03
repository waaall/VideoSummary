/**
 * 主题切换组件
 */

import { Dropdown, Button } from 'antd';
import type { MenuProps } from 'antd';
import { useSettingsStore, getResolvedTheme } from '@/stores/settingsStore';
import type { ThemeMode } from '@/config/theme';
import styles from './ThemeToggle.module.css';

// 主题图标 SVG
const SunIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="5" />
    <line x1="12" y1="1" x2="12" y2="3" />
    <line x1="12" y1="21" x2="12" y2="23" />
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
    <line x1="1" y1="12" x2="3" y2="12" />
    <line x1="21" y1="12" x2="23" y2="12" />
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
  </svg>
);

const MoonIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
  </svg>
);

const SystemIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
    <line x1="8" y1="21" x2="16" y2="21" />
    <line x1="12" y1="17" x2="12" y2="21" />
  </svg>
);

const themeOptions: { key: ThemeMode; label: string; icon: React.ReactNode }[] = [
  { key: 'light', label: '浅色', icon: <SunIcon /> },
  { key: 'dark', label: '深色', icon: <MoonIcon /> },
  { key: 'system', label: '跟随系统', icon: <SystemIcon /> },
];

export function ThemeToggle() {
  const themeMode = useSettingsStore((state) => state.themeMode);
  const setThemeMode = useSettingsStore((state) => state.setThemeMode);

  const resolvedTheme = getResolvedTheme(themeMode);

  const items: MenuProps['items'] = themeOptions.map(({ key, label, icon }) => ({
    key,
    label: (
      <span className={styles.menuItem}>
        {icon}
        <span>{label}</span>
        {themeMode === key && <span className={styles.checkmark}>✓</span>}
      </span>
    ),
    onClick: () => setThemeMode(key),
  }));

  // 当前显示的图标
  const currentIcon = resolvedTheme === 'dark' ? <MoonIcon /> : <SunIcon />;

  return (
    <Dropdown menu={{ items }} trigger={['click']} placement="bottomRight">
      <Button
        type="text"
        className={styles.toggleButton}
        icon={currentIcon}
        aria-label="切换主题"
      />
    </Dropdown>
  );
}
