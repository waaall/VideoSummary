/**
 * 执行追踪时间线组件
 */

import { useMemo } from 'react';
import { Tooltip } from 'antd';
import type { TraceEvent } from '@/types/pipeline';
import { formatDuration, getNodeTypeName } from '@/utils/formatters';
import styles from './TraceTimeline.module.css';

interface TraceTimelineProps {
  trace: TraceEvent[];
  totalDuration?: number;
}

// 状态颜色
const statusColors: Record<string, string> = {
  completed: 'var(--color-success)',
  failed: 'var(--color-error)',
  skipped: 'var(--color-text-tertiary)',
  started: 'var(--color-accent-primary)',
};

export function TraceTimeline({ trace, totalDuration }: TraceTimelineProps) {
  // 计算时间线数据
  const timelineData = useMemo(() => {
    if (trace.length === 0) return [];

    // 计算累积时间
    let accumulatedTime = 0;
    const items = trace.map((event) => {
      const startTime = accumulatedTime;
      accumulatedTime += event.elapsed_ms;

      return {
        ...event,
        startTime,
        endTime: accumulatedTime,
      };
    });

    return items;
  }, [trace]);

  // 计算总时长
  const maxTime = useMemo(() => {
    if (totalDuration) return totalDuration;
    if (timelineData.length === 0) return 0;
    return timelineData[timelineData.length - 1].endTime;
  }, [timelineData, totalDuration]);

  if (timelineData.length === 0) {
    return (
      <div className={styles.empty}>
        暂无执行记录
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* 时间刻度 */}
      <div className={styles.timeScale}>
        <span>0s</span>
        <span>{formatDuration(maxTime / 2)}</span>
        <span>{formatDuration(maxTime)}</span>
      </div>

      {/* 时间线 */}
      <div className={styles.timeline}>
        {timelineData.map((item, index) => {
          const left = (item.startTime / maxTime) * 100;
          const width = (item.elapsed_ms / maxTime) * 100;

          return (
            <Tooltip
              key={`${item.node_id}-${index}`}
              title={
                <div className={styles.tooltipContent}>
                  <div className={styles.tooltipTitle}>
                    {getNodeTypeName(item.node_id)}
                  </div>
                  <div className={styles.tooltipInfo}>
                    耗时: {formatDuration(item.elapsed_ms)}
                  </div>
                  {item.error && (
                    <div className={styles.tooltipError}>
                      错误: {item.error}
                    </div>
                  )}
                </div>
              }
            >
              <div
                className={`${styles.timelineItem} ${styles[item.status]}`}
                style={{
                  left: `${left}%`,
                  width: `${Math.max(width, 1)}%`,
                  backgroundColor: statusColors[item.status] || statusColors.completed,
                }}
              />
            </Tooltip>
          );
        })}
      </div>

      {/* 节点列表 */}
      <div className={styles.nodeList}>
        {timelineData.map((item, index) => (
          <div
            key={`${item.node_id}-${index}`}
            className={`${styles.nodeItem} ${styles[item.status]}`}
          >
            <span
              className={styles.nodeIndicator}
              style={{ backgroundColor: statusColors[item.status] }}
            />
            <span className={styles.nodeName}>
              {getNodeTypeName(item.node_id)}
            </span>
            <span className={styles.nodeTime}>
              {formatDuration(item.elapsed_ms)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
