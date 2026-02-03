/**
 * 摘要任务 Hook
 * 封装创建摘要与轮询逻辑
 */

import { useCallback } from 'react';
import { useSummaryJobStore } from '@/stores/summaryJobStore';
import { useSettingsStore } from '@/stores/settingsStore';
import { useHistoryStore } from '@/stores/historyStore';
import { createSummary, getJobStatus } from '@/api/summaries';
import { usePolling } from './usePolling';
import type { SummaryCreateRequest, JobStatusResponse } from '@/types/summary';
import type { HistoryJob } from '@/types/history';
import { CACHE_ID_PREFIX, LOCAL_ID_PREFIX } from '@/utils/historyJob';

interface UseSummaryJobOptions {
  pollingInterval?: number;
  onComplete?: (summaryText: string | null) => void;
  onError?: (error: string) => void;
}

// 用于传递给 submitSummary 的额外信息，记录到历史
interface SubmitContext {
  sourceUrl?: string;
  fileName?: string;
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
  const addJob = useHistoryStore((state) => state.addJob);
  const updateJob = useHistoryStore((state) => state.updateJob);
  const { onComplete, onError } = options;
  const pollingInterval = options.pollingInterval ?? pollingIntervalSetting;

  const handlePollingData = useCallback(
    (data: JobStatusResponse) => {
      updateFromJob(data);

      // 同步更新历史记录
      updateJob(data.job_id, {
        status: data.status,
        cacheKey: data.cache_key ?? undefined,
        cacheStatus: data.cache_status ?? undefined,
        sourceName: data.source_name ?? undefined,
        summaryText: data.summary_text ?? undefined,
        error: data.error ?? undefined,
      });

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
    [updateFromJob, updateJob, onComplete, onError, failJob]
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
    async (request: SummaryCreateRequest, context?: SubmitContext) => {
      const response = await createSummary(request);
      const data = response.data;
      const now = Date.now();

      if (data.status === 'completed') {
        const historyId =
          data.job_id ??
          (data.cache_key ? `${CACHE_ID_PREFIX}${data.cache_key}` : `${LOCAL_ID_PREFIX}${now}`);
        const normalized = { ...data, job_id: data.job_id ?? undefined, history_id: historyId };

        completeFromSummary(normalized);

        const historyJob: HistoryJob = {
          historyId,
          jobId: data.job_id ?? undefined,
          isCacheHit: !data.job_id && !!data.cache_key,
          sourceType: request.source_type,
          sourceUrl: context?.sourceUrl ?? request.source_url,
          fileName: context?.fileName,
          sourceName: request.source_type === 'local' ? context?.fileName : undefined,
          status: 'completed',
          cacheKey: data.cache_key ?? undefined,
          cacheStatus: 'completed',
          summaryText: data.summary_text ?? undefined,
          createdAt: data.created_at ?? now,
          updatedAt: now,
        };
        addJob(historyJob);

        onComplete?.(data.summary_text ?? null);
        return normalized;
      }

      if (!data.job_id) {
        throw new Error('响应缺少 job_id');
      }

      startJob(data.job_id, data.cache_key, 'pending');

      // 添加到历史记录
      const historyJob: HistoryJob = {
        historyId: data.job_id,
        jobId: data.job_id,
        sourceType: request.source_type,
        sourceUrl: context?.sourceUrl ?? request.source_url,
        fileName: context?.fileName,
        sourceName: request.source_type === 'local' ? context?.fileName : undefined,
        status: 'pending',
        cacheKey: data.cache_key ?? undefined,
        createdAt: now,
        updatedAt: now,
      };
      addJob(historyJob);

      startPolling();

      return data;
    },
    [completeFromSummary, onComplete, startJob, startPolling, addJob]
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
