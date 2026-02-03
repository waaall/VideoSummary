/**
 * 任务详情组件
 */

import { useEffect, useCallback, useState } from 'react';
import { Card, Tag, Button, Tabs, message, Tooltip, Space } from 'antd';
import {
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  CopyOutlined,
  FileMarkdownOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { JobProgress } from './JobProgress';
import { CacheViewer } from './CacheViewer';
import { getJobStatus, getCacheEntry } from '@/api';
import { useSettingsStore } from '@/stores';
import { usePolling } from '@/hooks';
import { formatTimestamp } from '@/utils/formatters';
import { isCacheHistoryJob, resolveCacheKey, resolveHistoryId } from '@/utils';
import type { HistoryJob } from '@/types/history';
import type { CacheEntryResponse, JobStatusResponse, SummaryStatus } from '@/types/summary';
import styles from './JobDetail.module.css';

interface JobDetailProps {
  job: HistoryJob;
  onUpdate?: (updates: Partial<HistoryJob>) => void;
}

// 状态配置
const statusIcons: Record<string, React.ReactNode> = {
  idle: <LoadingOutlined />,
  pending: <LoadingOutlined spin />,
  running: <LoadingOutlined spin />,
  completed: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
};

const statusColors: Record<string, string> = {
  idle: 'default',
  pending: 'processing',
  running: 'processing',
  completed: 'success',
  failed: 'error',
};

const statusTexts: Record<string, string> = {
  idle: '等待中',
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

export function JobDetail({ job, onUpdate }: JobDetailProps) {
  const pollingInterval = useSettingsStore((state) => state.pollingInterval);

  const [cacheEntry, setCacheEntry] = useState<CacheEntryResponse | null>(null);
  const [cacheLoading, setCacheLoading] = useState(false);
  const [cacheError, setCacheError] = useState<string | null>(null);
  const cacheKey = resolveCacheKey(job);
  const historyId = resolveHistoryId(job);
  const isCacheRecord = isCacheHistoryJob(job);
  const canLoadStatus = !!job.jobId && !isCacheRecord;

  // 加载缓存信息
  const loadCacheEntry = useCallback(async (key: string) => {
    setCacheLoading(true);
    setCacheError(null);

    try {
      const response = await getCacheEntry(key);
      const entry = response.data;
      setCacheEntry(entry);

      const summaryFromCache =
        entry && typeof entry.summary_text === 'string' ? entry.summary_text : undefined;
      if (summaryFromCache && !job.summaryText) {
        onUpdate?.({
          summaryText: summaryFromCache,
          status: job.status === 'completed' ? job.status : 'completed',
          cacheStatus: job.cacheStatus ?? 'completed',
        });
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '缓存信息获取失败';
      setCacheError(errorMsg);
    } finally {
      setCacheLoading(false);
    }
  }, [onUpdate, job.summaryText, job.status, job.cacheStatus]);

  // 加载任务状态
  const loadStatus = useCallback(async () => {
    const jobId = job.jobId;
    if (!canLoadStatus) {
      return undefined;
    }
    if (!jobId) {
      return undefined;
    }

    try {
      const response = await getJobStatus(jobId);
      const data = response.data;

      // 更新历史记录
      onUpdate?.({
        status: data.status,
        cacheKey: data.cache_key ?? undefined,
        cacheStatus: data.cache_status ?? undefined,
        summaryText: data.summary_text ?? undefined,
        error: data.error ?? undefined,
      });

      return data;
    } catch (err) {
      message.error('获取任务状态失败');
      throw err;
    }
  }, [job.jobId, onUpdate, canLoadStatus]);

  // 轮询处理
  const handlePollingData = useCallback((data?: JobStatusResponse) => {
    void data;
  }, []);

  const shouldStopPolling = useCallback(
    (data?: JobStatusResponse) =>
      data?.status === 'completed' || data?.status === 'failed',
    []
  );

  const { start: startPolling, stop: stopPolling } = usePolling({
    fetcher: loadStatus,
    onData: handlePollingData,
    shouldStop: shouldStopPolling,
    interval: pollingInterval,
    enabled: false,
  });

  // 初始化
  useEffect(() => {
    setCacheEntry(null);
    setCacheError(null);
    setCacheLoading(false);

    // 如果任务正在运行，启动轮询
    if (canLoadStatus && (job.status === 'pending' || job.status === 'running')) {
      loadStatus().then((data) => {
        if (data?.status === 'running' || data?.status === 'pending') {
          startPolling();
        }
      });
    }

    return () => {
      stopPolling();
    };
  }, [job.jobId, job.status, loadStatus, startPolling, stopPolling, canLoadStatus]);

  // 加载缓存
  useEffect(() => {
    const canLoadCache =
      cacheKey &&
      (job.status === 'completed' || job.cacheStatus === 'completed' || isCacheRecord);
    if (canLoadCache) {
      loadCacheEntry(cacheKey!);
    }
  }, [cacheKey, job.status, job.cacheStatus, loadCacheEntry, isCacheRecord]);

  // 复制 Job ID
  const handleCopyJobId = useCallback(async () => {
    const valueToCopy = job.jobId ?? historyId;
    if (!valueToCopy) {
      message.error('暂无可复制的 ID');
      return;
    }

    try {
      await navigator.clipboard.writeText(valueToCopy);
      message.success(job.jobId ? '已复制 Job ID' : '已复制记录 ID');
    } catch {
      message.error('复制失败');
    }
  }, [job.jobId, historyId]);

  // 复制摘要
  const handleCopySummary = useCallback(async () => {
    if (!job.summaryText) return;
    try {
      await navigator.clipboard.writeText(job.summaryText);
      message.success('已复制到剪贴板');
    } catch {
      message.error('复制失败');
    }
  }, [job.summaryText]);

  // 导出 Markdown
  const handleExportMarkdown = useCallback(() => {
    if (!job.summaryText) return;

    const content = `# 视频摘要\n\n${job.summaryText}\n\n---\n*生成于 ${new Date().toLocaleString()}*`;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const exportId = job.jobId ?? historyId ?? 'summary';

    const link = document.createElement('a');
    link.href = url;
    link.download = `summary-${exportId.slice(0, 8)}.md`;
    link.click();

    URL.revokeObjectURL(url);
    message.success('已导出 Markdown 文件');
  }, [job.summaryText, job.jobId, historyId]);

  // 刷新
  const handleRefresh = useCallback(() => {
    if (canLoadStatus) {
      loadStatus();
    }
    if (cacheKey && (job.status === 'completed' || job.cacheStatus === 'completed' || isCacheRecord)) {
      loadCacheEntry(cacheKey);
    }
  }, [loadStatus, cacheKey, job.status, job.cacheStatus, loadCacheEntry, canLoadStatus, isCacheRecord]);

  const isRunning = canLoadStatus && (job.status === 'pending' || job.status === 'running');

  // Tab 项配置
  const tabItems = [
    {
      key: 'progress',
      label: '任务进度',
      children: <JobProgress status={job.status as SummaryStatus | 'idle'} />,
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
    ...(job.summaryText
      ? [
          {
            key: 'summary',
            label: '摘要结果',
            children: (
              <div className={styles.summarySection}>
                <div className={styles.summaryActions}>
                  <Space>
                    <Tooltip title="复制">
                      <Button
                        type="text"
                        icon={<CopyOutlined />}
                        onClick={handleCopySummary}
                      />
                    </Tooltip>
                    <Tooltip title="导出 Markdown">
                      <Button
                        type="text"
                        icon={<FileMarkdownOutlined />}
                        onClick={handleExportMarkdown}
                      />
                    </Tooltip>
                  </Space>
                </div>
                <div className={styles.summaryContent}>
                  <div className={styles.markdown}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {job.summaryText}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className={styles.container}>
      {/* 头部操作栏 */}
      <div className={styles.header}>
        <h2 className={styles.title}>任务详情</h2>
        <Button
          icon={<ReloadOutlined />}
          onClick={handleRefresh}
          disabled={isRunning}
        >
          刷新
        </Button>
      </div>

      {/* 状态卡片 */}
      <Card className={styles.statusCard}>
        <div className={styles.statusHeader}>
          <div className={styles.statusInfo}>
            <Tag
              icon={statusIcons[job.status]}
              color={statusColors[job.status]}
              className={styles.statusTag}
            >
              {statusTexts[job.status]}
            </Tag>

            {job.cacheStatus && (
              <Tag color={cacheStatusColors[job.cacheStatus] || 'default'}>
                缓存：{cacheStatusTexts[job.cacheStatus] || job.cacheStatus}
              </Tag>
            )}

            {(job.jobId || historyId) && (
              <div className={styles.idContainer}>
                <span className={styles.idLabel}>{job.jobId ? 'Job ID' : '记录 ID'}</span>
                <span className={styles.idValue}>{job.jobId ?? historyId}</span>
                <Button
                  type="text"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={handleCopyJobId}
                />
              </div>
            )}

            {cacheKey && (
              <div className={styles.idContainer}>
                <span className={styles.idLabel}>Cache Key</span>
                <span className={styles.idValue}>{cacheKey}</span>
              </div>
            )}
          </div>

          <div className={styles.statusMeta}>
            <div className={styles.metaItem}>
              来源：
              <strong>
                {job.sourceType === 'url' ? 'URL 视频' : '本地文件'}
              </strong>
            </div>
            {job.sourceUrl && (
              <div className={styles.metaItem}>
                URL：<strong className={styles.urlValue}>{job.sourceUrl}</strong>
              </div>
            )}
            {job.fileName && (
              <div className={styles.metaItem}>
                文件：<strong>{job.fileName}</strong>
              </div>
            )}
            <div className={styles.metaItem}>
              创建时间：<strong>{formatTimestamp(job.createdAt)}</strong>
            </div>
            <div className={styles.metaItem}>
              更新时间：<strong>{formatTimestamp(job.updatedAt)}</strong>
            </div>
          </div>
        </div>

        {job.error && (
          <div className={styles.errorSection}>
            <div className={styles.errorTitle}>错误信息</div>
            <div className={styles.errorContent}>{job.error}</div>
          </div>
        )}
      </Card>

      {/* 详细信息 */}
      <Card className={styles.detailCard}>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}
