/**
 * 历史任务页面
 * 左侧历史列表 + 右侧任务详情的双栏布局
 */

import { useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { message } from 'antd';
import { useShallow } from 'zustand/react/shallow';
import { useHistoryStore } from '@/stores/historyStore';
import { getJobStatus } from '@/api/summaries';
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
    if (paramJobId) {
      selectJob(paramJobId);

      // 检查是否在历史记录中
      const existingJob = jobs.find((j) => resolveHistoryId(j) === paramJobId);

      if (!existingJob) {
        if (isCacheId(paramJobId) || isLocalId(paramJobId)) {
          const cacheKey = parseCacheKeyFromId(paramJobId);
          if (cacheKey) {
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
          } else {
            message.error('该记录为本地结果，请从历史列表查看');
          }
          return;
        }

        // 不在历史中，尝试从 API 获取
        getJobStatus(paramJobId)
          .then((response) => {
            const data = response.data;
            // 添加到历史记录
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
          })
          .catch(() => {
            message.error('无法获取任务信息，请检查 Job ID 是否正确');
          });
      }
    } else {
      selectJob(null);
    }
  }, [paramJobId, jobs, selectJob, addJob]);

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
