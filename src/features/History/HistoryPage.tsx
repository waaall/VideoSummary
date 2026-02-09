/**
 * 历史任务页面
 * 左侧历史列表 + 右侧任务详情的双栏布局
 */

import { useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { message } from 'antd';
import { useShallow } from 'zustand/react/shallow';
import { useHistoryStore } from '@/stores/historyStore';
import { getJobStatus, getCacheEntry } from '@/api/summaries';
import { HistoryList } from './components/HistoryList';
import { JobDetail } from './components/JobDetail';
import { EmptyState } from './components/EmptyState';
import type { HistoryJob } from '@/types/history';
import {
  isCacheId,
  isLocalId,
  parseCacheKeyFromId,
  resolveHistoryId,
} from '@/utils/historyJob';
import styles from './HistoryPage.module.css';

export function HistoryPage() {
  const { jobId: paramJobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  const { jobs, selectedJobId, selectJob, addJob, updateJob } = useHistoryStore(
    useShallow((state) => ({
      jobs: state.jobs,
      selectedJobId: state.selectedJobId,
      selectJob: state.selectJob,
      addJob: state.addJob,
      updateJob: state.updateJob,
    }))
  );

  // 处理选中任务
  const handleSelectJob = useCallback(
    (jobId: string) => {
      selectJob(jobId);
      navigate(`/history/${jobId}`, { replace: true });
    },
    [selectJob, navigate]
  );

  // 处理任务更新
  const handleUpdateJob = useCallback(
    (updates: Partial<HistoryJob>) => {
      if (selectedJobId) {
        updateJob(selectedJobId, updates);
      }
    },
    [selectedJobId, updateJob]
  );

  // 根据 URL 参数加载任务
  useEffect(() => {
    let disposed = false;

    const loadFromParam = async () => {
      if (!paramJobId) {
        selectJob(null);
        return;
      }

      selectJob(paramJobId);

      // 仅在 URL 参数变化时处理，避免删除记录后因 jobs 变化把记录重新加回来
      const existingJob = useHistoryStore
        .getState()
        .jobs.find((j) => resolveHistoryId(j) === paramJobId);
      if (existingJob) {
        return;
      }

      if (isCacheId(paramJobId) || isLocalId(paramJobId)) {
        const cacheKey = parseCacheKeyFromId(paramJobId);
        if (!cacheKey) {
          message.error('该记录为本地结果，请从历史列表查看');
          return;
        }

        try {
          await getCacheEntry(cacheKey);
          if (disposed) {
            return;
          }

          const now = Date.now();
          const newJob: HistoryJob = {
            historyId: paramJobId,
            jobId: undefined,
            isCacheHit: true,
            sourceType: 'url',
            status: 'completed',
            cacheKey,
            cacheStatus: 'completed',
            createdAt: now,
            updatedAt: now,
          };
          addJob(newJob);
        } catch {
          if (disposed) {
            return;
          }
          message.warning('缓存不存在或已删除');
          navigate('/history', { replace: true });
        }
        return;
      }

      try {
        const response = await getJobStatus(paramJobId);
        if (disposed) {
          return;
        }

        const data = response.data;
        const newJob: HistoryJob = {
          historyId: data.job_id,
          jobId: data.job_id,
          sourceType: 'url',
          status: data.status,
          cacheKey: data.cache_key ?? undefined,
          cacheStatus: data.cache_status ?? undefined,
          sourceName: data.source_name ?? undefined,
          summaryText: data.summary_text ?? undefined,
          error: data.error ?? undefined,
          createdAt: data.created_at ?? Date.now(),
          updatedAt: data.updated_at ?? Date.now(),
        };
        addJob(newJob);
      } catch {
        if (disposed) {
          return;
        }
        message.error('无法获取任务信息，请检查 Job ID 是否正确');
      }
    };

    void loadFromParam();

    return () => {
      disposed = true;
    };
  }, [paramJobId, selectJob, addJob, navigate]);

  // 获取当前选中的任务
  const currentJob = jobs.find((j) => resolveHistoryId(j) === selectedJobId);

  return (
    <div className={styles.page}>
      {/* 左侧列表 */}
      <aside className={styles.sidebar}>
        <HistoryList onSelectJob={handleSelectJob} />
      </aside>

      {/* 右侧详情 */}
      <main className={styles.content}>
        {currentJob ? (
          <JobDetail job={currentJob} onUpdate={handleUpdateJob} />
        ) : (
          <EmptyState hasHistory={jobs.length > 0} />
        )}
      </main>
    </div>
  );
}
