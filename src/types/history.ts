/**
 * 历史记录相关类型
 */

import type { SummaryStatus } from './summary';

export interface HistoryJob {
  historyId: string;
  jobId?: string;
  sourceType: 'url' | 'local';
  sourceUrl?: string;
  fileName?: string;
  sourceName?: string;
  title?: string;
  status: SummaryStatus | 'idle';
  cacheKey?: string;
  cacheStatus?: string;
  isCacheHit?: boolean;
  summaryText?: string;
  error?: string;
  createdAt: number;
  updatedAt: number;
}
