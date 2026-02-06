/**
 * 历史记录状态管理（带持久化）
 */

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import type { HistoryJob } from '@/types/history';
import { historyConfig } from '@/config/history';
import { resolveHistoryId } from '@/utils/historyJob';
import { appStateStorage } from '@/utils/storage';

interface HistoryState {
  jobs: HistoryJob[];
  selectedJobId: string | null;
  searchKeyword: string;

  // 操作方法
  addJob: (job: HistoryJob) => void;
  updateJob: (jobId: string, updates: Partial<HistoryJob>) => void;
  removeJob: (jobId: string) => void;
  selectJob: (jobId: string | null) => void;
  setSearchKeyword: (keyword: string) => void;
  clearHistory: () => void;
}

export const useHistoryStore = create<HistoryState>()(
  persist(
    (set) => ({
      jobs: [],
      selectedJobId: null,
      searchKeyword: '',

      // 添加任务
      addJob: (job) =>
        set((state) => {
          // 检查是否已存在（防止重复添加）
          const incomingId = resolveHistoryId(job);
          const exists = state.jobs.some((j) => resolveHistoryId(j) === incomingId);
          if (exists) {
            return state;
          }

          // 若 cacheKey 相同，仅保留最新的尝试记录
          if (job.cacheKey) {
            const sameCacheIndex = state.jobs.findIndex(
              (j) => j.cacheKey === job.cacheKey
            );

            if (sameCacheIndex !== -1) {
              const existingJob = state.jobs[sameCacheIndex];
              const isNewer =
                job.createdAt > existingJob.createdAt ||
                (job.createdAt === existingJob.createdAt &&
                  job.updatedAt > existingJob.updatedAt);

              if (!isNewer) {
                return state;
              }

              const newJobs = [
                job,
                ...state.jobs.filter((_, index) => index !== sameCacheIndex),
              ].slice(0, historyConfig.maxItems);

              const newSelectedJobId =
                state.selectedJobId === resolveHistoryId(existingJob)
                  ? incomingId
                  : state.selectedJobId;

              return { jobs: newJobs, selectedJobId: newSelectedJobId };
            }
          }

          // 添加到队首，并限制总数
          const newJobs = [job, ...state.jobs].slice(0, historyConfig.maxItems);
          return { jobs: newJobs };
        }),

      // 更新任务
      updateJob: (jobId, updates) =>
        set((state) => ({
          jobs: state.jobs.map((job) =>
            resolveHistoryId(job) === jobId
              ? { ...job, ...updates, updatedAt: Date.now() }
              : job
          ),
        })),

      // 删除任务
      removeJob: (jobId) =>
        set((state) => ({
          jobs: state.jobs.filter((job) => resolveHistoryId(job) !== jobId),
          selectedJobId:
            state.selectedJobId === jobId ? null : state.selectedJobId,
        })),

      // 选中任务
      selectJob: (jobId) => set({ selectedJobId: jobId }),

      // 设置搜索关键词
      setSearchKeyword: (keyword) => set({ searchKeyword: keyword }),

      // 清空历史
      clearHistory: () => set({ jobs: [], selectedJobId: null }),
    }),
    {
      name: historyConfig.storageKey,
      storage: createJSONStorage(() => appStateStorage),
      // 只持久化 jobs 数组
      partialize: (state) => ({ jobs: state.jobs }),
    }
  )
);

// 辅助方法：过滤历史记录
export function filterHistoryJobs(
  jobs: HistoryJob[],
  keyword: string
): HistoryJob[] {
  if (!keyword.trim()) {
    return jobs;
  }

  const lowerKeyword = keyword.toLowerCase();
  return jobs.filter((job) => {
    // 匹配 Job ID
    const idCandidate = resolveHistoryId(job);
    if (idCandidate && idCandidate.toLowerCase().includes(lowerKeyword)) return true;
    if (job.jobId?.toLowerCase().includes(lowerKeyword)) return true;
    if (job.cacheKey?.toLowerCase().includes(lowerKeyword)) return true;
    // 匹配 URL
    if (job.sourceUrl?.toLowerCase().includes(lowerKeyword)) return true;
    // 匹配文件名
    if (job.fileName?.toLowerCase().includes(lowerKeyword)) return true;
    // 匹配标题
    if (job.title?.toLowerCase().includes(lowerKeyword)) return true;
    // 匹配来源名称
    if (job.sourceName?.toLowerCase().includes(lowerKeyword)) return true;
    return false;
  });
}
