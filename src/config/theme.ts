/**
 * 主题配置文件
 * 定义应用的明暗主题变量，支持自定义扩展
 */

export type ThemeMode = 'light' | 'dark' | 'system';

// 颜色配置接口
export interface ThemeColors {
  // 背景色
  bgPrimary: string;
  bgSecondary: string;
  bgTertiary: string;
  bgElevated: string;
  bgHover: string;

  // 文字色
  textPrimary: string;
  textSecondary: string;
  textTertiary: string;
  textInverse: string;

  // 强调色
  accentPrimary: string;
  accentSecondary: string;
  accentHover: string;

  // 状态色
  success: string;
  warning: string;
  error: string;
  info: string;

  // 边框色
  border: string;
  borderLight: string;
  borderFocus: string;

  // 特殊效果
  glassBg: string;
  glassBlur: string;
  shadowColor: string;
}

// 间距配置
export interface ThemeSpacing {
  xs: string;
  sm: string;
  md: string;
  lg: string;
  xl: string;
  xxl: string;
}

// 圆角配置
export interface ThemeRadius {
  sm: string;
  md: string;
  lg: string;
  xl: string;
  full: string;
}

// 字体配置
export interface ThemeFonts {
  sans: string;
  mono: string;
}

// 动画配置
export interface ThemeTransitions {
  fast: string;
  normal: string;
  slow: string;
  spring: string;
}

// 完整主题配置
export interface ThemeConfig {
  colors: ThemeColors;
  spacing: ThemeSpacing;
  radius: ThemeRadius;
  fonts: ThemeFonts;
  transitions: ThemeTransitions;
}

// 亮色主题
export const lightTheme: ThemeColors = {
  bgPrimary: '#f8fafc',
  bgSecondary: '#ffffff',
  bgTertiary: '#f1f5f9',
  bgElevated: '#ffffff',
  bgHover: '#e2e8f0',

  textPrimary: '#0f172a',
  textSecondary: '#475569',
  textTertiary: '#94a3b8',
  textInverse: '#ffffff',

  accentPrimary: '#0891b2',
  accentSecondary: '#06b6d4',
  accentHover: '#0e7490',

  success: '#10b981',
  warning: '#f59e0b',
  error: '#ef4444',
  info: '#3b82f6',

  border: '#e2e8f0',
  borderLight: '#f1f5f9',
  borderFocus: '#0891b2',

  glassBg: 'rgba(255, 255, 255, 0.8)',
  glassBlur: '12px',
  shadowColor: 'rgba(15, 23, 42, 0.08)',
};

// 暗色主题
export const darkTheme: ThemeColors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  bgElevated: '#1e293b',
  bgHover: '#334155',

  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  textInverse: '#0f172a',

  accentPrimary: '#22d3ee',
  accentSecondary: '#06b6d4',
  accentHover: '#67e8f9',

  success: '#34d399',
  warning: '#fbbf24',
  error: '#f87171',
  info: '#60a5fa',

  border: '#334155',
  borderLight: '#1e293b',
  borderFocus: '#22d3ee',

  glassBg: 'rgba(30, 41, 59, 0.8)',
  glassBlur: '12px',
  shadowColor: 'rgba(0, 0, 0, 0.3)',
};

// 共享配置（不随主题变化）
export const sharedConfig = {
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  } as ThemeSpacing,

  radius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  } as ThemeRadius,

  fonts: {
    sans: '"Geist Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    mono: '"JetBrains Mono", "SF Mono", "Fira Code", monospace',
  } as ThemeFonts,

  transitions: {
    fast: '150ms ease',
    normal: '250ms ease',
    slow: '400ms ease',
    spring: '300ms cubic-bezier(0.34, 1.56, 0.64, 1)',
  } as ThemeTransitions,
};

/**
 * 将主题配置转换为 CSS 变量字符串
 */
export function themeToCssVars(colors: ThemeColors): string {
  return `
    --color-bg-primary: ${colors.bgPrimary};
    --color-bg-secondary: ${colors.bgSecondary};
    --color-bg-tertiary: ${colors.bgTertiary};
    --color-bg-elevated: ${colors.bgElevated};
    --color-bg-hover: ${colors.bgHover};

    --color-text-primary: ${colors.textPrimary};
    --color-text-secondary: ${colors.textSecondary};
    --color-text-tertiary: ${colors.textTertiary};
    --color-text-inverse: ${colors.textInverse};

    --color-accent-primary: ${colors.accentPrimary};
    --color-accent-secondary: ${colors.accentSecondary};
    --color-accent-hover: ${colors.accentHover};

    --color-success: ${colors.success};
    --color-warning: ${colors.warning};
    --color-error: ${colors.error};
    --color-info: ${colors.info};

    --color-border: ${colors.border};
    --color-border-light: ${colors.borderLight};
    --color-border-focus: ${colors.borderFocus};

    --glass-bg: ${colors.glassBg};
    --glass-blur: ${colors.glassBlur};
    --shadow-color: ${colors.shadowColor};
  `;
}

/**
 * 获取 Ant Design 主题 token 配置
 */
export function getAntdThemeToken(isDark: boolean) {
  const colors = isDark ? darkTheme : lightTheme;

  return {
    colorPrimary: colors.accentPrimary,
    colorBgContainer: colors.bgSecondary,
    colorBgElevated: colors.bgElevated,
    colorBgLayout: colors.bgPrimary,
    colorText: colors.textPrimary,
    colorTextSecondary: colors.textSecondary,
    colorBorder: colors.border,
    colorSuccess: colors.success,
    colorWarning: colors.warning,
    colorError: colors.error,
    colorInfo: colors.info,
    borderRadius: 8,
    fontFamily: sharedConfig.fonts.sans,
    fontFamilyCode: sharedConfig.fonts.mono,
  };
}
