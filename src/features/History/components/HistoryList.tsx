/**
 * 历史记录列表组件
 */

import { useCallback, useMemo } from 'react';
import { Empty, Button } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { useHistoryStore, filterHistoryJobs } from '@/stores/historyStore';
import { historyConfig } from '@/config/history';
import { SearchInput } from './SearchInput';
import { HistoryListItem } from './HistoryListItem';
import styles from './HistoryList.module.css';

interface HistoryListProps {
  onSelectJob: (jobId: string) => void;
}

export function HistoryList({ onSelectJob }: HistoryListProps) {
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
    (jobId: string) => {
      removeJob(jobId);
    },
    [removeJob]
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
                onDelete={() => handleDeleteJob(job.jobId)}
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
