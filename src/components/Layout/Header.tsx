/**
 * 顶部导航栏组件
 */

import { Link, useLocation } from 'react-router-dom';
import { ThemeToggle } from '@/components/common';
import { appMeta } from '@/config';
import styles from './Header.module.css';

// Logo 图标
const LogoIcon = () => (
  <svg
    width="28"
    height="28"
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <rect
      x="2"
      y="6"
      width="28"
      height="20"
      rx="3"
      stroke="currentColor"
      strokeWidth="2"
    />
    <polygon
      points="13,11 13,21 22,16"
      fill="currentColor"
    />
  </svg>
);

// 导航项配置
const navItems = [
  { path: '/', label: '快速开始' },
  { path: '/execution', label: '执行监控' },
  { path: '/settings', label: '设置' },
];

export function Header() {
  const location = useLocation();

  return (
    <header className={styles.header}>
      <div className={styles.container}>
        {/* Logo 和标题 */}
        <Link to="/" className={styles.logo}>
          <LogoIcon />
          <span className={styles.title}>{appMeta.name}</span>
        </Link>

        {/* 导航链接 */}
        <nav className={styles.nav}>
          {navItems.map(({ path, label }) => {
            // 处理执行监控页面的路由匹配
            const isActive = path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(path);

            return (
              <Link
                key={path}
                to={path}
                className={`${styles.navLink} ${isActive ? styles.active : ''}`}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        {/* 右侧操作区 */}
        <div className={styles.actions}>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
