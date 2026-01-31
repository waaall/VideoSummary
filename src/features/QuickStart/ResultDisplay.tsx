/**
 * 结果展示组件
 */

import { useCallback, useMemo } from 'react';
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
import type { TraceEvent, ExecutionStatus } from '@/types/pipeline';
import { formatDuration, getNodeTypeName, getStatusName } from '@/utils/formatters';
import styles from './ResultDisplay.module.css';

interface ResultDisplayProps {
  status: ExecutionStatus;
  runId: string | null;
  summaryText: string | null;
  trace: TraceEvent[];
  error: string | null;
  onReset: () => void;
}

// 状态图标
const statusIcons: Record<string, React.ReactNode> = {
  running: <LoadingOutlined spin />,
  completed: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
};

// 状态颜色
const statusColors: Record<string, string> = {
  running: 'processing',
  completed: 'success',
  failed: 'error',
};

export function ResultDisplay({
  status,
  runId,
  summaryText,
  trace,
  error,
  onReset,
}: ResultDisplayProps) {
  const navigate = useNavigate();

  // 复制摘要
  const handleCopy = useCallback(async () => {
    if (!summaryText) return;

    try {
      await navigator.clipboard.writeText(summaryText);
      message.success('已复制到剪贴板');
    } catch {
      message.error('复制失败');
    }
  }, [summaryText]);

  // 导出 Markdown
  const handleExportMarkdown = useCallback(() => {
    if (!summaryText) return;

    const content = `# 视频摘要\n\n${summaryText}\n\n---\n*生成于 ${new Date().toLocaleString()}*`;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `summary-${runId || 'export'}.md`;
    link.click();

    URL.revokeObjectURL(url);
    message.success('已导出 Markdown 文件');
  }, [summaryText, runId]);

  // 查看详细追踪
  const handleViewTrace = useCallback(() => {
    if (runId) {
      navigate(`/execution/${runId}`);
    }
  }, [runId, navigate]);

  // 计算进度
  const progress = useMemo(() => {
    if (trace.length === 0) return { completed: 0, total: 0 };

    const completed = trace.filter(
      (t) => t.status === 'completed' || t.status === 'skipped'
    ).length;

    return { completed, total: trace.length };
  }, [trace]);

  // 如果是空闲状态，不显示
  if (status === 'idle') {
    return null;
  }

  return (
    <div className={styles.container}>
      {/* 执行状态 */}
      <div className={styles.statusSection}>
        <div className={styles.statusHeader}>
          <Tag
            icon={statusIcons[status]}
            color={statusColors[status]}
            className={styles.statusTag}
          >
            {status === 'running' ? '执行中' : status === 'completed' ? '已完成' : '执行失败'}
          </Tag>

          {runId && (
            <span className={styles.runId}>
              Run ID: <code>{runId}</code>
            </span>
          )}
        </div>

        {/* 执行追踪 */}
        <div className={styles.traceList}>
          {trace.map((event, index) => (
            <div
              key={`${event.node_id}-${index}`}
              className={`${styles.traceItem} ${styles[event.status]}`}
            >
              <span className={styles.traceIcon}>
                {event.status === 'completed' && '✓'}
                {event.status === 'failed' && '✗'}
                {event.status === 'skipped' && '○'}
                {event.status === 'started' && '●'}
              </span>
              <span className={styles.traceName}>{getNodeTypeName(event.node_id)}</span>
              <span className={styles.traceStatus}>{getStatusName(event.status)}</span>
              <span className={styles.traceTime}>{formatDuration(event.elapsed_ms)}</span>
            </div>
          ))}

          {status === 'running' && (
            <div className={`${styles.traceItem} ${styles.pending}`}>
              <span className={styles.traceIcon}>
                <LoadingOutlined spin />
              </span>
              <span className={styles.traceName}>处理中...</span>
            </div>
          )}
        </div>

        {/* 进度指示 */}
        {status === 'running' && progress.total > 0 && (
          <div className={styles.progressText}>
            已完成 {progress.completed} / {progress.total} 步骤
          </div>
        )}
      </div>

      {/* 错误信息 */}
      {error && (
        <div className={styles.errorSection}>
          <div className={styles.errorTitle}>错误信息</div>
          <div className={styles.errorContent}>{error}</div>
        </div>
      )}

      {/* 摘要结果 */}
      {summaryText && (
        <div className={styles.resultSection}>
          <div className={styles.resultHeader}>
            <span className={styles.resultTitle}>摘要结果</span>
            <Space>
              <Tooltip title="复制">
                <Button
                  type="text"
                  icon={<CopyOutlined />}
                  onClick={handleCopy}
                />
              </Tooltip>
              <Tooltip title="导出 Markdown">
                <Button
                  type="text"
                  icon={<FileMarkdownOutlined />}
                  onClick={handleExportMarkdown}
                />
              </Tooltip>
              <Tooltip title="查看详细追踪">
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={handleViewTrace}
                />
              </Tooltip>
            </Space>
          </div>

          <div className={styles.resultContent}>{summaryText}</div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className={styles.actions}>
        <Button
          icon={<ReloadOutlined />}
          onClick={onReset}
          disabled={status === 'running'}
        >
          重新开始
        </Button>

        {runId && status !== 'running' && (
          <Button type="primary" onClick={handleViewTrace}>
            查看详细执行记录
          </Button>
        )}
      </div>
    </div>
  );
}
