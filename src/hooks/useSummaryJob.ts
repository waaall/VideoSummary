/**
 * 摘要任务 Hook
 * 封装创建摘要与轮询逻辑
 */

import { useCallback } from 'react';
import { useSummaryJobStore, useSettingsStore } from '@/stores';
import { createSummary, getJobStatus } from '@/api';
import { usePolling } from './usePolling';
import type { SummaryCreateRequest, JobStatusResponse } from '@/types/summary';

interface UseSummaryJobOptions {
  pollingInterval?: number;
  onComplete?: (summaryText: string | null) => void;
  onError?: (error: string) => void;
}

export function useSummaryJob(options: UseSummaryJobOptions = {}) {
  const {
    jobId,
    status,
    cacheKey,
    cacheStatus,
    summaryText,
    error,
    createdAt,
    updatedAt,
    startJob,
    updateFromJob,
    completeFromSummary,
    failJob,
    reset,
  } = useSummaryJobStore();

  const pollingIntervalSetting = useSettingsStore((state) => state.pollingInterval);
  const { onComplete, onError } = options;
  const pollingInterval = options.pollingInterval ?? pollingIntervalSetting;

  const handlePollingData = useCallback(
    (data: JobStatusResponse) => {
      updateFromJob(data);

      if (data.status === 'completed') {
        onComplete?.(data.summary_text ?? null);
        return;
      }

      if (data.status === 'failed') {
        const errorMsg = data.error || '任务失败';
        if (!data.error) {
          failJob(errorMsg);
        }
        onError?.(errorMsg);
      }
    },
    [updateFromJob, onComplete, onError, failJob]
  );

  const { start: startPolling, stop: stopPolling } = usePolling({
    fetcher: async () => {
      const currentJobId = useSummaryJobStore.getState().jobId;
      if (!currentJobId) {
        throw new Error('No job ID');
      }
      const response = await getJobStatus(currentJobId);
      return response.data;
    },
    onData: handlePollingData,
    onError: (err) => {
      console.error('轮询错误:', err);
    },
    shouldStop: (data) => data.status === 'completed' || data.status === 'failed',
    interval: pollingInterval,
    enabled: false,
  });

  const submitSummary = useCallback(
    async (request: SummaryCreateRequest) => {
      const response = await createSummary(request);

      if (response.status === 'completed') {
        completeFromSummary(response);
        onComplete?.(response.summary_text ?? null);
        return response;
      }

      if (!response.job_id) {
        throw new Error('响应缺少 job_id');
      }

      startJob(response.job_id, response.cache_key, 'pending');
      startPolling();

      return response;
    },
    [completeFromSummary, onComplete, startJob, startPolling]
  );

  const handleReset = useCallback(() => {
    stopPolling();
    reset();
  }, [stopPolling, reset]);

  return {
    jobId,
    status,
    cacheKey,
    cacheStatus,
    summaryText,
    error,
    createdAt,
    updatedAt,
    isIdle: status === 'idle',
    isRunning: status === 'pending' || status === 'running',
    isCompleted: status === 'completed',
    isFailed: status === 'failed',
    submitSummary,
    stopPolling,
    reset: handleReset,
  };
}
