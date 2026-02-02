/**
 * 主布局组件
 */

import { ReactNode } from 'react';
import { Header } from './Header';
import styles from './MainLayout.module.css';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className={styles.layout}>
      <Header />
      <main className={styles.main}>
        <div className={styles.content}>{children}</div>
      </main>
      <footer className={styles.footer}>
        <span className={styles.footerText}>
          VideoSummary · 智能视频摘要工具
        </span>
      </footer>
    </div>
  );
}
