/**
 * 历史记录列表组件
 */

import { useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Empty, Button, message } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { useHistoryStore, filterHistoryJobs } from '@/stores/historyStore';
import { deleteCache } from '@/api';
import { historyConfig } from '@/config/history';
import { SearchInput } from './SearchInput';
import { HistoryListItem } from './HistoryListItem';
import type { HistoryJob } from '@/types/history';
import styles from './HistoryList.module.css';

interface HistoryListProps {
  onSelectJob: (jobId: string) => void;
}

export function HistoryList({ onSelectJob }: HistoryListProps) {
  const navigate = useNavigate();
  const {
    jobs,
    selectedJobId,
    searchKeyword,
    setSearchKeyword,
    removeJob,
    clearHistory,
  } = useHistoryStore();

  // 过滤后的任务列表
  const filteredJobs = useMemo(
    () => filterHistoryJobs(jobs, searchKeyword),
    [jobs, searchKeyword]
  );

  // 默认显示数量
  const displayJobs = filteredJobs.slice(0, historyConfig.defaultDisplayCount);
  const hasMore = filteredJobs.length > historyConfig.defaultDisplayCount;

  const handleSelectJob = useCallback(
    (jobId: string) => {
      onSelectJob(jobId);
    },
    [onSelectJob]
  );

  const handleDeleteJob = useCallback(
    async (job: HistoryJob) => {
      if (!job.cacheKey) {
        message.error('缺少 cache_key，无法删除缓存');
        return;
      }

      try {
        const response = await deleteCache(job.cacheKey);
        if (response.data?.deleted) {
          if (selectedJobId === job.jobId) {
            navigate('/history', { replace: true });
          }
          removeJob(job.jobId);
          message.success('缓存已删除');
        } else {
          message.error('删除缓存失败');
        }
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : '删除缓存失败';
        message.error(errorMessage);
      }
    },
    [removeJob, selectedJobId, navigate]
  );

  const handleClearAll = useCallback(() => {
    clearHistory();
  }, [clearHistory]);

  return (
    <div className={styles.container}>
      {/* 搜索框 */}
      <SearchInput value={searchKeyword} onChange={setSearchKeyword} />

      {/* 列表区域 */}
      <div className={styles.listWrapper}>
        {filteredJobs.length === 0 ? (
          <div className={styles.emptyWrapper}>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                searchKeyword
                  ? '未找到匹配的任务'
                  : '暂无历史记录'
              }
            />
          </div>
        ) : (
          <div className={styles.list}>
            {displayJobs.map((job) => (
              <HistoryListItem
                key={job.jobId}
                job={job}
                isSelected={selectedJobId === job.jobId}
                onClick={() => handleSelectJob(job.jobId)}
                onDelete={() => {
                  void handleDeleteJob(job);
                }}
              />
            ))}

            {hasMore && (
              <div className={styles.moreHint}>
                还有 {filteredJobs.length - historyConfig.defaultDisplayCount} 条记录
              </div>
            )}
          </div>
        )}
      </div>

      {/* 底部操作栏 */}
      {jobs.length > 0 && (
        <div className={styles.footer}>
          <span className={styles.count}>
            共 {jobs.length} 条记录
          </span>
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={handleClearAll}
          >
            清空
          </Button>
        </div>
      )}
    </div>
  );
}
