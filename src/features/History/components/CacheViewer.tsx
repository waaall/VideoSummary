/**
 * 缓存信息查看器
 */

import { Empty, Spin } from 'antd';
import type { CacheEntryResponse } from '@/types/summary';
import styles from './CacheViewer.module.css';

interface CacheViewerProps {
  cacheEntry: CacheEntryResponse | null;
  loading?: boolean;
  error?: string | null;
}

export function CacheViewer({ cacheEntry, loading = false, error = null }: CacheViewerProps) {
  if (loading) {
    return (
      <div className={styles.container}>
        <Spin />
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>{error}</div>
      </div>
    );
  }

  if (!cacheEntry || Object.keys(cacheEntry).length === 0) {
    return (
      <div className={styles.container}>
        <Empty description="暂无缓存信息" />
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <pre className={styles.codeBlock}>{JSON.stringify(cacheEntry, null, 2)}</pre>
    </div>
  );
}
