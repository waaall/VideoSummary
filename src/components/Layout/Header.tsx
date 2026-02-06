/**
 * 顶部导航栏组件
 */

import { Link, useLocation } from 'react-router-dom';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { appMeta } from '@/config/app';
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

// 业务导航项（在 standalone 和 embedded 都保留）
const businessNavItems = [
  { path: '/', label: '快速开始' },
  { path: '/history', label: '历史任务' },
  { path: '/settings', label: '设置' },
];

interface HeaderProps {
  embedded?: boolean;
}

export function Header({ embedded = false }: HeaderProps) {
  const location = useLocation();
  const containerClassName = embedded
    ? `${styles.container} ${styles.containerEmbedded}`
    : styles.container;
  const navClassName = embedded
    ? `${styles.nav} ${styles.navEmbedded}`
    : styles.nav;

  return (
    <header className={styles.header}>
      <div className={containerClassName}>
        {!embedded && (
          // 全局项：Logo 和应用标题由 standalone 负责展示
          <Link to="/" className={styles.logo}>
            <LogoIcon />
            <span className={styles.title}>{appMeta.name}</span>
          </Link>
        )}

        {/* 业务项：应用内导航在双模式都展示 */}
        <nav className={navClassName}>
          {businessNavItems.map(({ path, label }) => {
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

        {!embedded && (
          // 全局项：主题等跨应用能力由 Portal 统一承接
          <div className={styles.actions}>
            <ThemeToggle />
          </div>
        )}
      </div>
    </header>
  );
}
