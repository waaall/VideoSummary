/**
 * 历史记录相关类型
 */

import type { SummaryStatus } from './summary';

export interface HistoryJob {
  jobId: string;
  sourceType: 'url' | 'local';
  sourceUrl?: string;
  fileName?: string;
  title?: string;
  status: SummaryStatus | 'idle';
  cacheKey?: string;
  cacheStatus?: string;
  summaryText?: string;
  error?: string;
  createdAt: number;
  updatedAt: number;
}
