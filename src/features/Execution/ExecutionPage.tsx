/**
 * 执行监控页面
 */

import { useEffect, useCallback, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Tag, Button, Empty, Tabs, message } from 'antd';
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import { JobProgress } from './JobProgress';
import { CacheViewer } from './CacheViewer';
import { getJobStatus, getCacheEntry } from '@/api';
import { useSummaryJobStore, useSettingsStore } from '@/stores';
import { usePolling } from '@/hooks';
import { formatTimestamp } from '@/utils/formatters';
import type { CacheEntryResponse, JobStatusResponse } from '@/types/summary';
import styles from './ExecutionPage.module.css';

const statusIcons: Record<string, React.ReactNode> = {
  pending: <LoadingOutlined spin />,
  running: <LoadingOutlined spin />,
  completed: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
};

const statusColors: Record<string, string> = {
  pending: 'processing',
  running: 'processing',
  completed: 'success',
  failed: 'error',
};

const statusTexts: Record<string, string> = {
  pending: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '执行失败',
};

const cacheStatusColors: Record<string, string> = {
  pending: 'processing',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  unknown: 'default',
};

const cacheStatusTexts: Record<string, string> = {
  pending: '排队中',
  running: '处理中',
  completed: '已完成',
  failed: '失败',
  unknown: '未知',
};

export function ExecutionPage() {
  const { runId: paramJobId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const {
    jobId,
    status,
    summaryText,
    cacheStatus,
    cacheKey,
    error,
    createdAt,
    updatedAt,
    updateFromJob,
    reset,
  } = useSummaryJobStore();

  const pollingInterval = useSettingsStore((state) => state.pollingInterval);

  const [cacheEntry, setCacheEntry] = useState<CacheEntryResponse | null>(null);
  const [cacheLoading, setCacheLoading] = useState(false);
  const [cacheError, setCacheError] = useState<string | null>(null);

  const loadCacheEntry = useCallback(async (key: string) => {
    setCacheLoading(true);
    setCacheError(null);

    try {
      const response = await getCacheEntry(key);
      setCacheEntry(response.data);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '缓存信息获取失败';
      setCacheError(errorMsg);
    } finally {
      setCacheLoading(false);
    }
  }, []);

  const loadStatus = useCallback(async () => {
    if (!paramJobId) return;

    try {
      const response = await getJobStatus(paramJobId);
      const data = response.data;
      updateFromJob(data);
      return data;
    } catch (err) {
      message.error('获取任务状态失败');
      throw err;
    }
  }, [paramJobId, updateFromJob]);

  const handlePollingData = useCallback((data?: JobStatusResponse) => {
    void data;
  }, []);

  const shouldStopPolling = useCallback(
    (data?: JobStatusResponse) => data?.status === 'completed' || data?.status === 'failed',
    []
  );

  const { start: startPolling, stop: stopPolling } = usePolling({
    fetcher: loadStatus,
    onData: handlePollingData,
    shouldStop: shouldStopPolling,
    interval: pollingInterval,
    enabled: false,
  });

  useEffect(() => {
    reset();
    setCacheEntry(null);
    setCacheError(null);
    setCacheLoading(false);

    if (paramJobId) {
      loadStatus().then((data) => {
        if (data?.status === 'running' || data?.status === 'pending') {
          startPolling();
        }
      });
    }

    return () => {
      stopPolling();
    };
  }, [paramJobId, loadStatus, startPolling, stopPolling, reset]);

  useEffect(() => {
    const canLoadCache = cacheKey && (status === 'completed' || cacheStatus === 'completed');
    if (canLoadCache) {
      loadCacheEntry(cacheKey);
    }
  }, [cacheKey, status, cacheStatus, loadCacheEntry]);

  const handleCopyJobId = useCallback(async () => {
    if (!paramJobId) return;
    try {
      await navigator.clipboard.writeText(paramJobId);
      message.success('已复制 Job ID');
    } catch {
      message.error('复制失败');
    }
  }, [paramJobId]);

  const handleRefresh = useCallback(() => {
    loadStatus();
    if (cacheKey && (status === 'completed' || cacheStatus === 'completed')) {
      loadCacheEntry(cacheKey);
    }
  }, [loadStatus, cacheKey, status, cacheStatus, loadCacheEntry]);

  if (!paramJobId) {
    return (
      <div className={styles.page}>
        <div className={styles.emptyContainer}>
          <Empty description="请从快速开始页面启动任务，或输入 Job ID 查看执行状态" />
          <Button type="primary" onClick={() => navigate('/')}>前往快速开始</Button>
        </div>
      </div>
    );
  }

  const tabItems = [
    {
      key: 'progress',
      label: '任务进度',
      children: <JobProgress status={status} />,
    },
    {
      key: 'cache',
      label: '缓存信息',
      children: (
        <CacheViewer
          cacheEntry={cacheEntry}
          loading={cacheLoading}
          error={cacheError}
        />
      ),
    },
    ...(summaryText
      ? [
          {
            key: 'summary',
            label: '摘要结果',
            children: <div className={styles.summaryContent}>{summaryText}</div>,
          },
        ]
      : []),
  ];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/')}
          className={styles.backButton}
        >
          返回
        </Button>

        <h1 className={styles.title}>执行监控</h1>

        <Button
          icon={<ReloadOutlined />}
          onClick={handleRefresh}
          disabled={status === 'running' || status === 'pending'}
        >
          刷新
        </Button>
      </div>

      <Card className={styles.statusCard}>
        <div className={styles.statusHeader}>
          <div className={styles.statusInfo}>
            {status !== 'idle' && (
              <Tag
                icon={statusIcons[status]}
                color={statusColors[status]}
                className={styles.statusTag}
              >
                {statusTexts[status]}
              </Tag>
            )}

            {cacheStatus && (
              <Tag color={cacheStatusColors[cacheStatus] || 'default'}>
                缓存：{cacheStatusTexts[cacheStatus] || cacheStatus}
              </Tag>
            )}

            <div className={styles.runIdContainer}>
              <span className={styles.runIdLabel}>Job ID</span>
              <span className={styles.runIdValue}>{jobId || paramJobId}</span>
              <Button
                type="text"
                size="small"
                icon={<CopyOutlined />}
                onClick={handleCopyJobId}
              />
            </div>

            {cacheKey && (
              <div className={styles.runIdContainer}>
                <span className={styles.runIdLabel}>Cache Key</span>
                <span className={styles.runIdValue}>{cacheKey}</span>
              </div>
            )}
          </div>

          <div className={styles.statusMeta}>
            <div className={styles.metaItem}>
              创建时间: <strong>{formatTimestamp(createdAt)}</strong>
            </div>
            <div className={styles.metaItem}>
              更新时间: <strong>{formatTimestamp(updatedAt)}</strong>
            </div>
          </div>
        </div>

        {error && (
          <div className={styles.errorSection}>
            <div className={styles.errorTitle}>错误信息</div>
            <div className={styles.errorContent}>{error}</div>
          </div>
        )}
      </Card>

      <Card className={styles.detailCard}>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}
