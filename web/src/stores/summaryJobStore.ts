/**
 * 摘要任务状态管理
 */

import { create } from 'zustand';
import type { JobStatusResponse, SummaryCreateResponse, SummaryStatus } from '@/types/summary';

type JobUiStatus = 'idle' | SummaryStatus;

interface SummaryJobState {
  jobId: string | null;
  status: JobUiStatus;
  cacheKey: string | null;
  cacheStatus: string | null;
  summaryText: string | null;
  error: string | null;
  createdAt: number | null;
  updatedAt: number | null;

  startJob: (jobId: string, cacheKey?: string | null, status?: SummaryStatus) => void;
  updateFromJob: (data: JobStatusResponse) => void;
  completeFromSummary: (data: SummaryCreateResponse) => void;
  failJob: (error: string) => void;
  reset: () => void;
}

const initialState = {
  jobId: null,
  status: 'idle' as JobUiStatus,
  cacheKey: null,
  cacheStatus: null,
  summaryText: null,
  error: null,
  createdAt: null,
  updatedAt: null,
};

export const useSummaryJobStore = create<SummaryJobState>((set) => ({
  ...initialState,

  startJob: (jobId, cacheKey = null, status = 'pending') =>
    set({
      jobId,
      status,
      cacheKey,
      cacheStatus: null,
      summaryText: null,
      error: null,
      createdAt: null,
      updatedAt: null,
    }),

  updateFromJob: (data) =>
    set({
      jobId: data.job_id,
      status: data.status,
      cacheKey: data.cache_key ?? null,
      cacheStatus: data.cache_status ?? null,
      summaryText: data.summary_text ?? null,
      error: data.error ?? null,
      createdAt: data.created_at ?? null,
      updatedAt: data.updated_at ?? null,
    }),

  completeFromSummary: (data) =>
    set({
      jobId: data.job_id ?? null,
      status: 'completed',
      cacheKey: data.cache_key ?? null,
      cacheStatus: 'completed',
      summaryText: data.summary_text ?? null,
      error: data.error ?? null,
      createdAt: data.created_at ?? null,
      updatedAt: data.created_at ?? null,
    }),

  failJob: (error) =>
    set({
      status: 'failed',
      error,
      updatedAt: Date.now(),
    }),

  reset: () => set(initialState),
}));
