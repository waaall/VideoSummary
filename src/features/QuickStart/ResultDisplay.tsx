/**
 * 结果展示组件
 */

import { useCallback } from 'react';
import { Button, Space, message, Tooltip, Tag } from 'antd';
import {
  CopyOutlined,
  FileMarkdownOutlined,
  EyeOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { SummaryStatus } from '@/types/summary';
import styles from './ResultDisplay.module.css';

type UiStatus = 'idle' | SummaryStatus;

interface ResultDisplayProps {
  status: UiStatus;
  jobId: string | null;
  cacheStatus: string | null;
  cacheKey: string | null;
  summaryText: string | null;
  error: string | null;
  onReset: () => void;
}

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
  running: '处理中',
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

export function ResultDisplay({
  status,
  jobId,
  cacheStatus,
  cacheKey,
  summaryText,
  error,
  onReset,
}: ResultDisplayProps) {
  const navigate = useNavigate();

  const handleCopy = useCallback(async () => {
    if (!summaryText) return;

    try {
      await navigator.clipboard.writeText(summaryText);
      message.success('已复制到剪贴板');
    } catch {
      message.error('复制失败');
    }
  }, [summaryText]);

  const handleExportMarkdown = useCallback(() => {
    if (!summaryText) return;

    const content = `# 视频摘要\n\n${summaryText}\n\n---\n*生成于 ${new Date().toLocaleString()}*`;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `summary-${jobId || 'export'}.md`;
    link.click();

    URL.revokeObjectURL(url);
    message.success('已导出 Markdown 文件');
  }, [summaryText, jobId]);

  const handleViewDetail = useCallback(() => {
    if (jobId) {
      navigate(`/history/${jobId}`);
    }
  }, [jobId, navigate]);

  if (status === 'idle') {
    return null;
  }

  return (
    <div className={styles.container}>
      <div className={styles.statusSection}>
        <div className={styles.statusHeader}>
          <div className={styles.statusTags}>
            <Tag
              icon={statusIcons[status]}
              color={statusColors[status]}
              className={styles.statusTag}
            >
              {statusTexts[status]}
            </Tag>

            {cacheStatus && (
              <Tag
                color={cacheStatusColors[cacheStatus] || 'default'}
                className={styles.cacheTag}
              >
                缓存：{cacheStatusTexts[cacheStatus] || cacheStatus}
              </Tag>
            )}
          </div>

          {jobId && (
            <span className={styles.runId}>
              Job ID: <code>{jobId}</code>
            </span>
          )}
        </div>

        {cacheKey && (
          <div className={styles.cacheKey}>
            Cache Key: <code>{cacheKey}</code>
          </div>
        )}
      </div>

      {error && (
        <div className={styles.errorSection}>
          <div className={styles.errorTitle}>错误信息</div>
          <div className={styles.errorContent}>{error}</div>
        </div>
      )}

      {summaryText && (
        <div className={styles.resultSection}>
          <div className={styles.resultHeader}>
            <span className={styles.resultTitle}>摘要结果</span>
            <Space>
              <Tooltip title="复制">
                <Button type="text" icon={<CopyOutlined />} onClick={handleCopy} />
              </Tooltip>
              <Tooltip title="导出 Markdown">
                <Button type="text" icon={<FileMarkdownOutlined />} onClick={handleExportMarkdown} />
              </Tooltip>
              <Tooltip title="查看任务详情">
                <Button type="text" icon={<EyeOutlined />} onClick={handleViewDetail} />
              </Tooltip>
            </Space>
          </div>

          <div className={styles.resultContent}>{summaryText}</div>
        </div>
      )}

      <div className={styles.actions}>
        <Button
          icon={<ReloadOutlined />}
          onClick={onReset}
          disabled={status === 'pending' || status === 'running'}
        >
          重新开始
        </Button>

        {jobId && status !== 'pending' && status !== 'running' && (
          <Button type="primary" onClick={handleViewDetail}>
            查看任务详情
          </Button>
        )}
      </div>
    </div>
  );
}
