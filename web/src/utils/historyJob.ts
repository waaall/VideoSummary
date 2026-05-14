/**
 * 历史记录相关辅助方法
 */

import type { HistoryJob } from '@/types/history';

export const CACHE_ID_PREFIX = 'cache_';
export const LOCAL_ID_PREFIX = 'local_';

export function resolveHistoryId(job: HistoryJob): string {
  if (job.historyId) return job.historyId;
  if (job.jobId) return job.jobId;
  if (job.cacheKey) return `${CACHE_ID_PREFIX}${job.cacheKey}`;
  return '';
}

export function isCacheId(id?: string | null): boolean {
  return typeof id === 'string' && id.startsWith(CACHE_ID_PREFIX);
}

export function isLocalId(id?: string | null): boolean {
  return typeof id === 'string' && id.startsWith(LOCAL_ID_PREFIX);
}

export function parseCacheKeyFromId(id?: string | null): string | undefined {
  if (!id || !isCacheId(id)) return undefined;
  return id.slice(CACHE_ID_PREFIX.length);
}

export function resolveCacheKey(job: HistoryJob): string | undefined {
  return job.cacheKey ?? parseCacheKeyFromId(job.jobId) ?? parseCacheKeyFromId(job.historyId);
}

export function isCacheHistoryJob(job: HistoryJob): boolean {
  return (
    job.isCacheHit === true ||
    (!job.jobId && !!resolveCacheKey(job)) ||
    isCacheId(job.jobId)
  );
}
