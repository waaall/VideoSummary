/**
 * 历史列表项组件
 */

import { Tag, Tooltip } from 'antd';
import {
  LinkOutlined,
  FileOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import type { HistoryJob } from '@/types/history';
import { formatTimestamp } from '@/utils/formatters';
import styles from './HistoryListItem.module.css';

interface HistoryListItemProps {
  job: HistoryJob;
  isSelected: boolean;
  onClick: () => void;
  onDelete?: () => void;
}

// 状态图标映射
const statusIcons: Record<string, React.ReactNode> = {
  idle: <ClockCircleOutlined />,
  pending: <LoadingOutlined spin />,
  running: <LoadingOutlined spin />,
  completed: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
};

// 状态颜色映射
const statusColors: Record<string, string> = {
  idle: 'default',
  pending: 'processing',
  running: 'processing',
  completed: 'success',
  failed: 'error',
};

// 状态文本映射
const statusTexts: Record<string, string> = {
  idle: '等待中',
  pending: '排队中',
  running: '处理中',
  completed: '已完成',
  failed: '失败',
};

export function HistoryListItem({
  job,
  isSelected,
  onClick,
  onDelete,
}: HistoryListItemProps) {
  const isRunning = job.status === 'pending' || job.status === 'running';

  // 获取显示标题
  const displayTitle =
    job.title ||
    job.fileName ||
    (job.sourceUrl ? new URL(job.sourceUrl).hostname : null) ||
    job.jobId.slice(0, 8);

  // 获取来源描述
  const sourceDesc =
    job.sourceType === 'url'
      ? job.sourceUrl || 'URL 视频'
      : job.fileName || '本地文件';

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete?.();
  };

  return (
    <div
      className={`${styles.item} ${isSelected ? styles.selected : ''} ${isRunning ? styles.running : ''}`}
      onClick={onClick}
    >
      {/* 来源图标 */}
      <div className={styles.sourceIcon}>
        {job.sourceType === 'url' ? (
          <LinkOutlined />
        ) : (
          <FileOutlined />
        )}
      </div>

      {/* 主要内容 */}
      <div className={styles.content}>
        <div className={styles.titleRow}>
          <Tooltip title={sourceDesc}>
            <span className={styles.title}>{displayTitle}</span>
          </Tooltip>
          <Tag
            icon={statusIcons[job.status]}
            color={statusColors[job.status]}
            className={styles.statusTag}
          >
            {statusTexts[job.status]}
          </Tag>
        </div>

        <div className={styles.meta}>
          <span className={styles.jobId}>
            {job.jobId.slice(0, 12)}...
          </span>
          <span className={styles.time}>
            {formatTimestamp(job.updatedAt)}
          </span>
        </div>
      </div>

      {/* 删除按钮 */}
      {onDelete && !isRunning && (
        <Tooltip title="删除">
          <button
            className={styles.deleteBtn}
            onClick={handleDelete}
          >
            <DeleteOutlined />
          </button>
        </Tooltip>
      )}
    </div>
  );
}
