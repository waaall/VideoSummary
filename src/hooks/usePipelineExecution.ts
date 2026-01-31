/**
 * 管线执行 Hook
 * 封装执行流程和状态轮询
 */

import { useCallback } from 'react';
import { useExecutionStore } from '@/stores';
import { getRunStatus } from '@/api';
import { usePolling } from './usePolling';
import type { PipelineRunResponse } from '@/types/pipeline';

interface UsePipelineExecutionOptions {
  // 轮询间隔
  pollingInterval?: number;
  // 执行完成回调
  onComplete?: (result: PipelineRunResponse) => void;
  // 执行失败回调
  onError?: (error: string) => void;
}

export function usePipelineExecution(options: UsePipelineExecutionOptions = {}) {
  const {
    runId,
    status,
    summaryText,
    context,
    trace,
    error,
    currentNodeId,
    completedNodes,
    startExecution,
    updateStatus,
    updateLastUpdatedAt,
    updateTrace,
    updateContext,
    completeExecution,
    failExecution,
    reset,
  } = useExecutionStore();

  const { onComplete, onError, pollingInterval } = options;

  // 处理轮询数据
  const handlePollingData = useCallback(
    (data: PipelineRunResponse) => {
      updateTrace(data.trace);
      updateContext(data.context);
      updateLastUpdatedAt((data as { updated_at?: string }).updated_at || null);

      if (data.status === 'completed') {
        completeExecution(data);
        onComplete?.(data);
      } else if (data.status === 'failed') {
        const errorMsg = (data.context.error as string) || '执行失败';
        failExecution(errorMsg);
        onError?.(errorMsg);
      }
    },
    [updateTrace, updateContext, updateLastUpdatedAt, completeExecution, failExecution, onComplete, onError]
  );

  // 轮询配置
  const { start: startPolling, stop: stopPolling } = usePolling({
    fetcher: async () => {
      if (!runId) throw new Error('No run ID');
      const response = await getRunStatus(runId);
      return response.data;
    },
    onData: handlePollingData,
    onError: (err) => {
      console.error('轮询错误:', err);
    },
    shouldStop: (data) => data.status !== 'running',
    interval: pollingInterval,
    enabled: false, // 手动控制启动
  });

  /**
   * 处理执行响应
   * 初始化状态并启动轮询（如果需要）
   */
  const handleExecutionResponse = useCallback(
    (response: PipelineRunResponse) => {
      startExecution(response.run_id);
      updateTrace(response.trace);
      updateContext(response.context);

      if (response.status === 'running') {
        // 启动轮询
        startPolling();
      } else if (response.status === 'completed') {
        completeExecution(response);
        onComplete?.(response);
      } else {
        const errorMsg = (response.context.error as string) || '执行失败';
        failExecution(errorMsg);
        onError?.(errorMsg);
      }
    },
    [startExecution, updateTrace, updateContext, startPolling, completeExecution, failExecution, onComplete, onError]
  );

  /**
   * 取消执行（停止轮询）
   */
  const cancelExecution = useCallback(() => {
    stopPolling();
    updateStatus('idle');
  }, [stopPolling, updateStatus]);

  return {
    // 状态
    runId,
    status,
    summaryText,
    context,
    trace,
    error,
    currentNodeId,
    completedNodes,

    // 状态检查
    isIdle: status === 'idle',
    isRunning: status === 'running',
    isCompleted: status === 'completed',
    isFailed: status === 'failed',

    // Actions
    handleExecutionResponse,
    cancelExecution,
    reset,
  };
}
