/**
 * 执行监控页面
 */

import { useEffect, useCallback } from 'react';
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
import { TraceTimeline } from './TraceTimeline';
import { ContextViewer } from './ContextViewer';
import { getRunStatus } from '@/api/execution';
import { useExecutionStore, getTotalElapsedMs } from '@/stores';
import { usePolling } from '@/hooks';
import { formatDuration } from '@/utils/formatters';
import styles from './ExecutionPage.module.css';

// 状态图标
const statusIcons: Record<string, React.ReactNode> = {
  idle: null,
  queued: <LoadingOutlined spin />,
  running: <LoadingOutlined spin />,
  completed: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
};

// 状态颜色
const statusColors: Record<string, string> = {
  idle: 'default',
  queued: 'processing',
  running: 'processing',
  completed: 'success',
  failed: 'error',
};

// 状态文本
const statusTexts: Record<string, string> = {
  idle: '空闲',
  queued: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '执行失败',
};

export function ExecutionPage() {
  const { runId: paramRunId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const {
    runId,
    status,
    summaryText,
    context,
    trace,
    error,
    startExecution,
    updateStatus,
    updateTrace,
    updateContext,
    updateRunMeta,
    completeExecution,
    failExecution,
  } = useExecutionStore();

  // 加载执行状态
  const loadStatus = useCallback(async () => {
    if (!paramRunId) return;

    try {
      const response = await getRunStatus(paramRunId);
      const data = response.data;

      // 初始化状态
      if (!runId || runId !== paramRunId) {
        startExecution(paramRunId, data.status);
      }

      updateTrace(data.trace);
      updateContext(data.context);
      updateRunMeta({
        createdAt: data.created_at ?? null,
        updatedAt: data.updated_at ?? null,
        startedAt: data.started_at ?? null,
        endedAt: data.ended_at ?? null,
      });

      if (data.status === 'completed') {
        completeExecution(data);
      } else if (data.status === 'failed') {
        failExecution(data.error || '执行失败');
      } else {
        updateStatus(data.status);
      }

      return data;
    } catch (err) {
      message.error('获取执行状态失败');
      throw err;
    }
  }, [
    paramRunId,
    runId,
    startExecution,
    updateStatus,
    updateTrace,
    updateContext,
    updateRunMeta,
    completeExecution,
    failExecution,
  ]);

  // 轮询配置
  const { start: startPolling, stop: stopPolling } = usePolling({
    fetcher: loadStatus,
    onData: () => {},
    shouldStop: (data) => data?.status === 'completed' || data?.status === 'failed',
    enabled: false,
  });

  // 初始加载
  useEffect(() => {
    if (paramRunId) {
      loadStatus().then((data) => {
        if (data?.status === 'running' || data?.status === 'queued') {
          startPolling();
        }
      });
    }

    return () => {
      stopPolling();
    };
  }, [paramRunId, loadStatus, startPolling, stopPolling]);

  // 复制 Run ID
  const handleCopyRunId = useCallback(async () => {
    if (!paramRunId) return;
    try {
      await navigator.clipboard.writeText(paramRunId);
      message.success('已复制 Run ID');
    } catch {
      message.error('复制失败');
    }
  }, [paramRunId]);

  // 刷新状态
  const handleRefresh = useCallback(() => {
    loadStatus();
  }, [loadStatus]);

  // 计算总耗时
  const totalElapsed = getTotalElapsedMs(trace);

  // 如果没有 runId，显示空状态
  if (!paramRunId) {
    return (
      <div className={styles.page}>
        <div className={styles.emptyContainer}>
          <Empty
            description="请从快速开始页面启动任务，或输入 Run ID 查看执行状态"
          />
          <Button
            type="primary"
            onClick={() => navigate('/')}
          >
            前往快速开始
          </Button>
        </div>
      </div>
    );
  }

  // Tab 配置
  const tabItems = [
    {
      key: 'timeline',
      label: '执行时间线',
      children: <TraceTimeline trace={trace} totalDuration={totalElapsed} />,
    },
    {
      key: 'context',
      label: '上下文数据',
      children: <ContextViewer context={context} />,
    },
    ...(summaryText
      ? [
          {
            key: 'summary',
            label: '摘要结果',
            children: (
              <div className={styles.summaryContent}>
                {summaryText}
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className={styles.page}>
      {/* 页面头部 */}
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
          disabled={status === 'running' || status === 'queued'}
        >
          刷新
        </Button>
      </div>

      {/* 状态卡片 */}
      <Card className={styles.statusCard}>
        <div className={styles.statusHeader}>
          <div className={styles.statusInfo}>
            <Tag
              icon={statusIcons[status]}
              color={statusColors[status]}
              className={styles.statusTag}
            >
              {statusTexts[status]}
            </Tag>

            <div className={styles.runIdContainer}>
              <span className={styles.runIdLabel}>Run ID:</span>
              <code className={styles.runIdValue}>{paramRunId}</code>
              <Button
                type="text"
                size="small"
                icon={<CopyOutlined />}
                onClick={handleCopyRunId}
              />
            </div>
          </div>

          <div className={styles.statusMeta}>
            <span className={styles.metaItem}>
              总耗时: <strong>{formatDuration(totalElapsed)}</strong>
            </span>
            <span className={styles.metaItem}>
              节点数: <strong>{trace.length}</strong>
            </span>
          </div>
        </div>

        {/* 错误信息 */}
        {error && (
          <div className={styles.errorSection}>
            <div className={styles.errorTitle}>错误信息</div>
            <div className={styles.errorContent}>{error}</div>
          </div>
        )}
      </Card>

      {/* 详细信息 Tabs */}
      <Card className={styles.detailCard}>
        <Tabs items={tabItems} defaultActiveKey="timeline" />
      </Card>
    </div>
  );
}
